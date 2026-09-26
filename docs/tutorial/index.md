---
type: tutorial
title: Tutorial
description: Build a complete blog API step by step, from models to production.
---

# Tutorial

In this tutorial you build a blog API with articles and categories. Each step
adds one feature on top of the previous one.

| Step | You will learn to |
| --- | --- |
| [1. Define the model](model.md) | Describe what each operation reads and writes |
| [2. Create the CRUD API](crud.md) | Expose the endpoints and add a custom action |
| [3. Add relations](relations.md) | Return and accept related objects |
| [4. Add authentication](authentication.md) | Protect endpoints with JWT |
| [5. Add permissions](permissions.md) | Decide who can do what |
| [6. Filter, search and sort](filtering.md) | Let clients find what they need |
| [7. Go to production](production.md) | Check, test and deploy your API |

!!! prerequisites "Before you start"

    - Python 3.10 or newer
    - A Django project with an app called `blog` in `INSTALLED_APPS`
    - django-ninja-aio-crud [installed](../getting_started/installation.md)

Every code example has a **Sync** and an **Async** version when they differ.
Pick one and use it for the whole tutorial.

[Start with step 1](model.md){ .md-button .md-button--primary }
