import time
import httpx
import logging
from app.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_cached_proxy_url = None
_last_fetch_time = 0
CACHE_TTL = 3600  # Cache proxy URL for 1 hour

def get_random_proxy() -> str | None:
    global _cached_proxy_url, _last_fetch_time

    settings = get_settings()

    # If they didn't provide a token, fallback to the hardcoded string
    if not settings.webshare_token:
        if settings.youtube_proxy:
            import random
            proxies = [p.strip() for p in settings.youtube_proxy.split(",") if p.strip()]
            if proxies:
                return random.choice(proxies)
        return None

    current_time = time.time()
    
    # Fetch from API if cache is empty or expired
    if not _cached_proxy_url or (current_time - _last_fetch_time) > CACHE_TTL:
        try:
            logger.info("Fetching Webshare API to build backbone proxy URL...")
            headers = {"Authorization": f"Token {settings.webshare_token}"}
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", 
                    headers=headers
                )
                r.raise_for_status()
                data = r.json()
            
            results = data.get("results", [])
            if results:
                p = results[0]
                # To bypass VPS firewalls (like Hetzner) that block random high outbound ports (e.g. 6754),
                # we connect to Webshare's load-balancer (Backbone Proxy) which runs on standard port 80.
                # Adding "-rotate" to the username tells the backbone proxy to route each request to a new IP!
                _cached_proxy_url = f"http://{p['username']}-rotate:{p['password']}@p.webshare.io:80"
                _last_fetch_time = current_time
                logger.info("Successfully configured backbone proxy URL.")
        except Exception as e:
            logger.error(f"Failed to fetch proxy auth from Webshare: {e}")
            raise AppError(f"Failed to authenticate with Webshare API: {e}")
            
    if _cached_proxy_url:
        return _cached_proxy_url
    
    raise AppError("Webshare API returned no credentials.")
