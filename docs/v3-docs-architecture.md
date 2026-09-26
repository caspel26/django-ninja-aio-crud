# Version 3 Documentation Architecture

> Internal implementation artifact for Step 14. It defines what the version 3
> documentation contains and where each topic lives. It does not change the
> live site, its theme, or any published page. Visual design is Step 15.

## 1. Scope and method

Inputs used for this analysis:

- Every Markdown page under `docs/` (37 public pages, about 18,750 lines),
  excluding the internal `v3-*.md` artifacts.
- `mkdocs.yml` navigation, plugins, and `mike` versioning.
- `README.md` links, which are the main external entry points.
- `docs/troubleshooting.md` questions, used as a proxy for common issues.
- The version 3 public API contract (`docs/v3-public-api-contract.md`).

Limitations:

- No analytics or search-log data was available locally. The site has Google
  Analytics configured, so the "high-traffic" list in section 6 should be
  confirmed against real page views before redirects are finalized.
- Page counts in section 2 come from pattern matching and are indicators, not
  exact API-usage audits.

## 2. Findings

### 2.1 The site teaches the version 2 API

| Signal | Pages affected | Examples |
| --- | --- | --- |
| Deprecated configuration (`CreateSerializer`/`ReadSerializer`, `Meta.schema_*`, `SchemaModelConfig`) | 19 of 37 | `api/models/serializers.md` (116 matches), `tutorial/serializer.md` (95), `api/models/model_serializer.md` (71), `api/views/api_view_set.md` (51), `index.md` (41), `tutorial/model.md` (38) |
| Version 3 `Schemas`/`SchemaConfig` | **0 of 37** | Only the internal contract documents it |
| `ModelUtil` or `.util` as an application API | 13 | `api/models/model_util.md` (36), `tutorial/crud.md` (11), `api/type_hints.md` (8) |
| Deprecated `*_s()` methods | 9 | `api/models/model_util.md` (35), `api/models/model_serializer.md` (15), `tutorial/crud.md` (7) |
| Deprecated `@api_get`/`@api_post` | 8 | `tutorial/crud.md` (20), `api/views/api_view_set.md` (12), `api/views/api_view.md` (9) |
| Synchronous examples (`execution_mode`, sync CRUD facade) | effectively none | Every CRUD example is `async def` |
| mkdocstrings `:::` autodoc blocks | 0 | The "API Reference" is entirely hand-written narrative |

### 2.2 Structural problems

1. **Two quick starts** (`quick_start.md`, `quick_start_serializer.md`) split
   the first run by serializer style instead of teaching one path.
2. **Parallel tutorials:** `tutorial/model.md` and `tutorial/serializer.md`
   are two alternative "Step 1" pages, about 1,700 lines together, that differ
   only in configuration syntax. In version 3, both styles use the same
   `Schemas` class, so the split no longer exists.
3. **Authentication in three places:** `tutorial/authentication.md` (895
   lines), `auth.md` (365), and `api/authentication.md` (916) overlap on
   `AsyncJwtBearer`, claims, and cookie helpers. `auth_cookie.md` adds a
   fourth partial copy.
4. **"API Reference" is a set of guides.** Pages such as
   `api/views/api_view_set.md` (1,373 lines) and
   `api/models/model_serializer.md` (1,618 lines) mix tutorials, recipes,
   configuration tables, and internals. Nothing is generated from code.
5. **Reference is organized by module** (`views/`, `models/`, `renderers/`)
   instead of by user goal.
6. **Internal details are public:** `api/models/model_util.md` documents
   `ModelUtil`, `QueryUtil`, and query schemas. It is also the most complete
   reference for public features such as `QuerySet` read/detail
   optimization; the tutorials only repeat parts of it.
7. **Features without a canonical page:** field selection is only in
   `api/views/mixins.md`; nested writes only in
   `api/models/model_serializer.md`; bulk operations appear in both
   `tutorial/crud.md` and `api/views/api_view_set.md`; hooks are split across
   four pages.
8. **Missing topics:** synchronous usage, calling serializers from Python
   code (the CRUD facade), `BulkResult`, `OperationContext`, the error model,
   transactions, testing an API, choosing a serializer style, and migrating
   from version 2.
9. **Top-level navigation mixes page types:** "Authentication" and "AI Agent
   Integration" are standalone tabs next to "API Reference" and "Resources".

### 2.3 What works and should be preserved

- `branding.md`, `exceptions.md`, `orjson_renderer.md`, `router.md`,
  `logging.md`, `deployment.md`, `mcp.md`, and `comparison.md` are focused
  and mostly version-independent.
- The tutorial already follows one example domain (Article, Author,
  Category, Tag) across its steps.
- `release_notes.md` is generated from `CHANGELOG.md` by the `main.py`
  macros.
- `mike` versioning already keeps each 2.x release online.

## 3. Audiences and journeys

