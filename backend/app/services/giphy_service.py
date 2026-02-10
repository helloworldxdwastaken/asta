import httpx
import logging
from app.keys import get_api_key

logger = logging.getLogger(__name__)

class GiphyService:
    @staticmethod
    async def get_gif(query: str) -> str:
        """Fetch a GIF from Giphy based on the query. Returns markdown image string or empty string."""
        key = await get_api_key("giphy_api_key")
        if not key:
            return ""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search endpoint
                url = "https://api.giphy.com/v1/gifs/search"
                params = {
                    "api_key": key,
                    "q": query,
                    "limit": 1,
                    "rating": "pg-13",
                    "lang": "en"
                }
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("data"):
                        # Get the downsized medium url for faster loading, or original
                        # data[0]["images"]["downsized_medium"]["url"]
                        gif = data["data"][0]
                        img_url = gif["images"]["downsized"]["url"]
                        title = gif.get("title", "gif")
                        return f"![{title}]({img_url})"
        except Exception as e:
            logger.error(f"Giphy error: {e}")
        
        return ""
