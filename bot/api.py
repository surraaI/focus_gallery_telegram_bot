import httpx
import os
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from project root
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

# API configuration
BACKEND_URL = os.getenv("BOT_BACKEND_URL", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("BOT_BACKEND_API_KEY")

# ---- Cache storage ----
_cache = {
    "categories": {"data": None, "timestamp": None},
    "years": {},  # keyed by category_id
}
CACHE_DURATION = timedelta(minutes=5)


def _get_headers():
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


async def get_categories():
    now = datetime.now()
    # Return cached categories if still fresh
    if (
        _cache["categories"]["data"]
        and _cache["categories"]["timestamp"]
        and now - _cache["categories"]["timestamp"] < CACHE_DURATION
    ):
        return _cache["categories"]["data"]

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(f"{BACKEND_URL}/categories/", headers=_get_headers())
        if response.status_code != 200:
            logger.error(f"Failed to fetch categories: {response.status_code} - {response.text}")
            # fallback to last cached
            return _cache["categories"]["data"]

        data = response.json()
        _cache["categories"]["data"] = data
        _cache["categories"]["timestamp"] = now
        return data


async def get_years(category_id: str):
    now = datetime.now()
    if category_id in _cache["years"]:
        entry = _cache["years"][category_id]
        if entry["data"] and entry["timestamp"] and now - entry["timestamp"] < CACHE_DURATION:
            return entry["data"]

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BACKEND_URL}/images/years", 
            params={"category": category_id},
            headers=_get_headers()
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch years: {response.status_code} - {response.text}")
            return _cache["years"].get(category_id, {}).get("data")

        data = response.json()
        _cache["years"][category_id] = {"data": data, "timestamp": now}
        return data


async def get_images(category_id: str, year: int, page: int, per_page: int = 5):
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BACKEND_URL}/images",
            params={
                "category": category_id,
                "year": year,
                "page": page,
                "per_page": per_page
            },
            headers=_get_headers()
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch images: {response.status_code} - {response.text}")
            return None
        return response.json()


async def upload_image(file_path: str, data: dict) -> Optional[httpx.Response]:
    url = f"{BACKEND_URL}/images/"
    headers = _get_headers()

    if not API_KEY:
        logger.error("BOT_BACKEND_API_KEY is not set in environment")
        return None

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "image/jpeg")}
            form_data = {
                "category": data["category"],
                "year": str(data["year"]),
                "tags": data.get("tags", ""),
                "uploaded_by": str(data["uploaded_by"]),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=form_data,
                    files=files,
                    headers=headers,
                    timeout=30.0,
                )
                logger.info(f"Upload response: {response.status_code} - {response.text}")
                return response
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        return None
