import razorpay
import requests
import json
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import RazorpayOrder, Transaction, PayPalOrder, PaymentGatewaySettings
from jobs.models import Package
from accounts.models import UserProfile


def get_payment_settings():
    return PaymentGatewaySettings.objects.filter(is_active=True).first()


class CreateRazorpayOrder(APIView):
    def post(self, request):
        package_id = request.data.get('package_id')
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get settings from DB
        db_settings = get_payment_settings()
        key_id = db_settings.razorpay_key_id if db_settings and db_settings.razorpay_key_id else settings.RAZORPAY_KEY_ID
        key_secret = db_settings.razorpay_key_secret if db_settings and db_settings.razorpay_key_secret else settings.RAZORPAY_KEY_SECRET

        if not key_id or not key_secret or 'placeholder' in key_id:
            return Response(
                {'error': 'Razorpay keys not configured. Please add them in the Admin Settings.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Parse price
        try:
            clean_price = "".join(filter(str.isdigit, package.price))
            price_in_usd = int(clean_price) if clean_price else 49
            price_in_inr = price_in_usd * 80
            razorpay_amount = price_in_inr * 100  # paise
        except Exception:
            razorpay_amount = 4900 * 100

        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            razorpay_order = client.order.create({
                "amount": razorpay_amount,
                "currency": "INR",
                "payment_capture": "1"
            })
        except Exception as e:
            return Response(
                {'error': f'Razorpay API error: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        order = RazorpayOrder.objects.create(
            user=request.user,
            package=package,
            order_id=razorpay_order['id'],
            amount=razorpay_amount / 100,
            status='created'
        )

        return Response({
            'order_id': order.order_id,
            'amount': razorpay_amount,
            'key_id': key_id,
            'currency': 'INR',
            'package_name': package.name
        }, status=status.HTTP_201_CREATED)


class VerifyRazorpayPayment(APIView):
    def post(self, request):
        payment_id = request.data.get('payment_id')
        order_id = request.data.get('order_id')
        signature = request.data.get('signature')

        db_settings = get_payment_settings()
        key_id = db_settings.razorpay_key_id if db_settings and db_settings.razorpay_key_id else settings.RAZORPAY_KEY_ID
        key_secret = db_settings.razorpay_key_secret if db_settings and db_settings.razorpay_key_secret else settings.RAZORPAY_KEY_SECRET

        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })

            with transaction.atomic():
                order = RazorpayOrder.objects.get(order_id=order_id)
                order.status = 'paid'
                order.save()

                Transaction.objects.create(
                    payment_id=payment_id,
                    order=order,
                    payment_method='razorpay',
                    signature=signature,
                    amount=order.amount
                )

                profile = UserProfile.objects.get(user=order.user)
                profile.package = order.package
                profile.searches_left = order.package.lead_limit
                profile.save()

            return Response({'status': 'Payment Successful'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'Payment verification failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


class CreatePayPalOrder(APIView):
    def post(self, request):
        package_id = request.data.get('package_id')
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

        db_settings = get_payment_settings()
        if not db_settings or not db_settings.paypal_client_id:
            return Response({'error': 'PayPal not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        client_id = db_settings.paypal_client_id
        secret = db_settings.paypal_client_secret
        mode = db_settings.paypal_mode
        base_url = "https://api-m.sandbox.paypal.com" if mode == 'sandbox' else "https://api-m.paypal.com"

        # Get Access Token
        auth_res = requests.post(
            f"{base_url}/v1/oauth2/token",
            auth=(client_id, secret),
            data={"grant_type": "client_credentials"}
        )
        if auth_res.status_code != 200:
            return Response({'error': 'PayPal Auth Failed'}, status=status.HTTP_502_BAD_GATEWAY)
        
        access_token = auth_res.json().get('access_token')

        # Parse price
        clean_price = "".join(filter(str.isdigit, package.price))
        amount_usd = clean_price if clean_price else "49.00"

        # Create Order
        order_res = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": amount_usd
                    },
                    "description": f"Subscription for {package.name}"
                }]
            }
        )

        if order_res.status_code not in [200, 201]:
            return Response({'error': 'PayPal Order Creation Failed'}, status=status.HTTP_502_BAD_GATEWAY)

        paypal_order_data = order_res.json()
        
        PayPalOrder.objects.create(
            user=request.user,
            package=package,
            paypal_order_id=paypal_order_data['id'],
            amount=amount_usd,
            status='created'
        )

        return Response({
            'order_id': paypal_order_data['id'],
            'client_id': client_id
        }, status=status.HTTP_201_CREATED)


class CapturePayPalOrder(APIView):
    def post(self, request):
        order_id = request.data.get('order_id')
        
        db_settings = get_payment_settings()
        client_id = db_settings.paypal_client_id
        secret = db_settings.paypal_client_secret
        mode = db_settings.paypal_mode
        base_url = "https://api-m.sandbox.paypal.com" if mode == 'sandbox' else "https://api-m.paypal.com"

        # Get Access Token
        auth_res = requests.post(f"{base_url}/v1/oauth2/token", auth=(client_id, secret), data={"grant_type": "client_credentials"})
        access_token = auth_res.json().get('access_token')

        # Capture
        capture_res = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        )

        if capture_res.status_code == 201:
            data = capture_res.json()
            if data.get('status') == 'COMPLETED':
                with transaction.atomic():
                    order = PayPalOrder.objects.get(paypal_order_id=order_id)
                    order.status = 'completed'
                    order.save()

                    Transaction.objects.create(
                        payment_id=data['id'],
                        paypal_order=order,
                        payment_method='paypal',
                        amount=order.amount
                    )

                    profile = UserProfile.objects.get(user=order.user)
                    profile.package = order.package
                    profile.searches_left = order.package.lead_limit
                    profile.save()

                return Response({'status': 'Payment Successful'}, status=status.HTTP_200_OK)
        
        return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)
