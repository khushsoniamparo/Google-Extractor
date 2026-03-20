# core/settings.py
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'accounts',
    'jobs',
    'billing',
]

# Razorpay Configuration
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='rzp_test_placeholder')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='secret_placeholder')
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration for Intel Hub OTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
# Note: User provided 'gmial.com' in request, applying as requested. 
# If connection fails, check for typo.
EMAIL_HOST_USER = 'sonikhush004@gmail.com'
EMAIL_HOST_PASSWORD = 'oavv abcy dhvt lhhv'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ADMIN_HUB_EMAIL = 'sonikhush004@gmail.com'
ADMIN_HUB_PASSWORD = 'OMISCIENT_ROOT_HUB' # High-level access secret