| # | Journey | Audience | Entry page | Path | Done when |
| --- | --- | --- | --- | --- | --- |
| J1 | First API | New user, new project | Home | Home → Installation → Quickstart → Tutorial | Running CRUD API with OpenAPI docs in under ten minutes |
| J2 | Existing Django project | User with existing models | Home / Choosing a serializer | Choosing a serializer → Schemas guide → ViewSets guide | Existing models exposed without changing their base class |
| J3 | Serializer choice | Evaluator | Choosing a serializer | Comparison table → one example per style | Can pick `ModelSerializer` or `Serializer` and knows the trade-offs |
| J4 | Sync usage | WSGI or sync-codebase user | Sync and async concept | Concept → sync tabs in every guide → Deployment | Runs the API under WSGI with sync hooks |
| J5 | Async usage | ASGI user | Sync and async concept | Concept → async tabs → Transactions → Deployment | Runs under ASGI with async hooks and no `SynchronousOnlyOperation` |
| J6 | Customization | Intermediate user | Guides index | Hooks, custom actions, permissions, filtering, query optimization | Adds behavior without leaving the framework |
| J7 | Troubleshooting | Any user | Search / Troubleshooting | Symptom → canonical guide section | Error resolved without reading source code |
| J8 | 2.x migration | Existing user | Version banner on 2.x pages / Migration | Migration overview → deprecation table → recipes | Upgrade runs with zero `DeprecationWarning`s |

Common-issue entry points, taken from the current FAQ, must each land on a
canonical section: empty relation lists, `SynchronousOnlyOperation`, nested
relations, disabling operations, UUID primary keys, pagination, mixed
public/protected endpoints, and unexpected 401 responses.

## 4. Sitemap

Principles:

- The top-level groups are the ones approved in the implementation plan.
- A page whose identity survives keeps its URL; new pages use hyphenated
  slugs. This keeps redirects to a minimum.
- Every guide shows `ModelSerializer` and `Serializer` in linked tabs when
  they differ, and sync and async in linked tabs when they differ. No page
  is duplicated per style or mode.

```text
Home                                   /
Get started                            /getting_started/
├── Installation                       /getting_started/installation/
├── Quickstart                         /getting_started/quick_start/
└── Choosing a serializer              /getting_started/choosing-a-serializer/      (new)
Tutorial                               /tutorial/                                   (new index: what you build, prerequisites)
├── 1. Models and schemas              /tutorial/model/
├── 2. CRUD API                        /tutorial/crud/
├── 3. Relations                       /tutorial/relations/                         (new)
├── 4. Authentication                  /tutorial/authentication/
├── 5. Permissions                     /tutorial/permissions/
├── 6. Filtering and pagination        /tutorial/filtering/
└── 7. Ready for production            /tutorial/production/                        (new)
Guides                                 /guides/
├── Data
│   ├── Schemas                        /guides/schemas/
│   ├── Validation                     /guides/validation/
│   ├── Using serializers in Python    /guides/python-crud/                         (new)
│   ├── Dumping objects                /guides/dumping/                             (new)
│   ├── Relations                      /guides/relations/
│   ├── Nested writes                  /guides/nested-writes/
│   ├── Bulk operations                /guides/bulk-operations/
│   └── Query optimization             /guides/query-optimization/
├── Endpoints
│   ├── ViewSets                       /guides/viewsets/
│   ├── Custom actions                 /guides/custom-actions/
│   ├── Routers and versioning         /guides/routers/
│   ├── Filtering and search           /guides/filtering/
│   ├── Pagination                     /guides/pagination/
│   ├── Field selection                /guides/field-selection/
│   └── Soft delete                    /guides/soft-delete/
├── Security
│   ├── JWT authentication             /guides/authentication/
│   ├── Cookie authentication (BFF)    /guides/cookie-authentication/
│   └── Permissions                    /guides/permissions/
├── Behavior
│   ├── Hooks                          /guides/hooks/
│   └── Errors                         /guides/errors/
└── Integrations
    ├── Django Admin                   /guides/admin/
    ├── AI agents (MCP)                /guides/mcp/
    ├── Swagger UI                     /guides/swagger-ui/
    ├── Logging                        /guides/logging/
    └── Type hints                     /guides/type-hints/
Concepts                               /concepts/
├── Serializer-first architecture      /concepts/serializer-first/                  (new)
├── Sync and async                     /concepts/sync-and-async/                    (new)
├── Request and operation lifecycle    /concepts/lifecycle/
├── Transactions                       /concepts/transactions/                      (new)
└── Schema generation and caching      /concepts/schema-generation/                 (new)
API reference                          /api/
├── Serializers                        /api/models/model_serializer/, /api/models/serializers/
├── SchemaConfig                       /api/schema-config/                          (new)
├── APIViewSet and APIView             /api/views/api_view_set/, /api/views/api_view/
├── Decorators                         /api/views/decorators/
├── Mixins                             /api/views/mixins/
├── NinjaAIO and router                /api/views/router/
├── Authentication                     /api/authentication/
├── Pagination                         /api/pagination/
├── Exceptions                         /api/exceptions/
├── Types (BulkResult, OperationContext) /api/types/                                (new)
├── Renderers                          /api/renderers/orjson_renderer/
└── Settings                           /api/settings/                               (new)
Migration to v3                        /migration/                                  (new)
├── Overview and checklist             /migration/
├── Deprecations and replacements      /migration/deprecations/
├── Breaking changes                   /migration/breaking-changes/
└── Recipes                            /migration/recipes/
Project
├── Release notes                      /release_notes/
├── Framework comparison               /comparison/
├── Performance                        /performance/
├── Deployment                         /deployment/
├── Troubleshooting and FAQ            /troubleshooting/
└── Contributing                       /contributing/
```

