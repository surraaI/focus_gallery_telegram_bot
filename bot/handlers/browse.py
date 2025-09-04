from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler
from bot import api
from bot.states import SELECTING_CATEGORY, SELECTING_YEAR, VIEWING_IMAGES

async def start_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the browsing process"""
    # Clear any previous browsing data
    context.user_data.pop('category_id', None)
    context.user_data.pop('category_name', None)
    context.user_data.pop('year', None)
    context.user_data.pop('page', None)
    
    categories = await api.get_categories()
    if not categories:
        # Handle both message and callback query cases
        if update.message:
            await update.message.reply_text("❌ No categories available.")
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text("❌ No categories available.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(cat['name'], callback_data=f"category_{cat['id']}")]
        for cat in categories
    ]
    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_browse")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Handle both message and callback query cases
    if update.message:
        await update.message.reply_text(
            "📁 Select a category:",
            reply_markup=reply_markup
        )
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(
            "📁 Select a category:",
            reply_markup=reply_markup
        )
    
    return SELECTING_CATEGORY

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection and show years"""
    query = update.callback_query
    await query.answer()
    
    # Handle cancel action
    if query.data == "cancel_browse":
        await query.edit_message_text("Browsing cancelled.")
        return ConversationHandler.END
    
    # Check if this is a callback from navigation or initial selection
    if query.data.startswith("category_"):
        category_id = query.data.split('_')[1]
        context.user_data['category_id'] = category_id
        context.user_data['category_name'] = next(
            (button.text for row in query.message.reply_markup.inline_keyboard 
             for button in row if button.callback_data == query.data), 
            category_id
        )
    
    # Ensure category_id exists in context
    if 'category_id' not in context.user_data:
        await query.edit_message_text("Category not found. Please start over.")
        return await start_browse(update, context)
    
    category_id = context.user_data['category_id']
    
    years = await api.get_years(category_id)
    if not years:
        # Show message with back button when no images available
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Categories", callback_data="back_categories")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"No images available for category: {context.user_data['category_name']}",
            reply_markup=reply_markup
        )
        return SELECTING_CATEGORY
    
    years.sort(reverse=True)
    keyboard = [
        [InlineKeyboardButton(str(year), callback_data=f"year_{year}")]
        for year in years
    ]
    # Add navigation buttons
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Categories", callback_data="back_categories"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_browse")
    ])
    
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
    
    # Handle cancel action
    if query.data == "cancel_browse":
        await query.edit_message_text("Browsing cancelled.")
        return ConversationHandler.END
    
    year = int(query.data.split('_')[1])
    context.user_data['year'] = year
    context.user_data['page'] = 1
    
    return await show_images(update, context)

async def show_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show images for the current page"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Check if required data exists in context
    if 'category_id' not in context.user_data or 'year' not in context.user_data:
        chat_id = query.message.chat_id if query and query.message else update.effective_chat.id
        await context.bot.send_message(
            chat_id,
            "❌ Session data lost. Please start over with /browse."
        )
        return ConversationHandler.END
    
    category_id = context.user_data['category_id']
    year = context.user_data['year']
    page = context.user_data.get('page', 1)
    per_page = 5
    
    data = await api.get_images(category_id, year, page, per_page)
    if not data:
        chat_id = query.message.chat_id if query and query.message else update.effective_chat.id
        
        # Show error message with navigation options
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Years", callback_data="back_years")],
            [InlineKeyboardButton("🏠 Back to Categories", callback_data="back_categories")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_browse")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id,
            "❌ Failed to load images.",
            reply_markup=reply_markup
        )
        return VIEWING_IMAGES
    
    images = data['items']
    total_count = data['total_count']
    total_pages = (total_count + per_page - 1) // per_page
    
    if not images:
        chat_id = query.message.chat_id if query and query.message else update.effective_chat.id
        
        # Show no images message with navigation options
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Years", callback_data="back_years")],
            [InlineKeyboardButton("🏠 Back to Categories", callback_data="back_categories")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_browse")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id,
            "No images found for this selection.",
            reply_markup=reply_markup
        )
        return VIEWING_IMAGES
    
    chat_id = query.message.chat_id if query and query.message else update.effective_chat.id
    
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
        chat_id=chat_id,
        media=media_group
    )
    
    keyboard_buttons = []
    if page > 1:
        keyboard_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
    if page < total_pages:
        keyboard_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
    
    navigation_buttons = [
        InlineKeyboardButton("🔙 Back to Years", callback_data="back_years"),
        InlineKeyboardButton("🏠 Back to Categories", callback_data="back_categories"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_browse")
    ]
    
    # Create keyboard layout
    keyboard = []
    if keyboard_buttons:
        keyboard.append(keyboard_buttons)
    keyboard.append(navigation_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
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
        return await show_images(update, context)
    elif query.data == "next_page":
        context.user_data['page'] += 1
        return await show_images(update, context)
    elif query.data == "back_years":
        # Clear the current image data but keep category info
        context.user_data.pop('year', None)
        context.user_data.pop('page', None)
        
        # Check if we have a message to edit
        if query.message:
            return await category_selected(update, context)
        else:
            # If no message, start fresh
            return await start_browse(update, context)
    elif query.data == "back_categories":
        # Clear all browsing data
        context.user_data.pop('category_id', None)
        context.user_data.pop('category_name', None)
        context.user_data.pop('year', None)
        context.user_data.pop('page', None)
        
        # Check if we have a message to edit
        if query.message:
            # Send a new message instead of trying to edit
            await query.message.reply_text("Returning to categories...")
            return await start_browse(update, context)
        else:
            # If no message, start fresh
            return await start_browse(update, context)
    elif query.data == "cancel_browse":
        await query.edit_message_text("Browsing cancelled.")
        return ConversationHandler.END
    
    return VIEWING_IMAGES

def get_browse_handlers():
    return [
        CallbackQueryHandler(category_selected, pattern="^category_"),
        CallbackQueryHandler(year_selected, pattern="^year_"),
        CallbackQueryHandler(handle_pagination)
    ]