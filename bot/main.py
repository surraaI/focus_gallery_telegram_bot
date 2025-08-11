import logging
import os
import httpx
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API configuration - Use 127.0.0.1 to avoid redirect issues
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = os.getenv("BOT_BACKEND_API_KEY")

# State constants for conversation flow
SELECTING_CATEGORY, SELECTING_YEAR, VIEWING_IMAGES = range(3)

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admin_ids = [int(id) for id in os.getenv("BOT_ADMIN_IDS", "").split(",") if id]
    return user_id in admin_ids

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with admin status"""
    user = update.effective_user
    admin_status = "🛡️ You are an ADMIN" if is_admin(user.id) else "👤 You are a regular user"
    await update.message.reply_text(
        f"Hi {user.first_name}! {admin_status}\n\n"
        "Use /upload to add new images (admins only)\n"
        "Use /browse to view images\n"
        "Use /categories to see available categories"
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's Telegram ID"""
    user = update.effective_user
    await update.message.reply_text(f"Your Telegram ID: `{user.id}`\n\n"
                                   "Provide this to the bot admin to get access",
                                   parse_mode='Markdown')

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt admin to upload an image"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    await update.message.reply_text(
        "📤 Please send an image with a caption in the format:\n"
        "`CategoryID|Year|optional,tags`\n\n"
        "Example: `gc-day|2025|event,group`\n\n"
        "Available categories: /categories",
        parse_mode='Markdown'
    )

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available categories"""
    try:
        url = f"{BACKEND_URL}/categories"
        logger.info(f"Fetching categories from: {url}")
        
        # Use follow_redirects to handle 307 redirects
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url)
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Failed to fetch categories: {error_detail}")
                await update.message.reply_text("❌ Failed to fetch categories. Server error.")
                return
            
            categories = response.json()
            logger.info(f"Received {len(categories)} categories")
            
            message = "📁 Available categories:\n\n"
            for cat in categories:
                message += f"- {cat['name']} (`{cat['id']}`)\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
    except httpx.ConnectError as ce:
        logger.error(f"Connection error: {str(ce)}")
        await update.message.reply_text("❌ Could not connect to the server. Is the backend running?")
    except Exception as e:
        logger.exception(f"Failed to get categories: {str(e)}")
        await update.message.reply_text("❌ Unexpected error fetching categories")

async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the browsing process"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{BACKEND_URL}/categories")
            if response.status_code != 200:
                await update.message.reply_text("❌ Failed to fetch categories. Please try again later.")
                return
            
            categories = response.json()
            if not categories:
                await update.message.reply_text("No categories available.")
                return
            
            keyboard = [
                [InlineKeyboardButton(cat['name'], callback_data=f"category_{cat['id']}")]
                for cat in categories
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📁 Select a category:",
                reply_markup=reply_markup
            )
            return SELECTING_CATEGORY
    except Exception as e:
        logger.error(f"Error in browse: {str(e)}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
        return ConversationHandler.END

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection and show years"""
    query = update.callback_query
    await query.answer()
    
    category_id = query.data.split('_')[1]
    context.user_data['category_id'] = category_id
    context.user_data['category_name'] = next((button.text for row in query.message.reply_markup.inline_keyboard for button in row if button.callback_data == query.data), category_id)
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                f"{BACKEND_URL}/images/years", 
                params={"category": category_id}
            )
            if response.status_code != 200:
                await query.edit_message_text("❌ Failed to fetch years for this category.")
                return SELECTING_CATEGORY
            
            years = response.json()
            if not years:
                await query.edit_message_text("No images available for this category.")
                return SELECTING_CATEGORY
            
            # Sort years in descending order
            years.sort(reverse=True)
            keyboard = [
                [InlineKeyboardButton(str(year), callback_data=f"year_{year}")]
                for year in years
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📅 Select a year for category: {context.user_data['category_name']}",
                reply_markup=reply_markup
            )
            return SELECTING_YEAR
    except Exception as e:
        logger.error(f"Error in category_selected: {str(e)}")
        await query.edit_message_text("❌ An error occurred. Please try again.")
        return SELECTING_CATEGORY