Structural notes:

- **Tutorial:** a single progressive Article/Author/Category/Tag
  application. Step 1 shows both serializer styles in tabs; from step 2 on
  the code is identical for both. Each step states its prerequisites and ends
  with a working, runnable state. Soft delete, bulk operations, and custom
  actions leave the tutorial and become guides.
- **API reference:** short pages built on mkdocstrings `:::` blocks plus a
  hand-written summary table. Narrative, recipes, and examples longer than a
  few lines belong in guides. The `/api/` URLs stay, but their content
  becomes reference only.
- **Internal artifacts** (`v3-*.md`) are excluded from the build with
  `exclude_docs` and removed before the 3.0 release, as each file already
  states.

## 5. Page inventory and dispositions

Dispositions: **keep** (URL and content survive with version 3 edits),
**rewrite** (URL survives, content replaced), **merge** (content folded into
another page, URL redirected), **move** (content survives at a new URL),
**split** (content distributed to several pages), **archive** (stays only in
2.x versioned docs).

| Current page | Lines | Disposition | Target |
| --- | ---: | --- | --- |
| `index.md` | 629 | rewrite | `/`: one value proposition, runnable example, sync/async story, learning paths (content in Step 17) |
| `getting_started/installation.md` | 61 | keep | Same URL; add supported Python/Django matrix |
| `getting_started/quick_start.md` | 181 | rewrite | Same URL; single canonical quickstart with `Schemas`, sync/async tabs |
| `getting_started/quick_start_serializer.md` | 243 | merge | `/getting_started/choosing-a-serializer/` (standalone example) |
| `tutorial/model.md` | 779 | rewrite | Same URL; `Schemas`, both styles in tabs; query optimization moves to a guide |
| `tutorial/serializer.md` | 918 | merge | `/tutorial/model/` (tab) and `/guides/schemas/` |
| `tutorial/crud.md` | 1128 | rewrite | Same URL; remove `@api_*`, `ModelUtil`, and bulk; add `execution_mode` |
| `tutorial/authentication.md` | 895 | rewrite | Same URL; tutorial-only content, link to `/guides/authentication/` for details |
| `tutorial/filtering.md` | 974 | rewrite | Same URL; shorten, link to filtering and pagination guides |
| `tutorial/permissions.md` | 225 | keep | Same URL; add sync/async tabs for permission hooks |
| `tutorial/soft_delete.md` | 174 | move | `/guides/soft-delete/` |
| `api/type_hints.md` | 262 | move | `/guides/type-hints/`; remove `ModelUtil[...]` as an application pattern |
| `api/views/api_view.md` | 183 | split | Reference stays; `@action` on `APIView` goes to `/guides/custom-actions/` |
| `api/views/api_view_set.md` | 1373 | split | Reference stays; narrative to `/guides/viewsets/`, `bulk-operations`, `relations` (M2M), `hooks`, `filtering`; lifecycle diagram to `/concepts/lifecycle/`; transactions to `/concepts/transactions/` |
| `api/views/decorators.md` | 331 | split | Reference stays; recipes to `/guides/custom-actions/` |
| `api/views/mixins.md` | 639 | split | Reference stays; to `/guides/filtering/`, `field-selection`, `soft-delete`, `permissions` |
| `api/views/router.md` | 184 | split | Reference stays; versioned-API example to `/guides/routers/` |
| `api/models/model_serializer.md` | 1618 | split | Reference stays; to `/guides/schemas/`, `nested-writes`, `hooks`, `relations` |
| `api/models/model_util.md` | 1285 | archive | `QuerySet` configuration to `/guides/query-optimization/`; `NinjaAIOMeta` to `/guides/viewsets/`; URL redirected to `/migration/deprecations/#modelutil` |
| `api/models/serializers.md` | 1217 | split | Reference stays; to `/guides/schemas/`, `relations` (unions, string refs), `/getting_started/choosing-a-serializer/` |
| `api/models/validators.md` | 475 | move | `/guides/validation/`; examples on `Schemas` |
| `api/admin.md` | 207 | move | `/guides/admin/` |
| `api/branding.md` | 237 | move | `/guides/swagger-ui/` |
| `api/authentication.md` | 916 | merge | `/guides/authentication/`; class signatures stay at `/api/authentication/` as reference |
| `api/exceptions.md` | 288 | split | Reference stays; error model narrative to `/guides/errors/` |
| `api/pagination.md` | 806 | split | Reference stays; narrative to `/guides/pagination/` |
| `api/renderers/orjson_renderer.md` | 156 | keep | Same URL |
| `auth.md` | 365 | merge | `/guides/authentication/` |
| `auth_cookie.md` | 210 | move | `/guides/cookie-authentication/` |
| `mcp.md` | 365 | move | `/guides/mcp/` |
| `logging.md` | 170 | move | `/guides/logging/` |
| `comparison.md` | 343 | keep | Same URL (linked from README) |
| `performance.md` | 150 | keep | Same URL |
| `deployment.md` | 286 | keep | Same URL; add WSGI (sync) next to ASGI |
| `troubleshooting.md` | 262 | rewrite | Same URL; each answer links to its canonical section |
| `contributing.md` | 210 | keep | Same URL |
| `release_notes.md` | 3 | keep | Same URL (macro-generated) |
| `v3-*.md` | — | exclude | Excluded from the build; deleted before 3.0 |

