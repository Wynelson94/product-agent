# Django + HTMX Deployment (Railway)

## Pre-Deployment Checklist

1. All tests pass: `python manage.py test`
2. Static files collected: `python manage.py collectstatic --noinput`
3. `requirements.txt` up to date: `pip freeze > requirements.txt`
4. `DEBUG = False` in production settings
5. `ALLOWED_HOSTS` configured
6. `SECRET_KEY` uses environment variable (not hardcoded)

## Procfile

```
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT
worker: celery -A config worker -l info
release: python manage.py migrate
```

## Railway Deployment

### 1. Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### 2. Create Project

```bash
railway init
railway add --plugin postgresql
railway add --plugin redis  # If using Celery
```

### 3. Configure Environment Variables

```bash
railway variables set DJANGO_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
railway variables set DJANGO_DEBUG=False
railway variables set ALLOWED_HOSTS=".railway.app"
```

DATABASE_URL and REDIS_URL are auto-provisioned by Railway plugins.

### 4. Deploy

```bash
railway up
```

### 5. Run Migrations

```bash
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

## Verify Deployment

```bash
# Check health
curl -I https://[your-app].railway.app

# Check admin
# Visit https://[your-app].railway.app/admin/
```

## Alternative: Vercel with Services

Django can deploy to Vercel using the Services API:

```json
{
  "experimentalServices": {
    "api": {
      "entrypoint": "src/config/wsgi.py",
      "routePrefix": "/"
    }
  }
}
```

Requires Python runtime. Set Framework Preset to "Services" in Vercel dashboard.

## Troubleshooting

### Static files not loading
- Verify `whitenoise` is in MIDDLEWARE
- Run `python manage.py collectstatic --noinput`
- Check `STATIC_ROOT` is set

### Database connection errors
- Verify `DATABASE_URL` environment variable is set
- Check PostgreSQL plugin is attached in Railway

### CSRF errors with HTMX
- Ensure base template includes `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on body
- Verify `CsrfViewMiddleware` is in MIDDLEWARE
