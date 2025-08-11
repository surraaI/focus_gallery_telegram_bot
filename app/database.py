from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
import logging
from pymongo.errors import ConfigurationError

logger = logging.getLogger(__name__)
settings = get_settings()

class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            
            # Extract database name from URL or use default
            if '/' in settings.mongodb_url:
                db_name = settings.mongodb_url.split('/')[-1].split('?')[0]
            else:
                db_name = "focus_gallery"
                
            if not db_name:
                db_name = "focus_gallery"
                
            self.db = self.client[db_name]
            logger.info(f"Connected to MongoDB database: {db_name}")
            
            await self._ensure_indexes()
            await self._seed_initial_data()
        except ConfigurationError as ce:
            logger.error(f"Configuration error: {str(ce)}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    # ... rest of the class remains the same ...

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    async def _ensure_indexes(self):
        try:
            # Create indexes for faster queries
            await self.db.categories.create_index("id", unique=True)
            await self.db.images.create_index([("category_id", 1), ("year", 1)])
            await self.db.images.create_index("uploaded_at")
            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")

    async def _seed_initial_data(self):
        try:
            # Seed initial categories if they don't exist
            initial_categories = [
                {"id": "gc-day", "name": "GC day"},
                {"id": "praise-night", "name": "Praise night"},
                {"id": "go-focus", "name": "Go Focus"},
                {"id": "easter", "name": "Easter"},
                {"id": "manuscript", "name": "Manuscript"}
            ]
            
            for category in initial_categories:
                await self.db.categories.update_one(
                    {"id": category["id"]},
                    {"$setOnInsert": category},
                    upsert=True
                )
            logger.info("Seeded initial categories")
        except Exception as e:
            logger.error(f"Failed to seed initial data: {str(e)}")

# Database instance to be imported
database = Database()