Totals for the 37 public pages: 8 keep, 7 rewrite, 9 split, 8 move, 4 merge,
1 archive. No page is deleted without a redirect.

## 6. URL migration map

Redirects apply to the version 3 docs (`latest` once 3.0 is published).
Versioned 2.x docs under `/2.36/` and earlier stay unchanged.

| Old URL | New URL | Reason |
| --- | --- | --- |
| `/getting_started/quick_start_serializer/` | `/getting_started/choosing-a-serializer/` | merge |
| `/tutorial/serializer/` | `/tutorial/model/` | merge (tab) |
| `/tutorial/soft_delete/` | `/guides/soft-delete/` | move |
| `/api/type_hints/` | `/guides/type-hints/` | move |
| `/api/models/model_util/` | `/migration/deprecations/#modelutil` | archive |
| `/api/models/validators/` | `/guides/validation/` | move |
| `/api/admin/` | `/guides/admin/` | move |
| `/api/branding/` | `/guides/swagger-ui/` | move |
| `/auth/` | `/guides/authentication/` | merge |
| `/auth_cookie/` | `/guides/cookie-authentication/` | move |
| `/mcp/` | `/guides/mcp/` | move |
| `/logging/` | `/guides/logging/` | move |

This is 12 redirects in total. Every other current URL keeps its path.
Pages marked "split" keep their URL, but some of their anchors move. Each
split page gets a short "Moved sections" table that links old section names
to their new guide.

Priority URLs to verify against analytics before release: `/`,
`/comparison/` (linked from README), `/getting_started/quick_start/`,
`/tutorial/model/`, `/api/views/api_view_set/`,
`/api/models/model_serializer/`, and `/auth/`.

Implementation needs the `mkdocs-redirects` plugin, a new docs dependency
that must be approved (see section 9).

## 7. Page templates

Every page has front matter with `title` and `description` (used for search
and social previews) and exactly one H1.

**Voice rule for all public pages:** keep the documentation as friendly and
simple as it is today. Pages show what to write and what you get, with short
examples. They never explain design rationale, implementation choices, or why
an alternative was rejected; that material stays in these internal `v3-*.md`
artifacts.

| Template | Used by | Required structure | Rules |
| --- | --- | --- | --- |
| **Landing** | `/` | Value proposition → runnable example → sync/async story → learning paths → project links | No feature-card walls; single primary call to action |
| **Section index** | `/getting_started/`, `/tutorial/`, `/guides/`, `/concepts/`, `/api/`, `/migration/` | One-paragraph purpose → grouped links with one-line summaries | No original content beyond orientation |
| **Tutorial step** | `/tutorial/*` | Prerequisites (previous step) → goal → numbered steps with complete code → "Check it works" → recap → next step | Continues the same project; runnable end state; links to guides instead of explaining every option |
| **Guide** | `/guides/*` | Problem statement → minimal example → options/variations → common pitfalls → related links | Task-oriented title ("Filter list endpoints"); linked `ModelSerializer`/`Serializer` and sync/async tabs where they differ |
| **Concept** | `/concepts/*` | Summary → mental model (diagram allowed) → how it affects your code → related guides | Explains *why*; code only to illustrate; no option tables |
| **Reference** | `/api/*` | One-line summary → import path → summary table → mkdocstrings `:::` block → "Moved sections" (when split) | No tutorials; examples at most a few lines; generated from docstrings where reliable |
| **Migration** | `/migration/*` | Who is affected → before/after code → automated check (warning text) → related reference | Every deprecation lists the exact `DeprecationWarning` message and replacement |
| **Release** | `/release_notes/` | Macro-generated from `CHANGELOG.md` | No hand edits |
| **Benchmark** | `/comparison/`, `/performance/` | Method and environment → results → how to reproduce → caveats | States framework versions and hardware; links to raw results |

Shared components (designed visually in Steps 15-18, defined here by
content): sync/async tabs, serializer-style tabs, callouts (note, warning,
deprecated, version-added), API signature block, prerequisites box,
previous/next navigation, compatibility table, and "Moved sections" table.

Version notices: every 2.x versioned page gets a banner linking to the same
topic in version 3 (or to `/migration/`) through the `mike` version selector
and an announcement partial. Content is not edited per page.

## 8. Content ownership matrix

Each topic has exactly one **canonical page**. Other pages can include at
most a short summary plus a link. **Source of truth** is what the page must
be checked against when the code changes.

