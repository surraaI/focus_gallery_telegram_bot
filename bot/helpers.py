import os
from dotenv import load_dotenv

load_dotenv()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admin_ids = [int(id) for id in os.getenv("BOT_ADMIN_IDS", "").split(",") if id]
    return user_id in admin_ids