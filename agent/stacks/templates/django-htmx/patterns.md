# Django + HTMX Code Patterns

## HTMX Partial Views

HTMX allows server-rendered interactivity without writing JavaScript.
Views return HTML fragments that replace parts of the page.

### View Pattern

```python
# core/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django_htmx.http import HttpResponseClientRedirect

@login_required
def item_list(request):
    items = request.user.items.all()
    if request.htmx:
        return render(request, "components/item_list.html", {"items": items})
    return render(request, "pages/items.html", {"items": items})

@login_required
def item_create(request):
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            items = request.user.items.all()
            return render(request, "components/item_list.html", {"items": items})
    else:
        form = ItemForm()
    return render(request, "components/item_form.html", {"form": form})

@login_required
def item_delete(request, pk):
    item = get_object_or_404(request.user.items, pk=pk)
    item.delete()
    items = request.user.items.all()
    return render(request, "components/item_list.html", {"items": items})
```

### HTMX Template Pattern

```html
<!-- templates/pages/items.html -->
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto p-6">
  <h1 class="text-2xl font-bold mb-4">Items</h1>

  <button hx-get="{% url 'item-create' %}" hx-target="#form-container"
          class="px-4 py-2 bg-zinc-800 text-white rounded">
    Add Item
  </button>

  <div id="form-container"></div>

  <div id="item-list" class="mt-6">
    {% include "components/item_list.html" %}
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/components/item_list.html -->
{% for item in items %}
<div class="flex items-center justify-between p-3 border-b border-zinc-200">
  <span>{{ item.name }}</span>
  <button hx-delete="{% url 'item-delete' item.pk %}"
          hx-target="#item-list" hx-swap="innerHTML"
          hx-confirm="Delete this item?"
          class="text-red-500 text-sm">Delete</button>
</div>
{% empty %}
<p class="text-zinc-500 p-3">No items yet.</p>
{% endfor %}
```

## Base Template with HTMX + Tailwind

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}App{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% include "components/navbar.html" %}
  <main class="container mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

## Models

```python
# core/models.py
from django.db import models
from django.conf import settings

class TimestampedModel(models.Model):
    """Base model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Item(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
```

## Forms with Crispy

```python
# core/forms.py
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Save"))
```

## URL Configuration

```python
# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.item_list, name="item-list"),
    path("create/", views.item_create, name="item-create"),
    path("<int:pk>/delete/", views.item_delete, name="item-delete"),
]
```

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("core.urls")),
]
```

## Admin Configuration

```python
# core/admin.py
from django.contrib import admin
from .models import Item

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "is_completed", "created_at"]
    list_filter = ["is_completed", "created_at"]
    search_fields = ["name", "description"]
```

## Background Tasks (Celery)

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```python
# core/tasks.py
from celery import shared_task

@shared_task
def send_notification(user_id, message):
    # Background task logic
    pass
```
