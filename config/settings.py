import os
from pathlib import Path

# ========================
# BASE DIR
# ========================
BASE_DIR = Path(__file__).resolve().parent.parent

# ========================
# SECURITY
# ========================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1').split(',') if h.strip()]


def _build_csrf_trusted_origins():
    origins = []
    for host in ALLOWED_HOSTS:
        if not host or host == '*':
            continue
        if host in ('127.0.0.1', 'localhost'):
            origins.extend([f'http://{host}:8000', f'http://{host}', f'http://{host}:8001'])
        else:
            origins.append(f'https://{host}')
            if not host.startswith('www.'):
                origins.append(f'https://www.{host}')
    extra = os.getenv('CSRF_TRUSTED_ORIGINS', '').strip()
    if extra:
        origins.extend([o.strip() for o in extra.split(',') if o.strip()])
    return list(dict.fromkeys(origins))


CSRF_TRUSTED_ORIGINS = _build_csrf_trusted_origins()

# Derriere Nginx / Caddy / Cloudflare : Django doit voir le HTTPS reel.
TRUST_PROXY = os.getenv('TRUST_PROXY', 'True') == 'True'
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = 'Lax'

# ========================
# APPLICATIONS
# ========================
INSTALLED_APPS = [
    'users.apps.UsersConfig',
    'articles.apps.ArticlesConfig',
    'lots.apps.LotsConfig',
    'caisse.apps.CaisseConfig',
    'ventes.apps.VentesConfig',
    'rapports.apps.RapportsConfig',
    'commandes.apps.CommandesConfig',
    'clients.apps.ClientsConfig',
    'fournisseurs.apps.FournisseursConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# ========================
# MIDDLEWARE
# ========================
MIDDLEWARE = [
    'config.middleware.MaxUploadSizeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.ClientPortalMiddleware',
    'users.middleware.EntrepriseSessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ========================
# URLS
# ========================
ROOT_URLCONF = 'config.urls'

# ========================
# TEMPLATES
# ========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.csrf',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.active_entreprise',
                'users.context_processors.staff_navigation',
                'users.context_processors.client_portal',
            ],
        },
    },
]

# ========================
# WSGI
# ========================
WSGI_APPLICATION = 'config.wsgi.application'

# ========================
# DATABASE (MySQL)
# ========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        }
    }
}

# ========================
# PASSWORD VALIDATION
# ========================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ========================
# INTERNATIONALIZATION
# ========================
LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Africa/Kinshasa'

USE_I18N = True
USE_TZ = True

# ========================
# STATIC FILES
# ========================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ========================
# MEDIA FILES
# ========================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

# Photos (articles, logos, preuves) : écrire sur disque tôt, et refuser
# un envoi énorme avant que le worker ne charge tout le corps en RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', str(1 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DATA_UPLOAD_MAX_MEMORY_SIZE', str(8 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.getenv('DATA_UPLOAD_MAX_NUMBER_FIELDS', '2000'))
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_MB', '20')) * 1024 * 1024
_upload_tmp = Path(os.getenv('FILE_UPLOAD_TEMP_DIR', str(BASE_DIR / 'tmp')))
_upload_tmp.mkdir(parents=True, exist_ok=True)
FILE_UPLOAD_TEMP_DIR = str(_upload_tmp)

# ========================
# DEFAULT PRIMARY KEY
# ========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Session : renouvellement à chaque requête ; durée longue tant que le navigateur est utilisé
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
