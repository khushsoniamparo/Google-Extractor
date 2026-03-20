from django.contrib import admin
from .models import RazorpayOrder, Transaction

@admin.register(RazorpayOrder)
class RazorpayOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'package', 'amount', 'status', 'created_at')
    list_filter = ('status', 'package')
    search_fields = ('order_id', 'user__username')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'order', 'amount', 'created_at')
    search_fields = ('payment_id', 'order__order_id')