| Topic | Canonical page | May summarize | Source of truth |
| --- | --- | --- | --- |
| Installation and supported versions | `/getting_started/installation/` | Home, Contributing | `pyproject.toml` |
| First API | `/getting_started/quick_start/` | Home | Tested snippet |
| Serializer styles and choice | `/getting_started/choosing-a-serializer/` | Home, Tutorial 1, Schemas | Contract §serializers |
| `Schemas` / `SchemaConfig` | `/guides/schemas/` | Tutorial 1, Quickstart | `ninja_aio/models/serializers.py`, system checks |
| Lazy schema attributes, `get_schema` | `/concepts/schema-generation/` | Schemas | Contract §schemas |
| Validators | `/guides/validation/` | Schemas | Validator collection code |
| Direct CRUD facade (`create`…`adestroy`) | `/guides/python-crud/` | Serializer-first concept | Contract method matrix |
| `model_dump(s)` / `amodel_dump(s)` | `/guides/dumping/` | Python CRUD | Contract method matrix |
| Relations (FK, reverse, M2M, unions, string refs, `relations_as_id`) | `/guides/relations/` | Tutorial 3 | Relation schema code |
| Nested writes | `/guides/nested-writes/` | Relations | `nested` config code |
| Bulk operations and `BulkResult` | `/guides/bulk-operations/` | ViewSets, `/api/types/` | `ninja_aio/types.py` |
| Query optimization (`QuerySet` config) | `/guides/query-optimization/` | Tutorial 6, Troubleshooting | `QueryUtil` |
| APIViewSet configuration, `NinjaAIOMeta`, `execution_mode` | `/guides/viewsets/` | Tutorial 2 | `ninja_aio/views/api.py` |
| `@action`, `@on`, `APIView` actions | `/guides/custom-actions/` | Tutorial 2 | Decorators code |
| `@api_*` decorators | `/migration/deprecations/` | Decorators reference | Deprecation warnings |
| Routers and versioned APIs | `/guides/routers/` | — | `ninja_aio/router.py` |
| Filtering, search, filter mixins | `/guides/filtering/` | Tutorial 6 | Mixins code |
| Pagination | `/guides/pagination/` | Tutorial 6 | Pagination code |
| Field selection | `/guides/field-selection/` | — | `FieldSelectionViewSetMixin` |
| Soft delete | `/guides/soft-delete/` | — | `SoftDeleteViewSetMixin` |
| JWT authentication | `/guides/authentication/` | Tutorial 4 | `ninja_aio/auth.py` |
| Cookie authentication | `/guides/cookie-authentication/` | JWT guide | `ninja_aio/auth.py` |
| Permissions | `/guides/permissions/` | Tutorial 5 | Permission mixins |
| Hooks (lifecycle, reactive, viewset; naming rule) | `/guides/hooks/` | Sync and async concept | `ninja_aio/models/hooks.py` |
| Operation context | `/api/types/` | Hooks guide | `OperationContext` |
| Errors and exception mapping | `/guides/errors/` | Exceptions reference | `ninja_aio/exceptions.py` |
| Sync vs async execution | `/concepts/sync-and-async/` | Every guide (tabs) | Parity test suite |
| Request/operation lifecycle | `/concepts/lifecycle/` | ViewSets | View factory code |
| Transactions | `/concepts/transactions/` | Nested writes, Bulk | Operation executors |
| Admin integration | `/guides/admin/` | — | `ninja_aio/admin.py` |
| MCP integration | `/guides/mcp/` | Home | `ninja_aio/mcp/` |
| Swagger UI branding | `/guides/swagger-ui/` | — | `ninja_aio/docs.py` |
| Logging | `/guides/logging/` | Deployment | Logger names in code |
| Type hints and generics | `/guides/type-hints/` | Reference pages | Typing examples (Phase 11) |
| Settings (`NINJA_AIO_*`) | `/api/settings/` | Guides that use a setting | `django.conf.settings` lookups |
| Deprecations and replacements | `/migration/deprecations/` | Reference "deprecated" callouts | `docs/v3-public-api-contract.md` |
| Release history | `/release_notes/` | Home (latest only) | `CHANGELOG.md` |
| Benchmarks | `/comparison/`, `/performance/` | Home, README | `tests/comparison/`, `tests/performance/` |

Code examples in canonical pages come from tested snippet files (via
`pymdownx.snippets`) so the Phase 9 "code-example validation" gate can run
them. Summaries elsewhere may use inline code, but must not contain full
configuration examples.

## 9. Decisions requested

1. **Sitemap (section 4):** approve the groups, page list, and slugs,
   including the new tutorial steps 3 (Relations) and 7 (Ready for
   production), and moving soft delete out of the tutorial.
2. **URL policy:** keep the URLs of surviving pages, including underscores
   in `getting_started/` and `release_notes/`, rather than renaming every
   path to hyphens. The alternative is about 20 more redirects.
3. **Redirects:** add `mkdocs-redirects` to `docs/requirements.txt` for the
   12 redirects in section 6.
4. **Reference generation:** use mkdocstrings for the `/api/` pages (already
   installed and configured, currently unused). This requires docstring
   quality work on public classes during Step 18.
5. **`ModelUtil` page:** archive it (available only in 2.x docs), after its
   public content (`QuerySet` config, `NinjaAIOMeta`) moves to guides.
