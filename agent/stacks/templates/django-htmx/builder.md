# Django + HTMX Build Process

## Steps

1. Create project: `django-admin startproject config . && python manage.py startapp core`
2. Install dependencies: `pip install django django-htmx django-allauth django-crispy-forms crispy-tailwind psycopg2-binary django-environ whitenoise gunicorn`
3. Configure settings.py with django-environ, HTMX middleware, allauth, crispy-tailwind
4. **Install DESIGN.md dependencies**: Read DESIGN.md and `pip install` every library it references
5. Create models from DESIGN.md data model
6. Run `python manage.py makemigrations && python manage.py migrate`
7. Create admin.py registrations for all models
8. Create views — use `request.htmx` to return partial templates for HTMX requests
9. Create base.html with HTMX script, Tailwind CDN, CSRF token header
10. Create page templates and HTMX partial components
11. Create forms with crispy-forms
12. Configure URL routing
13. **Setup Tests**: Create test files in core/tests/
14. Run `python manage.py test` to verify

## Test Infrastructure

```python
# core/tests/test_views.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()

class ItemViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@example.com", "password")
        self.client.login(username="testuser", password="password")

    def test_item_list(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
```
