from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional

class Category(BaseModel):
    id: str = Field(..., description="Unique identifier for the category")
    name: str = Field(..., description="Human-readable name of the category")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ImageMetadata(BaseModel):
    url: str = Field(..., description="Cloudinary URL of the image")
    cloudinary_id: str = Field(..., description="Cloudinary public ID")
    category_id: str = Field(..., description="Category ID the image belongs to")
    year: int = Field(..., description="Year associated with the image")
    tags: List[str] = Field(default=[], description="List of tags for the image")
    uploaded_by: int = Field(..., description="Telegram user ID of the uploader")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

class PaginatedResponse(BaseModel):
    total_count: int
    page: int
    per_page: int
    items: List[ImageMetadata]