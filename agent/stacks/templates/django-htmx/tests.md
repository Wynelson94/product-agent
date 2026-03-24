# Django + HTMX Test Patterns

## Test Framework

Django uses its built-in test runner (`python manage.py test`). Tests extend `django.test.TestCase`.

## Model Tests

```python
# core/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Item

User = get_user_model()

class ItemModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@example.com", "pass")

    def test_item_creation(self):
        item = Item.objects.create(user=self.user, name="Test Item")
        self.assertEqual(str(item), "Test Item")
        self.assertFalse(item.is_completed)

    def test_item_ordering(self):
        Item.objects.create(user=self.user, name="First")
        Item.objects.create(user=self.user, name="Second")
        items = list(Item.objects.all())
        self.assertEqual(items[0].name, "Second")  # Newest first
```

## View Tests

```python
# core/tests/test_views.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from core.models import Item

User = get_user_model()

class ItemViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@example.com", "pass")
        self.client.login(username="testuser", password="pass")

    def test_item_list_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/items.html")

    def test_item_list_htmx(self):
        response = self.client.get("/", HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "components/item_list.html")

    def test_item_create(self):
        response = self.client.post("/create/", {"name": "New Item", "description": ""})
        self.assertEqual(Item.objects.count(), 1)

    def test_item_delete(self):
        item = Item.objects.create(user=self.user, name="Delete Me")
        response = self.client.delete(f"/{item.pk}/delete/")
        self.assertEqual(Item.objects.count(), 0)

    def test_unauthenticated_redirect(self):
        self.client.logout()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
```

## Form Tests

```python
# core/tests/test_forms.py
from django.test import TestCase
from core.forms import ItemForm

class ItemFormTests(TestCase):
    def test_valid_form(self):
        form = ItemForm(data={"name": "Test", "description": "Desc"})
        self.assertTrue(form.is_valid())

    def test_empty_name_invalid(self):
        form = ItemForm(data={"name": "", "description": ""})
        self.assertFalse(form.is_valid())
```

## Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core

# Run with verbosity
python manage.py test -v 2

# Run specific test class
python manage.py test core.tests.test_views.ItemViewTests
```
