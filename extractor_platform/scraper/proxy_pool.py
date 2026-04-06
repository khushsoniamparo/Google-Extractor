import time
import os
import random
import structlog
from dataclasses import dataclass

log = structlog.get_logger()

@dataclass
class ProxyState:
    url: str
    usage_count: int = 0
    last_used: float = 0
    is_cooling_down: bool = False

class ProxyManager:
    def __init__(self):
        # Pillar 2: Pool of proxies. 
        # User should populate this in the Admin panel or .env
        self.raw_proxies = [
            # PREMIER CHOICE: High-Quality Residential Proxy (Oxylabs/Smartproxy etc.)
            # Format: http://customer-USERNAME-cc-IN:PASSWORD@pr.oxylabs.io:7777
            # Replace USERNAME and PASSWORD with your actual credentials below:
            'http://pnvmjqjm:t099twoh9t0l@31.59.20.176:6754', 
        ]
        
        # Add from env for flexibility
        env_proxies = os.getenv('SCRAPER_PROXIES', '')
        if env_proxies:
            for p in env_proxies.split(','):
                p = p.strip()
                if p and p not in self.raw_proxies:
                    self.raw_proxies.append(p)
                    
        self.proxies = [ProxyState(url=p) for p in self.raw_proxies]
        self.usage_limit = 10 # Pillar 3: Max 10 searches per proxy
        self.cooldown_seconds = 7200 # Pillar 3: 2 hour cooldown

    def get_proxy(self):
        """Pillar 3: Smart pick - finds an available proxy with usage < limit or reset cooldowns."""
        now = time.time()
        
        # 1. Reset cooldowns for proxies that have rested long enough
        for p in self.proxies:
            if p.is_cooling_down and (now - p.last_used) > self.cooldown_seconds:
                p.is_cooling_down = False
                p.usage_count = 0 
                log.info("proxy.cooldown_ended", proxy=p.url[:25]+"...")

        # 2. Filter for usable proxies
        available = [p for p in self.proxies if not p.is_cooling_down]
        
        if not available:
            # Emergency: if everything is cooling, pick the one with longest rest
            log.warning("proxy.all_cooling", count=len(self.proxies))
            return random.choice(self.raw_proxies) if self.raw_proxies else None

        # 3. Pick the one with the lowest usage to spread load
        available.sort(key=lambda x: x.usage_count)
        chosen = available[0]
        
        chosen.usage_count += 1
        chosen.last_used = now
        
        if chosen.usage_count >= self.usage_limit:
            chosen.is_cooling_down = True
            log.info("proxy.entering_cooldown", proxy=chosen.url[:25]+"...")
            
        return chosen.url

proxy_manager = ProxyManager()

def get_random_proxy():
    return proxy_manager.get_proxy()

def get_proxy_dict():
    p = proxy_manager.get_proxy()
    return {'http': p, 'https': p} if p else None

# Legacy global vars for compatibility
PROXIES = proxy_manager.raw_proxies
HTTP_PROXY = PROXIES[0] if PROXIES else None
SOCKS5_PROXY = None # Will be derived from HTTP_PROXY if needed
if HTTP_PROXY:
    SOCKS5_PROXY = HTTP_PROXY.replace('http://', 'socks5://')