6. **Internal artifacts:** exclude `v3-*.md` from the build now with
   `exclude_docs`, and delete them before the 3.0 release.
7. **Snippet testing:** canonical examples live in tested snippet files.
   Where they live (for example `docs/snippets/` plus a test module) is
   decided in Step 19.
8. **Build engine:** keep the MkDocs content format and build with Zensical,
   falling back to Material for MkDocs 9.x only if the Step 16 prototype hits
   a blocker (section 11.4).

## 10. Out of scope for this step

- Theme, colors, typography, templates, and CSS (Steps 15-16).
- Writing the new pages (Step 19). This document only defines their scope
  and ownership.
- Changing `mkdocs.yml` navigation or adding redirects. Both happen when the
  content migrates, so the live site never points to pages that do not exist
  yet.

## 11. Visual reference and principles for Step 15

The sister project `goninja` (`docs-site/`, Hugo + Hextra) is a **quality
benchmark, not a template**. It shows the level of finish we are aiming for:
a coherent token system, a real product demo on the homepage, and themeable
HTML diagrams. This site must reach that level with its own identity: modern,
clearly hand-designed, and not recognizable as a generated template.

### 11.1 What goninja does

| Area | goninja implementation |
| --- | --- |
| Architecture | Stock theme (Hextra) + one brand stylesheet (`assets/css/custom.css`, about 1,600 lines) + four small partials + one diagram shortcode. No forked templates. |
| Tokens | `--gn-*` custom properties for surface, border, text, code, and shadow, redefined under `.dark`. The theme's primary scale is derived from three HSL values. |
| Palette | Sampled from the logo: purple primary, cyan accent, near-black ink `#0D0C14` dark surface. |
| Typography | Inter (UI) and JetBrains Mono (code); compact 15px body, tight heading tracking, H2 with a hairline rule. |
| Homepage | Pill "status" badge → gradient headline → one-paragraph subtitle → primary and secondary buttons → editor-window demo (title bar, file tabs, model → generated code) → six feature cards → numbered "struct to running API" steps → "Where to go next" cards. |
| Code | Rounded, bordered, softly shadowed blocks; filename labels; tinted inline code in the accent colour. |
| Diagrams | HTML/CSS figures (`gn-diagram` shortcode: pipeline, list vs detail query shape, precedence lists) instead of images or Mermaid. Accessible via `aria-label`, themeable, and crisp at any size. |
| Docs pages | Left sidebar, right "On this page" TOC, breadcrumb, previous/next footer, "Edit this page" link. |
| Chrome | Navbar with logo, wordmark, live GitHub star count and version switcher; banner for old/dev versions; minimal footer; per-page OpenGraph/Twitter metadata; `theme-color` meta for both schemes. |
| Other components | Benchmark dashboard cards, release list, chips, version menu. |

### 11.2 What to take from it and what not to

Take the *mechanisms*, not the look:

| Take | Leave |
| --- | --- |
| Token system with a real dark theme (not an inverted light theme) | Gradient headline text |
| One brand stylesheet split by responsibility, no forked templates | Pill "status" badge above the hero |
| A homepage demo built from real code and real output | Six-card icon feature grid |
| HTML/CSS diagrams drawn from the same tokens | Soft drop shadows on every code block |
| Version banner, social metadata, `theme-color` | Its fonts (Inter + JetBrains Mono): common enough to feel default |

Mechanical mapping to this site:

| Mechanism | Implementation here |
| --- | --- |
| Brand stylesheet | `tokens.css`, `shell.css`, `components.css`, `pages.css` (replacing `extra.css`) |
| Palette from the logo | Colors sampled from `images/logo-full.png` (ninja purple, amber "CRUD" lettering), used as flat colors, with amber reserved for a single job |
| Custom homepage | `overrides/home.html`, used only by `index.md` |
| Product demo | Model with `Schemas` → `APIViewSet` → real request and JSON response, with a sync/async switch |
| Diagrams | `main.py` macros (a `diagram("lifecycle")` call in the page) rendering HTML figures: request lifecycle, sync vs async execution, auth precedence, schema generation |
| Version banner | `{% raw %}{% block outdated %}{% endraw %}` in `overrides/main.html`, shown by the `mike` version selector on every non-default version |
| Benchmark results | A results component for `comparison.md` and `performance.md` showing the real numbers |

### 11.3 Avoiding the generated look

Generated sites share recognizable defaults. Every Step 15 direction must
follow these rules, and the review checklist in Step 15 checks them
explicitly.

