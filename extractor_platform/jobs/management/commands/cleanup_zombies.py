# jobs/management/commands/cleanup_zombies.py
import os
import psutil
import platform
from django.core.management.base import BaseCommand
import structlog

log = structlog.get_logger()

class Command(BaseCommand):
    help = 'Kills any orphaned browser processes (Chrome/Chromium/Playwright) to free up RAM'

    def handle(self, *args, **options):
        system = platform.system()
        target_names = ['chrome', 'chromium', 'playwright', 'node'] # Playwright often runs via node
        
        count = 0
        self.stdout.write(self.style.NOTICE(f"Starting zombie cleanup on {system}..."))

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if any(target in name for target in target_names):
                    # Don't kill the current IDE or python process
                    if 'python' in name or 'vscode' in name:
                        continue
                        
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully terminated {count} zombie processes."))
            log.info("zombie.cleanup_success", terminated_count=count)
        else:
            self.stdout.write(self.style.SUCCESS("No zombie processes found."))
