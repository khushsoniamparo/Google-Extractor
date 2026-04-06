from django.contrib import admin
from .models import BulkJob, KeywordJob, Place, Proxy, Package

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'tier_badge', 'lead_limit', 'grid_cell_limit', 'is_featured')
    list_editable = ('is_featured', 'tier_badge')
    search_fields = ('name',)
    
    fieldsets = (
        ('General Information', {
            'fields': (('name', 'price'), 'tier_badge', 'description', 'is_featured')
        }),
        ('Resource Limits', {
            'fields': ('lead_limit', 'search_limit', 'grid_cell_limit')
        }),
        ('Strategic Access', {
            'fields': ('grid_strategies', 'allowed_search_types'),
            'description': 'Specify allowed strategies (fast, detailed, deep, ultra) and search types (city, state_country) separated by commas.'
        }),
        ('Marketing & Styling', {
            'fields': ('features',),
            'description': 'Comma separated features to show on the landing page.'
        }),
    )

    def has_delete_permission(self, request, obj=None):
        """
        Only allow deletion from the individual edit page (where obj is provided),
        not from the main list view (where obj is None).
        """
        if obj is None:
            return False
        return super().has_delete_permission(request, obj)

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
