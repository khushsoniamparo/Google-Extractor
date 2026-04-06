from django.urls import path
from django.contrib.auth import views as auth_views
from .views import get_profile, update_profile, send_otp, verify_otp, register_with_otp, firebase_login, traditional_login

urlpatterns = [
    path('profile/', get_profile, name='get_profile'),
    path('profile/update/', update_profile, name='update_profile'),
    path('send-otp/', send_otp, name='send_otp'),
    path('verify-otp/', verify_otp, name='verify_otp'),
    path('register/', register_with_otp, name='register_with_otp'),
    path('firebase-login/', firebase_login, name='firebase_login'),
    path('login/', traditional_login, name='traditional_login'),
    
    # Password Reset Flow (using Django built-ins)
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
]
