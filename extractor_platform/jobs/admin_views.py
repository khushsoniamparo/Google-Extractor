from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .models import BulkJob, KeywordJob, Place, ProxySetting, Package, ServerPressure
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from accounts.models import UserProfile
from billing.models import Transaction, RazorpayOrder, PayPalOrder, PaymentGatewaySettings
import psutil
import os
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from scraper.proxy_pool import PROXIES
from scraper.proxy_logic import test_proxy_connection
from django.core.mail import send_mail
from functools import wraps
from django.conf import settings
import random
import threading
from django.core.cache import cache

def admin_hub_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get('admin_hub_verified'):
            return redirect('admin_hub_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_hub_login(request):
    """Ensures multi-stage login starts at Step 1 for fresh entries."""
    error = None
    
    if request.method == 'POST':
        step = request.session.get('admin_login_step', 1)
        if step == 1:
            # Stage 1: Email Identification
            email = request.POST.get('email', '').strip()
            if email == settings.ADMIN_HUB_EMAIL:
                otp = random.randint(100000, 999999)
                pwd = settings.ADMIN_HUB_PASSWORD # For inclusion in email
                request.session['admin_otp'] = otp
                request.session['admin_login_step'] = 2
                
                # Async Professional HTML Email Dispatch
                def _send_async():
                    html_content = f"""
                    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1a202c;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #2d3748; font-size: 24px; font-weight: 800; letter-spacing: -0.025em; margin: 0;">7Shouters<span style="color: #f59e0b;">.</span>Admin</h1>
                            <p style="color: #718096; font-size: 14px; margin-top: 8px;">Secure Access Verification Protocol</p>
                        </div>
                        
                        <div style="background-color: #f7fafc; border-radius: 8px; padding: 24px; margin-bottom: 24px;">
                            <p style="color: #4a5568; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">Access Token</p>
                            <div style="font-family: 'Courier New', Courier, monospace; font-size: 32px; font-weight: 800; color: #2d3748; letter-spacing: 0.25em; text-align: center;">{otp}</div>
                        </div>

                        <div style="background-color: #fffaf0; border: 1px solid #fbd38d; border-radius: 8px; padding: 24px;">
                            <p style="color: #c05621; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">Master Clearance Secret</p>
                            <code style="font-size: 16px; font-weight: 700; color: #744210;">{pwd}</code>
                        </div>

                        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #edf2f7; text-align: center;">
                            <p style="color: #a0aec0; font-size: 12px; line-height: 1.6;">
                                This is a secure automated dispatch. If you did not initiate this request, please investigate terminal integrity immediately.
                            </p>
                        </div>
                    </div>
                    """
                    try:
                        send_mail(
                            'Administrative Clearance Dispatch',
                            f'Your Token: {otp} | Your Clearance Secret: {pwd}',
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=False,
                            html_message=html_content
                        )
                    except Exception as e:
                        print(f"SMTP Error: {e}")
                
                threading.Thread(target=_send_async, daemon=True).start()
                print(f"[OMEGA_OTP]: {otp}")
                
                return render(request, 'admin/intel_login.html', {'step': 2, 'email': email})
            else:
                error = "Access Denied: Unauthorized Identity"
                return render(request, 'admin/intel_login.html', {'step': 1, 'error': error})
                
        elif step == 2:
            # Stage 2: OTP and Password Verification
            otp_input = request.POST.get('otp', '').strip()
            pwd_input = request.POST.get('password', '').strip()
            saved_otp = request.session.get('admin_otp')
            
            # Robust comparison (strip spaces, ensure string type)
            if saved_otp and str(otp_input) == str(saved_otp) and pwd_input == settings.ADMIN_HUB_PASSWORD:
                request.session['admin_hub_verified'] = True
                request.session.pop('admin_otp', None)
                request.session.pop('admin_login_step', None)
                request.session.set_expiry(0) 
                return redirect('admin_dashboard')
            else:
                error = "Verification Failed: Invalid Token or Password"
                print(f"DEBUG_LOGIN: InputOTP={otp_input}, SavedOTP={saved_otp}, PwdMatch={pwd_input == settings.ADMIN_HUB_PASSWORD}")
                return render(request, 'admin/intel_login.html', {'step': 2, 'error': error})

    # GET Request: Always start at Step 1 to ensure email identification
    request.session['admin_login_step'] = 1
    return render(request, 'admin/intel_login.html', {'step': 1})

def admin_hub_logout(request):
    """Terminate administrative session."""
    request.session.flush()
    return redirect('admin_hub_login')

@staff_member_required
@admin_hub_required
def admin_dashboard(request):
    from .models import ServerPressure
    
    # 1. Subject Load Metrics (Cached for 60s to prevent DB thrashing)
    stats = cache.get('admin_dashboard_stats')
    if not stats:
        user_count = User.objects.count()
        total_searches = BulkJob.objects.count()
        total_results = KeywordJob.objects.aggregate(Sum('total_extracted'))['total_extracted__sum'] or 0
        active_ops = BulkJob.objects.filter(status='running').count()
        stats = {
            'users': user_count,
            'searches': total_searches,
            'results': total_results,
            'active_ops': active_ops,
        }
        cache.set('admin_dashboard_stats', stats, 60)
    else:
        active_ops = stats['active_ops']

    # Snapshot pressure (Non-cached)
    ServerPressure.objects.create(active_jobs=active_ops)
    
    # 2. Server Pressure History (Lightweight query)
    pressure_points = ServerPressure.objects.only('active_jobs', 'timestamp').order_by('-timestamp')[:15]
    pressure_data = [p.active_jobs for p in reversed(pressure_points)]
    pressure_labels = [p.timestamp.strftime('%H:%M') for p in reversed(pressure_points)]
    
    context = {
        'metrics': stats,
        'pressure': {
            'values': json.dumps(pressure_data),
            'labels': json.dumps(pressure_labels),
        },
        'admin': {
            'username': request.user.username,
            'terminal_ip': request.META.get('REMOTE_ADDR'),
        },
        'now': timezone.now()
    }
    return render(request, 'admin/dashboard.html', context)

@staff_member_required
@admin_hub_required
def live_monitor(request):
    active_bulk_jobs = BulkJob.objects.filter(status='running').prefetch_related('keyword_jobs')
    
    # Calculate system throughput (results last hour)
    one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
    results_last_hour = Place.objects.filter(scraped_at__gte=one_hour_ago).count()
    
    context = {
        'active_jobs': active_bulk_jobs,
        'results_last_hour': results_last_hour,
        'now': timezone.now()
    }
    return render(request, 'admin/live_monitor.html', context)


@staff_member_required
@admin_hub_required
def proxy_settings(request):
    """
    V1.1 Admin Page: Manage single active proxy.
    """
    setting, _ = ProxySetting.objects.get_or_create(key='active_proxy')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save':
            setting.value = request.POST.get('proxy_url', '').strip()
            setting.is_active = 'is_active' in request.POST
            setting.save()
        elif action == 'remove':
            setting.value = ''
            setting.is_active = False
            setting.is_working = False
            setting.last_ip = ''
            setting.last_location = ''
            setting.response_ms = 0
            setting.tested_at = None
            setting.save()
            
    context = {
        'setting': setting,
        'now': timezone.now()
    }
    return render(request, 'admin/proxy_settings.html', context)


@staff_member_required
@admin_hub_required
@require_POST
async def test_proxy_ajax(request):
    """
    AJAX endpoint to test the proxy URL.
    """
    data = json.loads(request.body)
    url = data.get('url', '').strip()
    
    if not url:
        return JsonResponse({'success': False, 'error': 'No URL provided'})
        
    test_results = await test_proxy_connection(url)
    
    # Update the setting record if this is the active URL
    setting = await ProxySetting.objects.filter(key='active_proxy').afirst()
    if setting and setting.value == url:
        setting.is_working = test_results['success']
        setting.response_ms = test_results['response_ms']
        setting.last_ip = test_results['ip']
        setting.last_location = test_results['location']
        setting.tested_at = timezone.now()
        await setting.asave()
        
    return JsonResponse(test_results)


@staff_member_required
@admin_hub_required
def user_management(request):
    """List all users with optimized pagination and counting."""
    from django.core.paginator import Paginator
    
    # Include profile resource fields
    users_list = User.objects.all().select_related('profile', 'profile__package').only(
        'username', 'date_joined', 'is_active', 'email',
        'profile__phone', 'profile__is_verified', 'profile__package__name',
        'profile__searches_left', 'profile__leads_scraped'
    ).order_by('-date_joined')
    
    paginator = Paginator(users_list, 20) # 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Inject stats manually for current page to avoid heavy join on all users
    for user in page_obj:
        user.total_jobs = BulkJob.objects.filter(user=user).count()
        # total_extracted from all jobs
        user.total_extracted = KeywordJob.objects.filter(bulk_job__user=user).aggregate(
            Sum('total_extracted'))['total_extracted__sum'] or 0

    packages = Package.objects.all().order_by('price')
    
    context = {
        'page_obj': page_obj,
        'packages': packages,
        'now': timezone.now()
    }
    return render(request, 'admin/user_management.html', context)


@staff_member_required
@admin_hub_required
@require_POST
def assign_package(request, user_id):
    """Manually assign a subscription package to a user."""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    try:
        data = json.loads(request.body)
        package_id = data.get('package_id')
        
        if not package_id:
            # Revert to default
            profile.package = None
            profile.searches_left = 5
            profile.save()
            return JsonResponse({'success': True, 'msg': f'Subscription removed for {user.username}'})
            
        package = get_object_or_404(Package, id=package_id)
        profile.package = package
        profile.searches_left = package.lead_limit
        profile.save()
        
        return JsonResponse({'success': True, 'msg': f'Package "{package.name}" assigned to {user.username}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@admin_hub_required
@require_POST
def update_credits(request, user_id):
    """Manually update the search credit balance for a user."""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    try:
        data = json.loads(request.body)
        new_credits = data.get('credits')
        
        if new_credits is None:
            return JsonResponse({'error': 'Credits value required'}, status=400)
            
        profile.searches_left = int(new_credits)
        profile.save()
        
        return JsonResponse({'success': True, 'msg': f'Credits updated to {profile.searches_left} for {user.username}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@admin_hub_required
@require_POST
def update_user_details(request, user_id):
    """Update basic user information (Email, Phone, Username)."""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    try:
        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        phone = data.get('phone')
        
        if username:
            # Check if username exists
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                return JsonResponse({'error': 'Username already taken'}, status=400)
            user.username = username
            
        if email:
            user.email = email
            
        user.save()
        
        if phone:
            profile.phone = phone
            profile.save()
            
        return JsonResponse({'success': True, 'msg': f'Account details updated for {user.username}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@admin_hub_required
@require_POST
def toggle_user_status(request, user_id):
    """Ban/Unban user."""
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        return JsonResponse({'error': 'Cannot modify superuser'}, status=403)
    
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({'success': True, 'is_active': user.is_active})


@staff_member_required
@admin_hub_required
@require_POST
def reset_password(request, user_id):
    """Set a custom password for the user."""
    user = get_object_or_404(User, id=user_id)
    
    # Allow superuser reset but add warning check later
    import json
    try:
        data = json.loads(request.body)
        new_password = data.get('password')
    except:
        new_password = request.POST.get('password')

    if not new_password:
        return JsonResponse({'error': 'New password is required'}, status=400)
    
    user.set_password(new_password)
    user.save()
    return JsonResponse({'success': True, 'msg': f'Password updated successfully to {new_password} for {user.username}'})


@staff_member_required
@admin_hub_required
@require_POST
def delete_user(request, user_id):
    """Deep purge of a user account and all strategic/metadata footprints."""
    from django.contrib.admin.models import LogEntry
    from django.db import transaction, connection
    
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser and request.user.id == user.id:
        return JsonResponse({'error': 'Cannot purge your own account'}, status=403)
    
    try:
        with transaction.atomic():
            # 0. Ghost Table Cleanup (FK blockers not defined in Django)
            with connection.cursor() as cursor:
                # SQLite PRAGMA check for safety
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_searchedcell'")
                if cursor.fetchone():
                    cursor.execute("""
                        DELETE FROM jobs_searchedcell 
                        WHERE keyword_job_id IN (
                            SELECT kj.id FROM jobs_keywordjob kj
                            JOIN jobs_bulkjob bj ON kj.bulk_job_id = bj.id
                            WHERE bj.user_id = %s
                        )
                    """, [user.id])

            # 1. Clear Administrative Audit Logs (Common Hidden FK)
            LogEntry.objects.filter(user_id=user.id).delete()
            
            # 2. Clear Operational Footprints (Deep Cascade)
            # We clear these explicitly to ensure no constraint issues with Place results
            Place.objects.filter(keyword_job__bulk_job__user=user).delete()
            KeywordJob.objects.filter(bulk_job__user=user).delete()
            BulkJob.objects.filter(user=user).delete()

            # 3. Clear Billing Footprints (Added to support new payment methods)
            Transaction.objects.filter(order__user=user).delete()
            Transaction.objects.filter(paypal_order__user=user).delete()
            RazorpayOrder.objects.filter(user=user).delete()
            PayPalOrder.objects.filter(user=user).delete()
            
            # 4. Clear verification metadata
            if hasattr(user, 'profile'):
                user.profile.delete()
                
            # 5. Final Platform Removal
            user.delete()
            
        return JsonResponse({'success': True})
    except Exception as e:
        err_str = str(e)
        # Log to terminal for administrative audit
        print(f"CRITICAL PURGE ERROR [UID:{user_id}]: {err_str}")
        
        # User-friendly explanation for common database errors
        if "FOREIGN KEY" in err_str.upper():
            friendly_err = "DATA INTEGRITY COLLISION: This subject has associated footprints that cannot be auto-purged. Ensure all active jobs for this user are terminated first."
        else:
            friendly_err = f"Purge protocol failed: {err_str}"

        return JsonResponse({
            'error': friendly_err,
            'detail': 'Administrative override may be required for deep system cleanup.'
        }, status=500)


@staff_member_required
@admin_hub_required
def package_management(request):
    """Manage subscription packages."""
    if request.method == 'POST':
        action = request.POST.get('action')
        pkg_id = request.POST.get('pkg_id')
        
        if action == 'save':
            name = request.POST.get('name')
            price = request.POST.get('price')
            limit = request.POST.get('lead_limit')
            strategies = request.POST.get('grid_strategies')
            features = request.POST.get('features', '')
            is_featured = request.POST.get('is_featured') == 'on'
            
            if pkg_id:
                pkg = get_object_or_404(Package, id=pkg_id)
            else:
                pkg = Package()
                
            pkg.name = name
            pkg.price = price
            pkg.lead_limit = limit
            pkg.grid_strategies = strategies
            pkg.features = features
            pkg.is_featured = is_featured
            pkg.save()
            return redirect('package_management')
            
        elif action == 'delete':
            pkg = get_object_or_404(Package, id=pkg_id)
            pkg.delete()
            return redirect('package_management')

    packages = Package.objects.all().order_by('lead_limit')
    return render(request, 'admin/package_management.html', {'packages': packages})



@staff_member_required
@admin_hub_required
@require_POST
def remove_subscription(request, user_id):
    """Purge a user's subscription package and reset credits."""
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    profile.package = None
    profile.searches_left = 5 # Back to default
    profile.save()
    
    return JsonResponse({'success': True, 'msg': 'Subscription purged successfully'})

@staff_member_required
@admin_hub_required
def user_activity(request, user_id):
    """See detailed activity for a specific user."""
    target_user = get_object_or_404(User, id=user_id)
    # Robustly get or create profile
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    
    jobs = BulkJob.objects.filter(user=target_user).prefetch_related('keyword_jobs').order_by('-created_at')
    
    packages = Package.objects.all().order_by('price')
    
    context = {
        'target_user': target_user,
        'profile': profile,
        'jobs': jobs,
        'packages': packages,
        'job_stats': {
            'total': jobs.count(),
            'extracted': sum(j.total_extracted for j in jobs),
            'searches_left': profile.searches_left,
            'package_name': profile.package.name if profile.package else "No Package",
            'lead_limit': profile.package.lead_limit if profile.package else 0
        },
        'now': timezone.now()
    }
    return render(request, 'admin/user_activity.html', context)

@staff_member_required
@admin_hub_required
def view_keyword_results(request, keyword_job_id):
    """View extracted places for a specific keyword in the admin panel."""
    kj = get_object_or_404(KeywordJob.objects.select_related('bulk_job', 'bulk_job__user'), id=keyword_job_id)
    places = kj.places.all().order_by('name')
    
    context = {
        'kj': kj,
        'places': places,
        'now': timezone.now()
    }
    return render(request, 'admin/keyword_results.html', context)


@staff_member_required
@admin_hub_required
def payment_management(request):
    """View all payments and transactions."""
    transactions = Transaction.objects.all().select_related(
        'order', 'paypal_order', 'order__user', 'paypal_order__user'
    ).order_by('-created_at')
    
    razorpay_orders = RazorpayOrder.objects.all().select_related('user', 'package').order_by('-created_at')
    paypal_orders = PayPalOrder.objects.all().select_related('user', 'package').order_by('-created_at')
    
    context = {
        'transactions': transactions,
        'razorpay_orders': razorpay_orders,
        'paypal_orders': paypal_orders,
        'now': timezone.now()
    }
    return render(request, 'admin/payment_management.html', context)


@staff_member_required
@admin_hub_required
def payment_settings(request):
    """Manage payment gateway keys."""
    # Use get or create for the default active record.
    # In a production app, you might want to manage multiple configurations.
    settings_obj = PaymentGatewaySettings.objects.filter(is_active=True).first()
    if not settings_obj:
        settings_obj = PaymentGatewaySettings.objects.create(is_active=True)
    
    if request.method == 'POST':
        settings_obj.razorpay_key_id = request.POST.get('razorpay_key_id', '').strip()
        settings_obj.razorpay_key_secret = request.POST.get('razorpay_key_secret', '').strip()
        settings_obj.paypal_client_id = request.POST.get('paypal_client_id', '').strip()
        settings_obj.paypal_client_secret = request.POST.get('paypal_client_secret', '').strip()
        settings_obj.paypal_mode = request.POST.get('paypal_mode', 'sandbox')
        settings_obj.save()
        return redirect('payment_settings')
        
    context = {
        'settings': settings_obj,
        'now': timezone.now()
    }
    return render(request, 'admin/payment_settings.html', context)
