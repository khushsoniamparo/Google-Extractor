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

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bulk_jobs'
    )
    location = models.CharField(max_length=500)
    grid_size = models.IntegerField(default=8)
    status = models.CharField(
        max_length=20, choices=STATUS, default='pending'
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
