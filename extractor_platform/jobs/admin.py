from django.contrib import admin
from .models import BulkJob, KeywordJob, Place, Proxy

@admin.register(Proxy)
class ProxyAdmin(admin.ModelAdmin):
    list_display = ('url', 'provider', 'is_active', 'last_status', 'avg_response_ms', 'success_rate')
    list_filter = ('is_active', 'last_status', 'protocol', 'provider')
    search_fields = ('url', 'provider')
    actions = ['test_proxies', 'toggle_active']

    def test_proxies(self, request, queryset):
        # Implementation for testing will come later
        self.message_user(request, f"Started testing {queryset.count()} proxies.")
    test_proxies.short_description = "Test selected proxies"

    def toggle_active(self, request, queryset):
        for proxy in queryset:
            proxy.is_active = not proxy.is_active
            proxy.save()
    toggle_active.short_description = "Toggle active status"

@admin.register(BulkJob)
class BulkJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'location', 'grid_size', 'strategy', 'status', 'created_at')
    list_filter = ('status', 'strategy', 'created_at')
    search_fields = ('location', 'user__username')
    readonly_fields = ('created_at', 'completed_at')

@admin.register(KeywordJob)
class KeywordJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'bulk_job', 'keyword', 'status', 'total_extracted', 'progress_percent', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('keyword', 'bulk_job__location')

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'state', 'phone', 'scraped_at')
    list_filter = ('category', 'city', 'state', 'scraped_at')
    search_fields = ('name', 'city', 'phone', 'place_id')
