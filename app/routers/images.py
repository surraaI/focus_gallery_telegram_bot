from fastapi import APIRouter, Query, HTTPException, status
from app.database import database
from app.models import ImageMetadata, PaginatedResponse
from typing import List, Optional

router = APIRouter()

@router.get("/years", response_model=List[int])
async def get_years(category: str = Query(...)):
    try:
        pipeline = [
            {"$match": {"category_id": category}},
            {"$group": {"_id": None, "years": {"$addToSet": "$year"}}}
        ]
        result = await database.db.images.aggregate(pipeline).to_list(1)
        if not result:
            return []
        return sorted(result[0].get("years", []), reverse=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching years: {str(e)}"
        )

@router.get("/", response_model=PaginatedResponse)
@router.get("", response_model=PaginatedResponse)  
async def get_images(
    category: str = Query(...),
    year: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(5, ge=1, le=20)
):
    try:
        skip = (page - 1) * per_page
        query = {"category_id": category, "year": year}
        
        total_count = await database.db.images.count_documents(query)
        cursor = database.db.images.find(query).skip(skip).limit(per_page)
        
        images = []
        async for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            images.append(ImageMetadata(**doc))
        
        return PaginatedResponse(
            total_count=total_count,
            page=page,
            per_page=per_page,
            items=images
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching images: {str(e)}"
        )