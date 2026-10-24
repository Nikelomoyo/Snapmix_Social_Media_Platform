import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'local-development-only-change-before-deployment')
if not DEBUG and SECRET_KEY.startswith('local-development'):
    raise RuntimeError('Set SECRET_KEY for deployment')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['daphne','django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','accounts.apps.AccountsConfig','posts','social','chat','notifications','missions']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','accounts.middleware.RateLimitMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','accounts.context.sidebar']}}]
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':os.getenv('SNAPMIX_DB_PATH', BASE_DIR/'db.sqlite3')}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
ASGI_APPLICATION = 'config.asgi.application'
REDIS_URL = os.getenv('REDIS_URL')
CHANNEL_LAYERS = {'default': {'BACKEND':'channels_redis.core.RedisChannelLayer','CONFIG':{'hosts':[REDIS_URL]}}} if REDIS_URL else {'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}}
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR/'static']
STATIC_ROOT = BASE_DIR/'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('SNAPMIX_MEDIA_ROOT', BASE_DIR/'media'))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/missions/'
LOGOUT_REDIRECT_URL = '/login/'
TIME_ZONE = 'Africa/Johannesburg'
USE_TZ = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 7 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

MISSION_MEDIA_ROOT = Path(os.getenv('SNAPMIX_MISSION_MEDIA_ROOT', BASE_DIR/'private_media'))