async def year_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle year selection and show first page of images"""
    query = update.callback_query
    await query.answer()
    
    year = int(query.data.split('_')[1])
    context.user_data['year'] = year
    context.user_data['page'] = 1
    
    return await show_images(update, context)

async def show_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show images for the current page"""
    query = update.callback_query
    if query:
        await query.answer()
    
    category_id = context.user_data['category_id']
    year = context.user_data['year']
    page = context.user_data['page']
    per_page = 5  # Default per_page
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                f"{BACKEND_URL}/images",
                params={
                    "category": category_id,
                    "year": year,
                    "page": page,
                    "per_page": per_page
                }
            )
            if response.status_code != 200:
                error_msg = response.json().get('detail', 'Failed to fetch images')
                await context.bot.send_message(
                    query.message.chat_id,
                    f"❌ Error: {error_msg}"
                )
                return VIEWING_IMAGES
            
            data = response.json()
            images = data['items']
            total_count = data['total_count']
            total_pages = (total_count + per_page - 1) // per_page
            
            if not images:
                await context.bot.send_message(
                    query.message.chat_id,
                    "No images found for this selection."
                )
                return VIEWING_IMAGES
            
            # Prepare media group for images (up to 10 images per message)
            media_group = []
            for img in images:
                media_group.append(InputMediaPhoto(
                    media=img['url'],
                    caption=f"📅 {year} | {context.user_data['category_name']}\n" +
                            (f"🏷️ Tags: {', '.join(img['tags'])}\n" if img['tags'] else "") +
                            f"🔼 Uploaded at: {img['uploaded_at']}"
                    if len(media_group) == 0 else img['url']  # Only first image has caption
                ))
            
            # Send the media group
            await context.bot.send_media_group(
                chat_id=query.message.chat_id,
                media=media_group
            )
            
            # Prepare pagination keyboard
            keyboard_buttons = []
            if page > 1:
                keyboard_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
            if page < total_pages:
                keyboard_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
            
            navigation_buttons = [
                InlineKeyboardButton("🔙 Back to Years", callback_data="back_years"),
                InlineKeyboardButton("🏠 Back to Categories", callback_data="back_categories")
            ]
            
            reply_markup = InlineKeyboardMarkup([keyboard_buttons, navigation_buttons])
            
            # Send pagination message
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📷 Page {page}/{total_pages} | Total images: {total_count}",
                reply_markup=reply_markup
            )
            
            return VIEWING_IMAGES
    except Exception as e:
        logger.exception(f"Error in show_images: {str(e)}")
        await context.bot.send_message(
            query.message.chat_id,
            "❌ An error occurred while loading images."
        )
        return VIEWING_IMAGES

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "prev_page":
        context.user_data['page'] -= 1
    elif query.data == "next_page":
        context.user_data['page'] += 1
    elif query.data == "back_years":
        # Go back to year selection
        return await category_selected(update, context)
    elif query.data == "back_categories":
        # Go back to category selection
        return await browse(update, context)
    
    return await show_images(update, context)

async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image upload from admin"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    photo = update.message.photo[-1]  # highest resolution
    caption = update.message.caption
    if not caption:
        await update.message.reply_text("❌ Missing caption. Use format: `CategoryID|Year|Tags`", 
                                      parse_mode='Markdown')
        return

    try:
        parts = caption.split('|')
        if len(parts) < 2:
            raise ValueError("Insufficient parts in caption")

        category = parts[0].strip()
        year = int(parts[1].strip())
        tags = parts[2].strip() if len(parts) > 2 else ""

        # Download the image
        file = await context.bot.get_file(photo.file_id)
        temp_file = f"temp_{file.file_id}.jpg"
        await file.download_to_drive(temp_file)

        # Prepare the request to our backend
        url = f"{BACKEND_URL}/images"
        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }
        data = {
            "category": category,
            "year": year,
            "tags": tags,
            "uploaded_by": user.id
        }
        
        # Use proper file handling
        with open(temp_file, 'rb') as f:
            files = {'file': f}
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, files=files, headers=headers)

        if response.status_code == 200:
            await update.message.reply_text("✅ Image uploaded successfully!")
        else:
            error = response.json().get("detail", "Upload failed")
            await update.message.reply_text(f"❌ Upload failed: {error}")

    except ValueError as ve:
        await update.message.reply_text(f"❌ Invalid format: {str(ve)}")
    except Exception as e:
        logger.exception("Image upload failed")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)

def main() -> None:
    """Start the bot."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")
    
    application = Application.builder().token(token).build()
    
    # Register commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("categories", list_categories))
    application.add_handler(CommandHandler("browse", browse))
    
    # Register callbacks
    application.add_handler(CallbackQueryHandler(category_selected, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(year_selected, pattern="^year_"))
    application.add_handler(CallbackQueryHandler(handle_pagination))
    
    # Handler for image uploads (with caption)
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_image_message))
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()