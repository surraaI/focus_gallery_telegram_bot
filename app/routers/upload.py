import os
import aiofiles
import logging
from fastapi import APIRouter, UploadFile, Form, File, Depends, HTTPException, status
from app.database import database
from app.models import ImageMetadata
from app.services.cloudinary import upload_to_cloudinary
from app.utils.security import verify_api_key
from datetime import datetime
from typing import List, Optional
import tempfile

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)

@router.post("/", response_model=ImageMetadata)
async def upload_image(
    file: UploadFile = File(...),
    category: str = Form(...),
    year: int = Form(...),
    tags: str = Form(""),
    uploaded_by: int = Form(...)
):
    # Validate file type and size
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only JPG, JPEG, PNG are allowed."
        )
    
    # Create a temporary file with a proper extension
    file_ext = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        content = await file.read()
        
        # Check size (8 MB max)
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 8 MB limit"
            )
        
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        # Upload to Cloudinary - ADD AWAIT HERE
        upload_result = await upload_to_cloudinary(temp_file_path)
        
        # Prepare tags
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
        
        # Create image document
        image_doc = {
            "url": upload_result["url"],
            "cloudinary_id": upload_result["public_id"],
            "category_id": category,
            "year": year,
            "tags": tag_list,
            "uploaded_by": uploaded_by,
            "uploaded_at": datetime.utcnow()
        }
        
        # Save to database
        result = await database.db.images.insert_one(image_doc)
        image_doc["_id"] = result.inserted_id
        
        return ImageMetadata(**image_doc)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Image upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image upload failed"
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.debug(f"Removed temp file: {temp_file_path}")