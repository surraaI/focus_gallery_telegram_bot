import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler , CallbackQueryHandler
from bot import api
from telegram.error import TimedOut
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bot.helpers import is_admin
from bot.states import UPLOAD_SELECT_CATEGORY, UPLOAD_GET_YEAR, UPLOAD_GET_IMAGES, UPLOAD_NEXT_ACTION

logger = logging.getLogger(__name__)

async def start_upload_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Upload flow started by user {user.id}")
    
    if not is_admin(user.id):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return ConversationHandler.END
    
    # Initialize upload state
    context.user_data['upload_state'] = {
        'category_id': None,
        'category_name': None,
        'year': None
    }
    
    # Fetch categories
    categories = await api.get_categories()
    if not categories:
        await update.message.reply_text("❌ No categories available.")
        return ConversationHandler.END
    
    # Create category selection keyboard
    keyboard = [
        [InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['id']}")]
        for cat in categories
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📁 Select a category for your upload:",
        reply_markup=reply_markup
    )
    
    return UPLOAD_SELECT_CATEGORY

async def handle_upload_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Extract category ID safely
    try:
        # Changed pattern to more generic "cat_"
        category_id = query.data.split('_', 1)[1]
        logger.info(f"Received category selection: {category_id}")
        
        # Find category name from keyboard
        for row in query.message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data == query.data:
                    context.user_data['upload_state']['category_id'] = category_id
                    context.user_data['upload_state']['category_name'] = button.text
                    break
    except Exception as e:
        logger.error(f"Error processing category selection: {str(e)}")
        await query.edit_message_text("❌ Error processing your selection. Please try again.")
        return ConversationHandler.END
    
    logger.info(f"Category selected: {context.user_data['upload_state']['category_name']} (ID: {category_id})")
    
    await query.edit_message_text(
        f"✅ Category selected: {context.user_data['upload_state']['category_name']}\n\n"
        "📅 Now please enter the year for these images (e.g., 2025):"
    )
    return UPLOAD_GET_YEAR

async def handle_upload_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = int(update.message.text)
        if year < 2000 or year > 2100:
            raise ValueError("Invalid year")
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid year between 2000 and 2100.")
        return UPLOAD_GET_YEAR
    
    context.user_data['upload_state']['year'] = year
    logger.info(f"Year set to: {year}")
    
    await update.message.reply_text(
        f"✅ Year set to: {year}\n\n"
        "📤 Now send me the images you want to upload. You can send multiple images at once.\n\n"
        "After sending images, I'll ask what you'd like to do next."
    )
    return UPLOAD_GET_IMAGES

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(TimedOut)  
)
async def download_with_retry(file, destination):
    await file.download_to_drive(destination)

async def handle_upload_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Image upload handler triggered")
    
    photos = update.message.photo
    if not photos:
        await update.message.reply_text("⚠️ Please send actual images.")
        return UPLOAD_GET_IMAGES

    uploaded_count = 0
    failed_count = 0
    upload_state = context.user_data['upload_state']
    user = update.effective_user

    # Process each photo (use highest quality version)
    photo = photos[-1]
    temp_file = None
    try:
        file = await context.bot.get_file(photo.file_id)
        temp_file = f"temp_{file.file_id}.jpg"
        
        # Use retry mechanism for download
        await download_with_retry(file, temp_file)
        logger.info(f"Downloaded image to: {temp_file}")

        data = {
            "category": upload_state['category_id'],
            "year": upload_state['year'],
            "tags": "",
            "uploaded_by": user.id
        }
        
        logger.debug(f"Sending upload request with data: {data}")
        response = await api.upload_image(temp_file, data)
        
        if response and response.status_code == 200:
            uploaded_count += 1
            logger.info(f"Uploaded image successfully: {response.json().get('id')}")
        else:
            error_msg = response.text if response else "No response"
            logger.error(f"Upload failed: {error_msg}")
            failed_count += 1
            
    except TimedOut:
        logger.error("Timed out during image download")
        failed_count += 1
        await update.message.reply_text("⌛ Download timed out. Please try sending the image again.")
        return UPLOAD_GET_IMAGES
        
    except Exception as e:
        logger.exception(f"Image upload error: {str(e)}")
        failed_count += 1
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
            logger.debug(f"Removed temp file: {temp_file}")
    
    # Show results
    result_message = f"📤 Upload results:\n- ✅ Success: {uploaded_count}\n- ❌ Failed: {failed_count}"
    await update.message.reply_text(result_message)
    
    # Next action keyboard
    keyboard = [
        [InlineKeyboardButton("📤 Upload more for same category/year", callback_data="more_same")],
        [InlineKeyboardButton("🔄 Change category/year", callback_data="change_settings")],
        [InlineKeyboardButton("🚫 Stop uploading", callback_data="stop_upload")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "What would you like to do next?",
        reply_markup=reply_markup
    )
    return UPLOAD_NEXT_ACTION

async def handle_upload_next_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "more_same":
        await query.edit_message_text("📤 Send me more images for the same category/year...")
        return UPLOAD_GET_IMAGES
    
    elif choice == "change_settings":
        categories = await api.get_categories()
        if not categories:
            await query.edit_message_text("❌ Failed to fetch categories.")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['id']}")]
            for cat in categories
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📁 Select a new category for your upload:",
            reply_markup=reply_markup
        )
        return UPLOAD_SELECT_CATEGORY
    
    elif choice == "stop_upload":
        await query.edit_message_text("✅ Upload session ended. Thank you!")
        return ConversationHandler.END
    
    return UPLOAD_NEXT_ACTION

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Upload process cancelled.")
    return ConversationHandler.END

def get_upload_handlers():
    return [
        CallbackQueryHandler(handle_upload_category, pattern=r"^cat_"),
        CallbackQueryHandler(handle_upload_next_action, pattern=r"^(more_same|change_settings|stop_upload)$"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_upload_year),
        MessageHandler(filters.PHOTO, handle_upload_images),
    ]