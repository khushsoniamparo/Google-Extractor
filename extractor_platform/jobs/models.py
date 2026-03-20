# jobs/models.py
from django.db import models
from django.contrib.auth.models import User


class BulkJob(models.Model):
    """
    One bulk job = multiple keywords, one location.
    Parent that holds everything together.
    """
    STATUS = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    EXECUTION_MODES = [
        ('direct', 'Direct Connection'),
        ('proxy', 'Proxy Active'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bulk_jobs'
    )
    location = models.CharField(max_length=500)
    grid_size = models.IntegerField(default=8)
    strategy = models.CharField(
        max_length=50, 
        choices=[
            ('fast', 'Fast (144 cells)'),
            ('detailed', 'Detailed (225 cells)'),
            ('deep', 'Deep (400 cells)'),
            ('ultra', 'Ultra (625 cells)'),
            ('geolocation', 'Geolocation'),
        ],
        default='fast'
    )
    status = models.CharField(
        max_length=20, choices=STATUS, default='pending'
    )
    execution_mode = models.CharField(
        max_length=20, choices=EXECUTION_MODES, default='direct'
    )
    status_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"BulkJob({self.id}) in {self.location} — {self.status}"

    @property
    def total_extracted(self):
        return sum(j.total_extracted for j in self.keyword_jobs.all())

    @property
    def all_complete(self):
        jobs = self.keyword_jobs.all()
        return jobs.exists() and all(
            j.status in ('completed', 'failed') for j in jobs
        )


class KeywordJob(models.Model):
    """
    One keyword inside a BulkJob.
    Each gets its own results, own status, own CSV.
    """
    STATUS = [
        ('pending', 'Pending'),
        ('fetching_boundary', 'Fetching Boundary'),
        ('building_grid', 'Building Grid'),
        ('searching', 'Searching'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    bulk_job = models.ForeignKey(
        BulkJob, on_delete=models.CASCADE, related_name='keyword_jobs'
    )
    keyword = models.CharField(max_length=500)
    status = models.CharField(
        max_length=30, choices=STATUS, default='pending'
    )
    status_message = models.CharField(max_length=500, blank=True)
    error_message = models.TextField(blank=True)

    total_cells = models.IntegerField(default=0)
    cells_done = models.IntegerField(default=0)
    total_extracted = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"KeywordJob({self.id}) '{self.keyword}' — {self.status}"

    @property
    def progress_percent(self):
        if self.total_cells == 0:
            return 0
        return int((self.cells_done / self.total_cells) * 100)


class Place(models.Model):
    """One extracted business. Belongs to a KeywordJob."""
    keyword_job = models.ForeignKey(
        KeywordJob, on_delete=models.CASCADE, related_name='places'
    )

    place_id = models.CharField(max_length=500, blank=True)
    name = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=300, blank=True)
    street = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=200, blank=True)
    state = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    website = models.URLField(max_length=2000, blank=True)
    rating = models.CharField(max_length=20, blank=True)
    review_count = models.CharField(max_length=50, blank=True)
    maps_url = models.URLField(max_length=2000, blank=True)
    latitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=13, decimal_places=8, null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['keyword_job', 'place_id']

    def __str__(self):
        return self.name


class Proxy(models.Model):
    """Proxy storage for management via Admin Panel."""
    PROTOCOL_CHOICES = [
        ('http', 'HTTP'),
        ('socks4', 'SOCKS4'),
        ('socks5', 'SOCKS5'),
    ]

    url = models.CharField(max_length=500, unique=True)
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='http')
    provider = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    last_checked = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=50, blank=True) # e.g. "working", "failed", "slow"
    avg_response_ms = models.IntegerField(default=0)
    
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} ({self.url})"

    class Meta:
        verbose_name_plural = "Proxies"


class ProxySetting(models.Model):
    """
    Version 1.1 Single Active Proxy Setting.
    Stores the global proxy used by Playwright.
    """
    key = models.CharField(max_length=50, default='active_proxy', unique=True)
    value = models.CharField(max_length=500, help_text="http://user:pass@host:port")
    is_active = models.BooleanField(default=True)
    
    # Metadata for the Admin UI
    tested_at = models.DateTimeField(null=True, blank=True)
    is_working = models.BooleanField(default=False)
    response_ms = models.IntegerField(default=0)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_location = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Proxy: {self.value}"


class Package(models.Model):
    """Platform subscription tiers with resource limits."""
    name = models.CharField(max_length=100)
    price = models.CharField(max_length=50, help_text="e.g. $49/mo")
    lead_limit = models.IntegerField(default=2000, help_text="Monthly leads")
    grid_strategies = models.CharField(max_length=200, default="search,grid")
    features = models.TextField(blank=True, help_text="Comma-separated: Real-time scan, API access, etc.")
    description = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def grid_strategies_list(self):
        return [s.strip() for s in self.grid_strategies.split(',') if s.strip()]

    @property
    def features_list(self):
        return [f.strip() for f in self.features.split(',') if f.strip()]

class ServerPressure(models.Model):
    """Log entry for server load analysis."""
    timestamp = models.DateTimeField(auto_now_add=True)
    active_jobs = models.IntegerField(default=0)
    cpu_load = models.IntegerField(default=0) # We might still want to log it internally for pressure logic
    
    def __str__(self):
        return f"Pressure @ {self.timestamp}: {self.active_jobs} jobs"

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import connection

@receiver(pre_delete, sender=KeywordJob)
def clear_searched_cells(sender, instance, **kwargs):
    """
    Clears the 'jobs_searchedcell' ghost table before a KeywordJob is deleted.
    This prevents FOREIGN KEY constraint failures since this table isn't 
    formally managed by Django and won't normally cascade.
    """
    try:
        with connection.cursor() as cursor:
            # Safely check for table existence (SQLite syntax)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_searchedcell'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM jobs_searchedcell WHERE keyword_job_id = %s", [instance.id])
    except Exception as e:
        # We don't want to block deletion if the cleanup fails for minor reasons,
        # but the FK check will block it anyway if we don't succeed.
        # Log to terminal for oversight.
        print(f"DEBUG: Failed to clear searched cells for KJ {instance.id}: {e}")