| Generated-look default | Rule for this site |
| --- | --- |
| Purple-to-blue gradients, glows, glassmorphism | Flat colors only, with one exception: the brand gradient (logo purple to amber) on the wordmark. Depth comes from tonal surface layers, hairline borders, and a restrained three-step elevation scale; no glows or blur |
| Centered hero with gradient text and two pill buttons | Left-aligned, asymmetric hero: one plain statement, then the product demo carries the page |
| 3×2 grid of icon + title + blurb cards | At most three strong sections; features are shown through code and output, not described in cards |
| An icon or emoji on every heading (the current site puts `:material-*:` on almost every H1/H2) | No decorative heading icons; icons only where they carry meaning (e.g. HTTP method, deprecated, sync/async) |
| Stock abstract illustrations and 3D blobs | Only real artifacts: code, terminal output, OpenAPI screenshots, query counts, benchmark numbers, and the project's own mascot |
| Marketing copy ("blazing fast", "seamless", "supercharge", "effortless") | Specific, checkable claims: names, numbers, and links to the benchmark that backs them |
| Large radii and pill shapes everywhere | One small radius scale (4-6 px controls, 10-14 px surfaces); pills only for the version and HTTP methods |
| Uniform spacing and card-in-card layouts | Editorial rhythm: a strict 4 px grid, clear density changes between hero, prose, and reference |
| Default font pairings (Inter, Roboto, Poppins) | A deliberate pairing chosen in Step 15 from shortlisted families with real character (for example IBM Plex, Source Serif + Source Code, or a grotesk with a matching mono), with tabular figures for numbers |
| Decorative motion | Motion only on state changes (tab thumb, panel swap, linked fields, copy confirmation, palette); honors `prefers-reduced-motion` |

Signals of craft that each direction must show: consistent optical sizes for
headings, proper code typography (ligatures off, clear `0`/`O` and `1`/`l`),
aligned table numerals, visible keyboard focus, and one consistent line
weight across diagrams and icons.

### 11.4 Implications for Steps 15 and 16

- Step 15 produces two or three directions as static HTML mockups of the
  homepage and one guide page, in light and dark themes. They must be
  genuinely different: for example an editorial/typographic direction, a
  technical/terminal-inspired direction, and a quieter reference-first
  direction. Each is reviewed against section 11.3 before comparison.
- Keeping the MkDocs content format stays the default (implementation plan,
  Phase 9 item 10). goninja shows the target quality comes from tokens, a
  brand stylesheet, a custom homepage, and HTML diagrams, not from the static
  site generator.
- **Build engine: Zensical instead of MkDocs + Material.** MkDocs 1.x has been
  unmaintained since August 2024. Material for MkDocs entered maintenance mode
  in November 2025, with critical fixes promised for at least 12 months. Its
  team's successor, Zensical, reads `mkdocs.yml`, renders the same Python
  Markdown, and natively supports every plugin this site uses: `macros`,
  `search`, `autorefs`, `section-index`, `mkdocstrings`, `mike` (compatible
  fork). It also supports `redirects`, including anchor-level redirects for
  split pages. Content, `main.py` macros, and overrides carry over.
- Risk: Zensical is pre-1.0 (0.0.x as of September 2026). Mitigation: Step 16
  builds the prototype with Zensical first. If a blocker appears, the same
  `mkdocs.yml`, CSS, and overrides build on Material for MkDocs 9.x.
- Hugo + Hextra, as in goninja, stays rejected. It would give up mkdocstrings,
  the published `mike` history, and the macros for no gain in visual
  quality.

### 11.5 Selected direction: D · Studio

Mockups live in `design/step15/` (overview: `index.html`). Directions A
(Manuscript), B (Console), and C (Index) were reviewed as professional but not
modern enough; D combines B's precision, A's hierarchy, and C's search-first
index, and is the direction Step 16 implements.

| Element | Decision |
| --- | --- |
| Theme | Dark-first; light is a full variant, not an inversion |
| Surfaces | `bg` plus three tonal layers (`surface-1..3`), hairline edges, a 1px inner top highlight instead of shadows |
| Type | Schibsted Grotesk (UI and display, weights 400-900), Source Serif 4 (guide titles, ledes and section headings, taken from direction A), IBM Plex Mono (code); tabular figures scoped to data, because Schibsted's `tnum` also spaces punctuation |
| Color | Logo purple for brand and links, amber for attention and linked highlights; gradient on the wordmark only |
| Depth | Tonal layers plus a three-step elevation scale (`shadow-1..3`): code blocks and cards at 1, the guide article sheet and key diagram step at 2, the homepage demo, menus and palette at 3 |
| Guide pages | Direction A's article reading experience on a raised sheet: serif title and lede, ruled serif section headings with hover anchors, content blocks set back on the page tone |
| Homepage | Bold statement beside the mascot, primary button plus copyable install command, verifiable facts (Python, Django Ninja, tests, coverage, license), interactive operation demo (model, HTTP, OpenAPI with linked fields), capability list with real attribute names, Python usage, honest benchmarks, three learning paths |
| Versioning | Header version menu styled over the `mike` selector (latest, dev, 2.x releases, all versions); non-latest versions show a banner with links to the latest docs and the migration guide |
| Logo | `design/step15/logo/build_logo.py` derives header marks from `docs/images/logo.png`: the drop shadow is removed, and the dark-theme mark gets a light outline so the black line work reads on dark surfaces |
| Components | Segmented control with sliding thumb, code block with tabs and copy, command palette (⌘K and `/`), version menu, scroll-spy table of contents, pager, callout, diagram cards |

Open items for Step 16:

- Replace the generated raster marks with a redrawn SVG mark when a designer
  is available; the build script stays the fallback.
