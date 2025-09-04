from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import database
from app.routers import categories, images, upload
from app.services.cloudinary import configure_cloudinary
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Focus Gallery API",
    description="Backend API for Focus Gallery Telegram Bot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
app.include_router(images.router, prefix="/api/v1/images", tags=["images"])
app.include_router(upload.router, prefix="/api/v1/images", tags=["upload"])

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    try:
        await database.connect()
        configure_cloudinary()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    await database.close()
    logger.info("Application shutdown complete")

@app.get("/")
async def root():
    return {"message": "Focus Gallery API is running"}