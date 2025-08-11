import cloudinary
import cloudinary.uploader
from app.config import get_settings
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def configure_cloudinary():
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True
    )
    logger.info("Cloudinary configured successfully")

async def upload_to_cloudinary(file_path: str, folder: str = "focus_gallery") -> dict:
    try:
        result = cloudinary.uploader.upload(
            file_path,
            folder=folder,
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png"],
            transformation=[{"quality": "auto", "fetch_format": "auto"}]
        )
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id")
        }
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image upload to Cloudinary failed"
        )