from fastapi import APIRouter, Depends
from app.database import database
from app.models import Category
from typing import List

router = APIRouter()

@router.get("", response_model=List[Category])
async def get_categories():
    categories = []
    cursor = database.db.categories.find({})
    async for doc in cursor:
        categories.append(Category(**doc))
    return categories