- Self-hosted fonts instead of Google Fonts, within the performance budget.
- Map every mockup component onto the Zensical/Material template blocks, and
  list what needs a template override rather than CSS.
- Found while building: `docs/api/pagination.md` documents
  `count/next/previous/results`, but the list endpoint returns
  `{"items": [...], "count": N}`. Fixed with the content in Step 19.

### 11.6 Step 16 implementation

| Area | Result |
| --- | --- |
| Build engine | Zensical 0.0.65 builds the unchanged `mkdocs.yml` (macros, search, autorefs, section-index) in about 2 s with no warnings, using `theme.variant: classic`. The same config still builds on MkDocs + Material 9.6 with no warnings, so CI keeps working until the engine switch |
| Stylesheets | `docs/extra.css` (1,218 lines) removed. `docs/stylesheets/tokens.css` (tokens, `@font-face`, Material/Zensical variable mapping, search-dialog variables), `shell.css` (header, search, version selector, banners, tabs, sidebars, TOC, footer), `components.css` (typography, code, tabs, callouts, tables, buttons, cards), `pages.css` (transitional restyle of classes the current content still uses; removed in Steps 17-19) |
| Fonts | Self-hosted WOFF2 in `docs/assets/fonts/` (about 220 KB, OFL texts alongside); `theme.font: false`, so no Google Fonts requests |
| Palette | Dark (`slate`) first, light second, both `primary/accent: custom` |
| Templates | `partials/logo.html` renders the dark and light marks; `main.html` replaces the GitHub announcement with the outdated-version banner; `partials/javascripts/outdated.html` fixes an upstream `new URL()` call that threw on every page; `partials/announce.html` removed (unused) |
| Site name | `django-ninja-aio-crud`, rendered as the gradient wordmark |
| Versioning | Checked against a simulated `mike` layout (3.0 latest, dev, 2.36): selector lists all versions, non-latest versions show the banner |
| Baselines | `docs-tests/` Playwright suite (`npx playwright test` after `zensical build`): visual regression for home, installation, tutorial, reference, and release notes in dark and light at desktop and mobile, axe WCAG 2 AA checks, labelled header controls, and keyboard-reachable scrollable code (`docs/javascripts/a11y.js`). 44 checks pass |

Deferred:

- CI and `docs/requirements.txt` still use MkDocs + Material. Switching them to
  Zensical and the `mike` fork changes the publishing workflow, so it happens
  with release validation (Step 21). Zensical currently requires
  `pymdown-extensions` 12, which conflicts with the pinned Material 9.6.
- The ⌘K palette, homepage demo, and article sheet from the mockups belong to
  the homepage and page templates (Steps 17 and 18).

### 11.7 Step 17 implementation

- `docs/index.md` is now only front matter (`template: home.html`, title,
  description); the 629-line markdown homepage is gone.
- `overrides/home.html` renders the Studio homepage: hero with the mascot,
  copyable install command, requirements, the interactive operation demo
  (model, HTTP, OpenAPI with linked fields), capability list linking to the
  current pages, sync/async Python example, benchmark bars, and three learning
  paths. Links use the `url` filter, so they work under every `mike` version.
- `docs/javascripts/home.js` drives the demo, tabs, and copy button, and
  re-initializes on instant navigation through `document$`.
- Homepage styles live in the final section of `pages.css`; the transitional
  hero, badge, and call-to-action rules are removed.
- `theme-color` metadata for both schemes in `overrides/main.html`.
- Checks: all 15 homepage links resolve, no script errors, no horizontal
  overflow at 390 px, and the `docs-tests` suite passes 44/44 with refreshed
  homepage baselines. Fixed along the way: dimmed demo lines and `small`
  labels (Material's 0.75 opacity) failed contrast, and the GitHub facts in the
  header did too once the API responded.

### 11.8 Step 18 implementation: page patterns

Pages opt into a layout with front matter; `overrides/partials/content.html`
renders the label strip above the title, and CSS picks the layout from it.

```yaml
type: guide        # tutorial | guide | concept | reference | migration | release | benchmark
step: 2            # tutorial only
steps: 7           # tutorial only
status: new        # new | changed | deprecated (optional)
since: "3.0"       # version for the status label
```

| Pattern | Markdown |
| --- | --- |
| Article sheet, serif lede | automatic for `guide`, `tutorial`, `concept`; the first paragraph after the title is the lede |
| Dense reference headings | automatic for `reference` |
| Numbered steps | `<div class="nac-steps" markdown>` with one `###` heading per step |
| Sync/async tabs | `=== "Sync"` / `=== "Async"` (linked across the page) |
| API signature | `<div class="nac-signature" markdown>` around one fenced code block |
| Version notices | `!!! new "New in 3.0"`, `!!! changed "Changed in 3.0"`, `!!! deprecated "Deprecated in 3.0"` |
| Before you start | `!!! prerequisites "Before you start"` |
| Callouts | `!!! note`, `tip`, `warning`, `danger`, collapsible `??? question` |
| Previous/next | automatic from the navigation order (`navigation.footer`) |

`docs/v3-components.md` shows every pattern on one page, is covered by
`docs-tests` (52 checks pass), and is removed with the other `v3-*.md` files
before release.
