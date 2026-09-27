---
type: migration
title: A tested blog migration
description: A real v2 blog application migrated and tested against the unreleased v3 branch.
---

# A tested blog migration

The [ninja-aio-blog-example](https://github.com/caspel26/ninja-aio-blog-example)
application at commit `93cf463` was migrated to the unreleased v3 branch.
The original application checkout was left intact. The migration is available
as a [Git patch](blog-example-v3.patch), with seven HTTP regression tests and
an updated README. It has not been pushed to the example repository or released.

## Apply and run

Start from the example's `93cf463` commit in a separate checkout. Apply the
patch with `git am /path/to/blog-example-v3.patch`, then follow its README.
Install the local framework checkout in editable mode; no published v3 package
is required. The patch includes the initial Django migration so a fresh database
can be created with `manage.py migrate`.

## Changes exercised

- Nested serializer declarations become `Schemas` and `SchemaConfig`.
- Async queryset hooks use `aqueryset_request`.
- `ModelUtil` reads become model facade calls; custom lists use bounded pagination.
- Custom endpoints use `action`, preserving the application's plural routes.
- Login explicitly permits unauthenticated requests. Password changes hash the
  new value before saving it.
- Foreign keys accept field names and `_id` attnames. Duplicate usernames return
  `409`, and `PATCH` preserves omitted fields.

The login and password fixes correct existing application defects; they are
not required framework API renames. Default pagination on custom lists is an
intentional response change: these endpoints now return `items` and `count`.

## Validation

The migrated application passes Django's system checks, a fresh migration and
seed, and all seven tests with `DeprecationWarning` treated as an error:

```bash
python -W error::DeprecationWarning blog/manage.py check
python -W error::DeprecationWarning blog/manage.py test api
```

The tests cover signup and password hashing, login/refresh/current user,
authentication failures, partial updates and duplicate usernames, owner-scoped
posts with both FK input spellings, M2M relations and comments, and logging in
with a changed password.

The same tests against the original application with framework 2.36 yield two
passes, four failures, and one error. This establishes the observed pre-migration
behavior; it does not imply every difference was introduced by the framework.
Both environments used the same Python, Django, Ninja, and Pydantic versions.
The original application's dependency versions were not otherwise evaluated.
