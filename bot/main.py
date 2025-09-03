import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ConversationHandler , CallbackQueryHandler, MessageHandler, filters
from bot.states import (
    SELECTING_CATEGORY, SELECTING_YEAR, VIEWING_IMAGES,
    UPLOAD_SELECT_CATEGORY, UPLOAD_GET_YEAR, UPLOAD_GET_IMAGES, UPLOAD_NEXT_ACTION
)
from bot.handlers.base import get_base_handlers
from bot.handlers.browse import start_browse, get_browse_handlers
from bot.handlers.upload import handle_upload_category, handle_upload_images, handle_upload_next_action, handle_upload_year, start_upload_flow, cancel_upload, get_upload_handlers

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)
# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")
    
    application = (
        Application.builder()
        .token(token)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )
    # Add base command handlers (without browse/upload commands)
    for handler in get_base_handlers():
        application.add_handler(handler)
    
    # Add browse conversation handler
    browse_conv = ConversationHandler(
        entry_points=[CommandHandler("browse", start_browse)],
        states={
            SELECTING_CATEGORY: get_browse_handlers(),
            SELECTING_YEAR: get_browse_handlers(),
            VIEWING_IMAGES: get_browse_handlers(),
        },
        fallbacks=[],
        per_user=True,  # Track state per user
        per_chat=True,  # Track state per chat
        conversation_timeout=300
    )
    application.add_handler(browse_conv)
    
    # Add upload conversation handler
    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", start_upload_flow)],
        states={
            UPLOAD_SELECT_CATEGORY: [
                CallbackQueryHandler(handle_upload_category, pattern=r"^cat_")
            ],
            UPLOAD_GET_YEAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_upload_year)
            ],
            UPLOAD_GET_IMAGES: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_upload_images),
                CallbackQueryHandler(handle_upload_next_action, pattern=r"^(more_same|change_settings|stop_upload)$")
            ],
            UPLOAD_NEXT_ACTION: [
                CallbackQueryHandler(handle_upload_next_action, pattern=r"^(more_same|change_settings|stop_upload)$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
        per_user=True,
        per_chat=True,
        conversation_timeout=300
    )
    application.add_handler(upload_conv)
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()