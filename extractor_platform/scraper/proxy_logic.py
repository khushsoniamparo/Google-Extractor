import structlog
from django.utils import timezone
import aiohttp
from aiohttp_socks import ProxyConnector
import time

log = structlog.get_logger()

def get_active_proxy_url():
    """
    Checks database for Version 1.2 Proxy Rotation.
    Pulls a RANDOM active proxy from the Proxy list first.
    Fallbacks to ProxySetting if list is empty.
    """
    from jobs.models import Proxy, ProxySetting
    try:
        # 1. Try ROTATED PROXIES (High Priority)
        rotated = Proxy.objects.filter(is_active=True).order_by('?').first()
        if rotated:
            return rotated.url
            
        # 2. Fallback to STATIC SETTING
        setting = ProxySetting.objects.filter(key='active_proxy', is_active=True).first()
        if setting:
            return setting.url if hasattr(setting, 'url') else setting.value
    except Exception as e:
        log.error("proxy.db_error", error=str(e))
    return None

async def test_proxy_connection(proxy_url):
    """
    Tests a proxy URL and returns performance/location data.
    Used by the Admin UI.
    """
    results = {
        'success': False,
        'response_ms': 0,
        'ip': None,
        'location': 'Unknown',
        'error': None
    }
    
    start_time = time.time()
    try:
        # Use a reliable IP echo service
        test_url = "http://ip-api.com/json"
        
        # Use ProxyConnector to handle both HTTP and SOCKS
        connector = ProxyConnector.from_url(proxy_url, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(test_url, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results['success'] = True
                    results['ip'] = data.get('query')
                    results['location'] = f"{data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}"
                    results['response_ms'] = int((time.time() - start_time) * 1000)
                else:
                    results['error'] = f"Status Code: {resp.status}"
    except Exception as e:
        results['error'] = str(e)
        
    return results
