import time
import httpx
import random
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

_cached_proxies = []
_last_fetch_time = 0
CACHE_TTL = 3600  # Cache proxy list for 1 hour

def get_random_proxy() -> str | None:
    global _cached_proxies, _last_fetch_time

    settings = get_settings()

    # If they didn't provide a token, fallback to the hardcoded string
    if not settings.webshare_token:
        if settings.youtube_proxy:
            proxies = [p.strip() for p in settings.youtube_proxy.split(",") if p.strip()]
            if proxies:
                return random.choice(proxies)
        return None

    current_time = time.time()
    
    # Fetch from API if cache is empty or expired
    if not _cached_proxies or (current_time - _last_fetch_time) > CACHE_TTL:
        try:
            logger.info("Fetching fresh proxies from Webshare API...")
            headers = {"Authorization": f"Token {settings.webshare_token}"}
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", 
                    headers=headers
                )
                r.raise_for_status()
                data = r.json()
            
            new_proxies = []
            for p in data.get("results", []):
                # Include username/password so it works locally. 
                # On Coolify (where your IP is whitelisted), Webshare will just ignore the password and let you through anyway!
                proxy_str = f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}/"
                new_proxies.append(proxy_str)
                
            if new_proxies:
                _cached_proxies = new_proxies
                _last_fetch_time = current_time
                logger.info(f"Successfully cached {len(_cached_proxies)} proxies.")
        except Exception as e:
            logger.error(f"Failed to fetch proxies from Webshare: {e}")
            
    if _cached_proxies:
        return random.choice(_cached_proxies)
    
    return None
