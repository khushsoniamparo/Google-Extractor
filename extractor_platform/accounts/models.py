from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    
    # Subscription & Limits
    package = models.ForeignKey('jobs.Package', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    searches_left = models.IntegerField(default=5, help_text="Number of searches remaining")
    leads_scraped = models.IntegerField(default=0, help_text="Total leads scraped across all time")

    def __str__(self):
        return f"{self.user.username} - {self.phone}"

class UserOTP(models.Model):
    phone = models.CharField(max_length=255, help_text="Email or Phone number")
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.phone} - {self.otp}"
