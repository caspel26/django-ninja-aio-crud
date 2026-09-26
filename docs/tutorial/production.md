---
type: tutorial
step: 7
steps: 7
title: Go to production
description: Check, test and deploy your API.
---

# Go to production

In this last step you check the configuration, write tests and get the API
ready to deploy.

## Check the configuration

Django validates every `Schemas` class. Run the checks in your CI:

```bash
python manage.py check
python manage.py check --deploy
```

A misspelled field, a field listed twice or an option on the wrong schema kind
fails the check with a clear message, like `ninja_aio.E003`.

## Match the server

Choose the execution mode that matches how you run Django:

| Server | Examples | Use |
| --- | --- | --- |
| ASGI | Uvicorn, Daphne, Granian | `execution_mode = "async"` (default) |
| WSGI | Gunicorn, uWSGI, mod_wsgi | `execution_mode = "sync"` |

Both modes work on both servers, but matching them avoids switching between
sync and async code on every request. See [deployment](../deployment.md) for
server settings.

## Write tests

Test the endpoints with Django's test client:

=== "Sync"

    ```python title="blog/tests.py"
    from django.test import TestCase

    from .models import Article, Category


    class ArticleAPITests(TestCase):
        def setUp(self):
            self.category = Category.create({"name": "Django"})

        def test_list_shows_published_articles(self):
            Article.create({
                "title": "Hello",
                "body": "...",
                "is_published": True,
                "category_id": self.category.pk,
            })

            response = self.client.get("/api/articles")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], 1)
    ```

=== "Async"

    ```python title="blog/tests.py"
    from django.test import TestCase

    from .models import Article, Category


    class ArticleAPITests(TestCase):
        async def test_list_shows_published_articles(self):
            category = await Category.acreate({"name": "Django"})
            await Article.acreate({
                "title": "Hello",
                "body": "...",
                "is_published": True,
                "category_id": category.pk,
            })

            response = await self.async_client.get("/api/articles")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], 1)
    ```

`Article.create()` runs the same validation and hooks as the `POST` endpoint,
so it is a quick way to prepare test data.

## Hide or protect the docs

The interactive docs are public by default. Turn them off, or allow only staff
users:

```python title="blog/api.py"
from django.contrib.admin.views.decorators import staff_member_required

api = NinjaAIO(title="Blog API", docs_url=None)  # no docs
api = NinjaAIO(title="Blog API", docs_decorator=staff_member_required)  # staff only
```

## Checklist

- [ ] `python manage.py check --deploy` passes
- [ ] Private keys come from the environment, not from the repository
- [ ] `DEBUG = False` and `ALLOWED_HOSTS` is set
- [ ] The execution mode matches your server
- [ ] Tests cover your permission rules
- [ ] The docs are hidden or protected

## What's next

You've built a complete API. From here, explore the topics you need:

- [Deployment](../deployment.md) for servers, workers and databases
- [Viewsets](../guides/viewsets.md) for every viewset option
- [Troubleshooting](../troubleshooting.md) if something doesn't work
