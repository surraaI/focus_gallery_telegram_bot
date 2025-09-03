from fastapi import APIRouter, Query, Depends
from app.database import database
from app.models import ImageMetadata, PaginatedResponse
from typing import List

router = APIRouter()

@router.get("/years", response_model=List[int])
async def get_years(category: str = Query(...)):
    pipeline = [
        {"$match": {"category_id": category}},
        {"$group": {"_id": None, "years": {"$addToSet": "$year"}}}
    ]
    result = await database.db.images.aggregate(pipeline).to_list(1)
    if not result:
        return []
    return sorted(result[0].get("years", []), reverse=True)

@router.get("/", response_model=PaginatedResponse)
async def get_images(
    category: str = Query(...),
    year: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(5, ge=1, le=20)
):
    skip = (page - 1) * per_page
    query = {"category_id": category, "year": year}
    
    total_count = await database.db.images.count_documents(query)
    cursor = database.db.images.find(query).skip(skip).limit(per_page)
    
    images = []
    async for doc in cursor:
        images.append(ImageMetadata(**doc))
    
    return PaginatedResponse(
        total_count=total_count,
        page=page,
        per_page=per_page,
        items=images
    )