import httpx
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# API configuration
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = os.getenv("BOT_BACKEND_API_KEY")  

async def get_categories():
    headers = {}
    if API_KEY:
         headers['Authorization'] = API_KEY
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(f"{BACKEND_URL}/categories/", headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch categories: {response.status_code} - {response.text}")
            return None
        return response.json()

async def get_years(category_id: str):
    headers = {}
    if API_KEY:
         headers['Authorization'] = API_KEY
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BACKEND_URL}/images/years", 
            params={"category": category_id},
            headers=headers
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch years: {response.status_code} - {response.text}")
            return None
        return response.json()

async def get_images(category_id: str, year: int, page: int, per_page: int = 5):
    headers = {}
    if API_KEY:
         headers['Authorization'] = API_KEY
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BACKEND_URL}/images",
            params={
                "category": category_id,
                "year": year,
                "page": page,
                "per_page": per_page
            },
            headers=headers
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch images: {response.status_code} - {response.text}")
            return None
        return response.json()

async def upload_image(file_path: str, data: dict) -> Optional[httpx.Response]:
    url = f"{BACKEND_URL}/images/"
    headers = {}
    
    if API_KEY:
        headers['Authorization'] = f'Bearer {API_KEY}'
        logger.info(f"Using API key: {API_KEY[:10]}...")  # Log first 10 chars for debugging
    else:
        logger.error("BOT_BACKEND_API_KEY is not set in environment")
        return None
    
    try:
        # Open the file and prepare for upload
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'image/jpeg')}
            
            # Prepare form data
            form_data = {
                'category': data['category'],
                'year': str(data['year']),
                'tags': data.get('tags', ''),
                'uploaded_by': str(data['uploaded_by'])
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, 
                    data=form_data, 
                    files=files, 
                    headers=headers,
                    timeout=30.0
                )
                logger.info(f"Upload response: {response.status_code} - {response.text}")
                return response
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        return None