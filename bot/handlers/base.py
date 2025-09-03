from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot import api
from bot.helpers import is_admin
from bot.handlers import browse, upload

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

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available categories"""
    categories = await api.get_categories()
    if not categories:
        await update.message.reply_text("❌ Failed to fetch categories.")
        return
    
    message = "📁 Available categories:\n\n"
    for cat in categories:
        message += f"- {cat['name']} (`{cat['id']}`)\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

def get_base_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("id", id_command),
        CommandHandler("categories", list_categories),
    ]