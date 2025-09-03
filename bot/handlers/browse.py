from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler
from bot import api
from bot.states import SELECTING_CATEGORY, SELECTING_YEAR, VIEWING_IMAGES

async def start_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the browsing process"""
    categories = await api.get_categories()
    if not categories:
        await update.message.reply_text("❌ No categories available.")
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

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection and show years"""
    query = update.callback_query
    await query.answer()
    
    category_id = query.data.split('_')[1]
    context.user_data['category_id'] = category_id
    context.user_data['category_name'] = next(
        (button.text for row in query.message.reply_markup.inline_keyboard 
         for button in row if button.callback_data == query.data), 
        category_id
    )
    
    years = await api.get_years(category_id)
    if not years:
        await query.edit_message_text("No images available for this category.")
        return SELECTING_CATEGORY
    
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
    per_page = 5
    
    data = await api.get_images(category_id, year, page, per_page)
    if not data:
        await context.bot.send_message(
            query.message.chat_id,
            "❌ Failed to load images."
        )
        return VIEWING_IMAGES
    
    images = data['items']
    total_count = data['total_count']
    total_pages = (total_count + per_page - 1) // per_page
    
    if not images:
        await context.bot.send_message(
            query.message.chat_id,
            "No images found for this selection."
        )
        return VIEWING_IMAGES
    
    media_group = []
    for img in images:
        media_group.append(InputMediaPhoto(
            media=img['url'],
            caption=f"📅 {year} | {context.user_data['category_name']}\n" +
                    (f"🏷️ Tags: {', '.join(img['tags'])}\n" if img['tags'] else "") +
                    f"🔼 Uploaded at: {img['uploaded_at']}"
            if len(media_group) == 0 else img['url']
        ))
    
    await context.bot.send_media_group(
        chat_id=query.message.chat_id,
        media=media_group
    )
    
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
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📷 Page {page}/{total_pages} | Total images: {total_count}",
        reply_markup=reply_markup
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
        return await category_selected(update, context)
    elif query.data == "back_categories":
        return await start_browse(update, context)
    
    return await show_images(update, context)

def get_browse_handlers():
    return [
        CallbackQueryHandler(category_selected, pattern="^category_"),
        CallbackQueryHandler(year_selected, pattern="^year_"),
        CallbackQueryHandler(handle_pagination)
    ]