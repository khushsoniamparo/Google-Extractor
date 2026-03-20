from django.db import models
from django.contrib.auth.models import User
from jobs.models import Package

class PaymentGatewaySettings(models.Model):
    """
    Store payment gateway keys that can be edited from the admin panel.
    """
    # Razorpay
    razorpay_key_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_key_secret = models.CharField(max_length=255, blank=True, null=True)
    
    # PayPal
    paypal_client_id = models.CharField(max_length=255, blank=True, null=True)
    paypal_client_secret = models.CharField(max_length=255, blank=True, null=True)
    paypal_mode = models.CharField(max_length=20, choices=[('sandbox', 'Sandbox'), ('live', 'Live')], default='sandbox')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment Settings ({'Active' if self.is_active else 'Inactive'})"

    class Meta:
        verbose_name = "Payment Gateway Setting"
        verbose_name_plural = "Payment Gateway Settings"

class RazorpayOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='razorpay_orders')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(
        max_length=20,
        choices=[('created', 'Created'), ('paid', 'Paid'), ('failed', 'Failed')],
        default='created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Razorpay Order {self.order_id} - {self.user.username}"

class PayPalOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paypal_orders')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    paypal_order_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(
        max_length=20,
        choices=[('created', 'Created'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PayPal Order {self.paypal_order_id} - {self.user.username}"

class Transaction(models.Model):
    payment_id = models.CharField(max_length=100, unique=True)
    # Allow linking to either Razorpay or PayPal
    order = models.OneToOneField(RazorpayOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='transaction')
    paypal_order = models.OneToOneField(PayPalOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='transaction')
    
    payment_method = models.CharField(max_length=20, choices=[('razorpay', 'Razorpay'), ('paypal', 'PayPal')], default='razorpay')
    signature = models.CharField(max_length=256, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        order_id = self.order.order_id if self.order else (self.paypal_order.paypal_order_id if self.paypal_order else "Unknown")
        return f"Transaction {self.payment_id} via {self.payment_method} for Order {order_id}"
