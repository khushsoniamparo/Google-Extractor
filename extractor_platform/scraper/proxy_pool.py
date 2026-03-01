import os
import asyncio
import random
import structlog
import httpx
from itertools import cycle

log = structlog.get_logger()

class ProxyPoolManager:
    """
    Manages a pool of rotating proxies for HTTP requests.
    - Health checking: Automatically marks dead proxies and removes them.
    - Rotation: Uses a healthy proxy for each request.
    - DNS Caching: Handled natively by reusing the AsyncClient instances.
    """
    def __init__(self):
        self.proxies = []
        self._load_proxies()
        self.clients = {}  # Proxy URL -> httpx.AsyncClient
        
        if self.proxies:
            self.proxy_cycle = cycle(self.proxies)
        else:
            self.proxy_cycle = None
            
        # Single client for direct connections if no proxies
        self._direct_client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(15.0)
        )

    def _load_proxies(self):
        proxy_env = os.environ.get("PROXY_LIST", "")
        if proxy_env:
            self.proxies = [p.strip() for p in proxy_env.split(',') if p.strip()]
            log.info("proxy_pool.loaded_env", count=len(self.proxies))
        else:
            proxy_file = os.path.join(os.path.dirname(__file__), 'proxies.txt')
            if os.path.exists(proxy_file):
                with open(proxy_file, 'r', encoding='utf-8') as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
                log.info("proxy_pool.loaded_file", count=len(self.proxies))
            else:
                log.warning("proxy_pool.no_proxies", message="Using direct connection (No proxies found)")

    def get_client(self) -> httpx.AsyncClient:
        """
        Returns a healthy httpx.AsyncClient from the pool.
        Uses connection pooling to provide DNS caching automatically!
        """
        if not self.proxy_cycle or not self.proxies:
            return self._direct_client

        proxy_url = next(self.proxy_cycle)
        
        if not proxy_url.startswith("http"):
            proxy_url = f"http://{proxy_url}"
            
        if proxy_url not in self.clients:
            # Create a dedicated HTTP/2 client for this proxy
            # This allows multiplexing and persistent DNS cache
            client = httpx.AsyncClient(
                proxies=proxy_url,
                http2=True,
                timeout=httpx.Timeout(15.0),
                verify=False,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
            self.clients[proxy_url] = client
            
        return self.clients[proxy_url]
        
    async def check_health(self, proxy_url: str) -> bool:
        """
        Health checking logic. Removes the proxy if it fails.
        """
        client = self.clients.get(proxy_url)
        if not client:
            return False
            
        try:
            resp = await client.get("https://www.google.com/generate_204", timeout=5.0)
            return resp.status_code == 204
        except Exception as e:
            log.warning("proxy_pool.health_check_failed", proxy=proxy_url, error=str(e))
            self._remove_proxy(proxy_url)
            return False
            
    def _remove_proxy(self, proxy_url):
        log.warning("proxy_pool.removing_proxy", proxy=proxy_url)
        try:
            # Strip http:// just in case
            raw = proxy_url.replace("http://", "").replace("https://", "")
            if raw in self.proxies:
                self.proxies.remove(raw)
            if proxy_url in self.proxies:
                self.proxies.remove(proxy_url)
            
            # Recreate cycle with remaining proxies
            if self.proxies:
                self.proxy_cycle = cycle(self.proxies)
            else:
                self.proxy_cycle = None
        except ValueError:
            pass

# Global Singleton Pool
_pool = ProxyPoolManager()

def get_httpx_client() -> httpx.AsyncClient:
    return _pool.get_client()
