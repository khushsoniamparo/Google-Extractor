from django.core.management.base import BaseCommand
from scraper.proxy_pool import PROXIES
from jobs.models import Proxy

class Command(BaseCommand):
    help = 'Import proxies from scraper/proxy_pool.py into the database'

    def handle(self, *args, **options):
        imported = 0
        for url in PROXIES:
            proxy, created = Proxy.objects.get_or_create(url=url)
            if created:
                proxy.provider = 'Webshare' if 'webshare' in url.lower() else 'Manual'
                proxy.save()
                imported += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {imported} new proxies.'))
