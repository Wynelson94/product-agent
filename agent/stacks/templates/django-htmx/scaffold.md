# Django + HTMX Scaffolding

## Initial Setup

```bash
# Create project directory and virtual environment
mkdir src && cd src
python3 -m venv venv
source venv/bin/activate

# Install Django and core dependencies
pip install django django-htmx django-allauth django-crispy-forms crispy-tailwind
pip install psycopg2-binary django-environ whitenoise gunicorn
pip install celery redis django-celery-beat  # Background jobs

# Create Django project
django-admin startproject config .
python manage.py startapp core

# Install Tailwind CSS via django-tailwind
pip install django-tailwind
python manage.py tailwind install
```

## Directory Structure

```
src/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── core/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/       # HTMX partial templates
│   │   └── pages/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_forms.py
├── templates/
│   ├── base.html
│   ├── account/              # django-allauth templates
│   └── components/
├── static/
├── manage.py
├── requirements.txt
├── Procfile
└── .env.example
```

## Environment Template

Create `.env.example`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/app_dev
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
REDIS_URL=redis://localhost:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Settings Configuration

Key settings in `config/settings.py`:

```python
import environ

env = environ.Env()
environ.Env.read_env()

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_htmx",
    "allauth",
    "allauth.account",
    "crispy_forms",
    "crispy_tailwind",
    # Local
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

DATABASES = {
    "default": env.db("DATABASE_URL")
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"
STATIC_URL = "static/"
STATIC_ROOT = "staticfiles/"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

## Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```
