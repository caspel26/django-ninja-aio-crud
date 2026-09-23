# Version 3.0 Implementation Plan

## Objective

Version 3.0 will replace the utility-first, async-only public API with a
serializer-first API that has equivalent synchronous and asynchronous entry
points.

The release should reduce the number of concepts required for common CRUD
work while retaining the current hooks, relationship handling, query
optimizations, bulk behavior, and generated viewsets.

The documentation site is part of the product redesign. Version 3 will ship
with a new information architecture, visual language, and learning path that
teach the serializer-first, sync/async API instead of adapting the current
site page by page.

## Accepted API decisions

### Serializer-first public API

Application code should call operations on its concrete `ModelSerializer` or
`Serializer`, not through `.util`:

```python
# Sync
book = Book.create(data, request=request)
book = Book.get(pk=book.pk, request=request)
book = Book.update(book, data, request=request)
payload = Book.dump(book)
Book.destroy(book, request=request)

# Async
book = await Book.acreate(data, request=request)
book = await Book.aget(pk=book.pk, request=request)
book = await Book.aupdate(book, data, request=request)
payload = await Book.adump(book)
await Book.adestroy(book, request=request)
```

`ModelUtil` remains available internally but is no longer the documented
application-facing API. It should eventually be exposed as `_util` on
serializer classes.

### Sync and async naming

Follow Django's convention: the unprefixed method is synchronous and the
`a`-prefixed method is asynchronous.

| Concern | Sync | Async |
| --- | --- | --- |
| Create | `create()` | `acreate()` |
| Retrieve | `get()` | `aget()` |
| Update | `update()` | `aupdate()` |
| Delete | `destroy()` | `adestroy()` |
| Serialize one | `dump()` | `adump()` |
| Serialize many | `dumps()` | `adumps()` |
| Bulk create | `bulk_create()` | `abulk_create()` |
| Bulk update | `bulk_update()` | `abulk_update()` |
| Bulk delete | `bulk_destroy()` | `abulk_destroy()` |

Use `destroy` rather than `delete` so the class-level operation does not
replace Django model instances' existing `delete()`/`adelete()` behavior.

Do not add an `afilter()` method. Django querysets are lazy, so building a
queryset does not perform database I/O. Execution methods receive explicit
sync/async variants instead.

### Return contracts

Keep persistence and representation separate:

- `create`/`acreate` return a model instance.
- `get`/`aget` return a model instance.
- `update`/`aupdate` return a model instance.
- `destroy`/`adestroy` return `None`.
- `dump`/`adump` return `dict[str, Any]`.
- `dumps`/`adumps` return `list[dict[str, Any]]`.
- Bulk operations return a typed `BulkResult`, not a tuple.

This prevents a method from returning a model in one context and serialized
data in another. Generated viewsets will compose persistence and dumping.

### Schema method names

Replace the `_s` schema methods with descriptive names:

| Version 2 | Version 3 |
| --- | --- |
| `generate_create_s()` | `create_schema()` |
| `generate_update_s()` | `update_schema()` |
| `generate_read_s()` | `read_schema()` |
| `generate_detail_s()` | `detail_schema()` |
| `generate_related_s()` | `related_schema()` |

Schema generation remains synchronous because it performs no database I/O.

### Optional request context

The request must be optional and keyword-only on public operations:

```python
Book.create(data, request=request)
await Book.acreate(data, request=request)
```

This permits the same API in Ninja views, traditional Django views,
management commands, Django Admin, jobs, scripts, and tests. Operations that
require request-scoped behavior must fail with a precise configuration error
when no request is supplied.

### Documentation is a product surface

The version 3 documentation will be redesigned rather than merely updated.
The current site is strongly centered on the async-only API, exposes
`ModelUtil` as a primary concept, splits the first-run experience across two
quick starts, duplicates some navigation topics, and largely organizes the
reference around internal modules.

The new site should:

- Lead with the serializer-first mental model.
- Present sync and async examples together without duplicating entire pages.
- Organize guides around user goals rather than source-code layout.
- Keep tutorials, how-to guides, explanations, API reference, and migration
  material visibly distinct.
- Treat accessibility, responsive behavior, search, link stability, and page
  performance as release requirements.
- Preserve version 2 documentation while version 3 becomes the default.

## Phase 0: Freeze and specify the contract

Before changing implementation code:

1. Add contract tests containing the complete public method matrix.
2. Define positional and keyword-only parameters for every method.
3. Define behavior when `request`, input schema, output schema, or instance is
   omitted.
4. Record exact return types and exception types.
5. Decide which current names disappear in 3.0 and which remain as temporary
   deprecated aliases.
6. Capture the current query counts for create, retrieve, update, dump,
   nested writes, and bulk operations.

Deliverable: failing public-contract tests plus an API reference table.

## Phase 1: Separate shared logic from I/O

Refactor `ModelUtil` without changing observable behavior:

1. Extract pure payload parsing, field inspection, relation discovery,
   validation, error formatting, and output transformation.
2. Separate database reads/writes from those pure transformations.
3. Remove calls where a sync implementation is merely hidden inside
   `sync_to_async` when Django provides a native async ORM method.
4. Keep query optimization and relation-prefetch planning shared.
5. Preserve query counts and transactional behavior with regression tests.

The target structure is conceptually:

```text
shared operation rules
├── native synchronous database executor
└── native asynchronous database executor
```

Avoid implementing the complete sync API with `async_to_sync()` or the
complete async API with `sync_to_async()`. Adapters may be used at isolated
boundaries where Django or a user hook only offers one execution mode.

Deliverable: internal sync/async executors with the existing test suite still
passing.

## Phase 2: Add the serializer facade

Add the public methods to the shared serializer base so they are available on
both serializer styles:

```python
Book.create(...)
Book.acreate(...)

BookSerializer.create(...)
BookSerializer.acreate(...)
```

Tasks:

1. Add typed class-level CRUD and dump methods.
2. Move current standalone `Serializer.create()` and `Serializer.update()`
   implementation details behind private instance methods.
3. Keep instance hooks internal to the operation executor.
4. Retain Django model instance `save`, `asave`, `delete`, and `adelete`
   unchanged.
5. Rename the attached utility to `_util` after all internal consumers stop
   using the public `.util` attribute.
6. Update `APIViewSet` to use the serializer facade rather than `model_util`
   for CRUD execution.

The current instance-bound standalone serializer API needs explicit migration
coverage. In 3.0, CRUD is class-level; model instance methods such as
`has_changed()` and lifecycle hooks may remain instance-level.

Deliverable: serializer-first CRUD works for both `ModelSerializer` and the
standalone generic `Serializer[Model]`.

## Phase 3: Add native sync/async parity

Implement and verify both execution modes for:

1. Single-object CRUD.
2. Single and collection dumping.
3. Foreign-key and reverse-relation resolution.
4. Nested creates.
5. Bulk operations.
6. Permission/queryset hooks.
7. Reactive hooks.
8. Transaction management and rollback.

Hook invocation rules:

- Sync operations may execute regular hooks directly.
- Async operations may await async hooks directly.
- A sync operation may bridge an async hook at the isolated hook boundary.
- An async operation may bridge a sync hook at the isolated hook boundary.
- Exceptions and ordering must be identical in both modes.

Add parity tests that run the same scenario against both implementations and
compare results, database state, hook order, exceptions, and query counts.

Deliverable: the sync and async contract suites cover equivalent behavior.

## Phase 4: Rename schema and dump APIs

1. Add `create_schema`, `update_schema`, `read_schema`, `detail_schema`, and
   `related_schema`.
2. Add `dump`/`dumps` and `adump`/`adumps`.
3. Update internal schema generation, nested relations, views, MCP
   introspection, tests, examples, and documentation.
4. Ensure generated schemas preserve their existing names so OpenAPI client
   generation does not change accidentally.
5. Add cache-equivalence tests for every renamed schema factory.

Deliverable: no internal production code depends on an `_s` method.

## Phase 5: Introduce typed bulk results

Replace `(successes, errors)` tuples with a stable result object:

```python
BulkResult[T](
    succeeded=[...],
    failed=[...],
)
```

The result should expose:

- `succeeded`
- `failed`
- `has_errors`
- `success_count`
- `failure_count`

Each failure should include the source index, a stable error code, a message,
field details, and the relevant primary key when available.

Deliverable: viewsets and direct callers consume `BulkResult`; wire response
compatibility is either retained or documented as an intentional break.

## Phase 6: Normalize errors and operation context

Introduce a shared `OperationContext` containing, at minimum:

```python
context.request
context.operation
context.serializer
context.instance
context.data
context.changed_fields
```

Normalize public exceptions around a stable base error carrying:

- `code`
- `message`
- `status`
- structured field errors
- nested field paths

The HTTP exception handler and direct Python API should expose the same error
information without forcing non-HTTP callers to understand response objects.

Deliverable: consistent exceptions for sync, async, direct, viewset, nested,
and bulk operations.

## Phase 7: Complete configuration cleanup

Unify schema configuration across model-bound and standalone serializers.
The proposed public form is:

```python
class Schemas:
    create = SchemaConfig(...)
    update = SchemaConfig(...)
    read = SchemaConfig(...)
    detail = SchemaConfig(...)
```

Tasks:

1. Prototype the configuration on both serializer types.
2. Validate configuration during Django startup.
3. Report unknown fields, invalid relations, and incompatible options early.
4. Retain generated-schema caching.
5. Determine whether legacy nested classes and `Meta.schema_*` settings are
   removed or supported through a compatibility parser.

This phase should only proceed after the serializer facade is stable; it is a
separate migration concern and should not block early API work.

Deliverable: one documented configuration language for both serializer
styles.

## Phase 8: Views, integrations, and public exports

1. Migrate generated CRUD and bulk view functions to async facade methods.
2. Migrate mixins, custom actions, routers, Admin integration, and MCP tools.
3. Establish a small supported top-level import surface.
4. Move internal types out of public documentation.
5. Verify OpenAPI schemas and operation IDs against stored snapshots.
6. Verify soft delete, field selection, permissions, pagination, filtering,
   and nested writes in both sync and async contexts where applicable.

Proposed common imports:

```python
from ninja_aio import APIViewSet, ModelSerializer, SchemaConfig, Serializer
```

Deliverable: internal integrations no longer call deprecated utilities.

## Phase 9: Redesign the documentation site

Treat the docsite as its own design and engineering workstream.

### Content and audience discovery

1. Inventory every existing page and mark it as keep, rewrite, merge, move,
   archive, or delete.
2. Define the primary journeys: first API, existing Django project,
   serializer choice, sync usage, async usage, customization, troubleshooting,
   and 2.x migration.
3. Identify concepts that belong in public documentation and remove internal
   implementation details such as routine `ModelUtil` usage.
4. Review search terms, common issues, and repeated examples to identify
   missing entry points.

### New information architecture

Use a task-oriented top-level structure:

```text
Home
Get started
Tutorial
Guides
Concepts
API reference
Migration to v3
Project
```

The proposed content groups are:

- **Get started:** installation, one canonical quick start, serializer choice,
  and a five-minute sync/async example.
- **Tutorial:** one progressive application from model to production-ready
  API.
- **Guides:** schemas, CRUD, dumping, relations, nested writes, filtering,
  pagination, auth, permissions, hooks, bulk operations, Admin, and MCP.
- **Concepts:** serializer-first architecture, operation context, sync versus
  async, transactions, errors, and query optimization.
- **API reference:** concise, generated where reliable, and separated from
  narrative documentation.
- **Migration:** automated checks, renamed methods, changed returns, recipes,
  and a complete compatibility table.
- **Project:** releases, benchmarks, deployment, troubleshooting, and
  contributing.

### Visual redesign

This is a full visual redesign, not a new palette applied to the existing
theme. The old page chrome and component styling are not compatibility
constraints.

1. Produce two or three lightweight visual directions before implementing the
   theme. Each direction must cover the homepage, one long-form guide, a code
   example, navigation, and both color schemes.
2. Establish or refresh the product identity: wordmark treatment, color
   system, typography, iconography, illustration style, voice, and motion.
   Redesigning the logo itself remains a separate explicit decision.
3. Define design tokens for typography, spacing, layout widths, color,
   borders, radii, elevation, code syntax, callouts, and light/dark themes.
4. Replace the visible MkDocs Material shell with custom templates for the
   header, desktop and mobile navigation, search entry point, announcement,
   table of contents, footer, and page-level navigation.
5. Redesign the homepage around one clear value proposition, a runnable code
   example, the sync/async story, and direct learning paths.
6. Replace the current feature-card and badge-heavy hierarchy with fewer,
   stronger sections and a more deliberate editorial layout.
7. Create a small reusable component system for code samples, sync/async tabs,
   callouts, API signatures, compatibility notices, feature comparisons,
   steps, cards, and migration tables.
8. Create distinct but related page templates for tutorials, guides,
   concepts, reference, migration, releases, and benchmarks.
9. Remove obsolete selectors and one-off presentation rules from
   `docs/extra.css`; split the new styles by tokens, shell, components, and
   pages so the theme remains maintainable.
10. Keep MkDocs Material as the content/build foundation unless the prototype
    identifies a concrete limitation that justifies changing stacks. Keeping
    it does not require retaining its default visual identity.

The visual direction must not be chosen solely in CSS. Approve a homepage and
one representative documentation page first, then derive the shared theme.

### Documentation behavior

1. Use linked sync/async code tabs where examples differ.
2. Add copyable minimal examples that are exercised by tests or documentation
   snippets in CI.
3. Add previous/next learning navigation and explicit prerequisites.
4. Provide version and migration notices on every relevant 2.x page.
5. Preserve intentional URLs or add redirects for moved high-traffic pages.
6. Improve local search labels, page titles, descriptions, and social preview
   metadata.

### Quality gates

The redesigned site must pass:

- WCAG-oriented color contrast, focus, keyboard, landmark, and heading checks.
- Mobile layouts for navigation, tables, tabs, code blocks, and callouts.
- Internal-link and anchor validation.
- Documentation build with warnings treated as errors where practical.
- Code-example validation against the version 3 API.
- A performance budget for the homepage and representative content pages.
- Visual regression coverage for the homepage and core page templates.

Deliverable: a versioned, accessible, responsive docsite that teaches version
3 from first principles and retains discoverable version 2 documentation.

## Phase 10: Migration tooling and documentation

1. Publish a method-by-method 2.x to 3.0 migration table.
2. Add before/after examples for model-bound and standalone serializers.
3. Document sync and async usage side by side.
4. Document return-contract changes, especially CRUD no longer returning
   serialized dictionaries.
5. Document `delete_s` to `destroy`/`adestroy` and explain the Django method
   collision.
6. Add a script or lint rule that detects common removed method names where
   practical.
7. Update README, tutorials, API reference, type-hint guide, changelog, and
   release notes.

If a final 2.x compatibility release is published, introduce the new async
names there where possible and emit `DeprecationWarning` with `stacklevel=2`
from old entry points. Do not silently change an existing method from async to
sync in a 2.x release.

Deliverable: a project can migrate without reading implementation code.

## Phase 11: Release validation

The 3.0 release candidate must pass:

1. Full unit and integration suite.
2. Sync/async parity suite.
3. Static type-check examples for concrete model return types.
4. Supported Python and Django version matrix.
5. OpenAPI snapshot comparison.
6. Performance and query-count comparison against 2.36.
7. Package build and clean-environment installation.
8. Documentation build with no broken internal links.
9. At least one sample application migrated from 2.x.
10. Accessibility, responsive, visual-regression, and performance checks for
    the redesigned docsite.

Only bump `ninja_aio.__version__` to `3.0.0` when the migration guide and all
release gates are complete.

## Approval, commit, and push protocol

Implementation proceeds through the numbered steps below, one step at a time.
Every step uses the following mandatory gate:

1. Implement only the scope of the active step.
2. Run the targeted checks and the broader regression suite appropriate to
   that step.
3. Report the changed files, behavior, design decisions, test results, known
   limitations, and proposed commit message.
4. Stop with the changes uncommitted and request explicit approval.
5. If changes are requested, revise the same step, rerun checks, report the
   new result, and request approval again.
6. Only after explicit approval, commit the approved diff and push it to
   `origin/feat/v3-api-redesign`.
7. Report the commit hash and push result, then stop before beginning the next
   step.

Never combine the approval of one step with implementation of the next. Never
amend, squash, force-push, or rewrite an approved commit unless explicitly
requested.

## Granular implementation sequence

Each step must leave the branch in a coherent, testable state.

### Step 0: Approve the version 3 plan

- Review and approve this implementation plan.
- Commit and push the plan as the branch baseline.
- No production behavior changes.

### Step 1: Freeze the public contracts

- Add the public API signature and return-type specification.
- Add contract-test scaffolding for both serializer styles.
- Record compatibility decisions for every version 2 public method.
- Capture baseline tests, query counts, OpenAPI snapshots, and benchmarks.

### Step 2: Add the new schema factory names

- Add `create_schema`, `update_schema`, `read_schema`, `detail_schema`, and
  `related_schema` as additive APIs.
- Preserve generated schema identity, caching, and OpenAPI names.
- Keep old `_s` methods functional until the removal step.

### Step 3: Separate shared transformations from database I/O

- Extract payload parsing, validation, relation planning, and output
  transformation into execution-mode-independent helpers.
- Preserve all existing behavior and query counts.
- Do not expose new CRUD methods yet.

### Step 4: Add the async serializer facade for single-object CRUD

- Add `acreate`, `aget`, `aupdate`, and `adestroy`.
- Return model instances according to the version 3 contract.
- Support both `ModelSerializer` and `Serializer[Model]`.
- Keep the existing version 2 paths operational.

### Step 5: Add native synchronous single-object CRUD

- Add `create`, `get`, `update`, and `destroy`.
- Use native synchronous ORM operations.
- Add sync/async parity tests for state, hooks, errors, transactions, and
  queries.

### Step 6: Add the dump APIs

- Add `dump`, `dumps`, `adump`, and `adumps`.
- Define and test relation-loading behavior explicitly.
- Preserve custom fields, nested output, optional schemas, and output
  transformations.

### Step 7: Normalize operation context and hooks

- Introduce `OperationContext`.
- Normalize lifecycle hook names and ordering.
- Support regular and async hooks at isolated invocation boundaries.
- Add ordering, exception, rollback, and changed-field parity tests.

### Step 8: Add sync/async bulk parity

- Add `bulk_create`/`abulk_create`, `bulk_update`/`abulk_update`, and
  `bulk_destroy`/`abulk_destroy`.
- Preserve partial-success and per-item transaction semantics.
- Verify foreign-key caching and nested-write rollback in both modes.

### Step 9: Introduce structured errors and `BulkResult`

- Add the common error contract and nested field paths.
- Replace public success/error tuples with typed results.
- Preserve or explicitly migrate the existing HTTP wire format.

### Step 10: Migrate generated viewsets

- Switch CRUD and bulk views to the async serializer facade.
- Remove routine `model_util` use from view code.
- Verify response schemas, status codes, permissions, filters, pagination,
  field selection, soft delete, and OpenAPI snapshots.

### Step 11: Migrate framework integrations

- Migrate routers, decorators, actions, Admin integration, authentication
  touchpoints, and MCP introspection/invocation.
- Establish and test the supported top-level import surface.

### Step 12: Unify serializer configuration

- Introduce the shared `Schemas`/`SchemaConfig` configuration language.
- Support both model-bound and standalone serializers.
- Add startup validation with actionable configuration errors.
- Implement the approved legacy-configuration migration policy.

### Step 13: Remove version 2 APIs from the version 3 surface

- Remove approved deprecated aliases and public `.util` access.
- Retain `_util` only where required internally.
- Run the complete suite, typing examples, benchmarks, and package build.

### Step 14: Redesign the documentation architecture

- Complete the page inventory and audience/task analysis.
- Approve the new sitemap, URL migration map, page templates, and content
  ownership matrix.
- Do not change the live visual theme in this step.

### Step 15: Approve the visual direction

- Produce two or three distinct homepage and documentation-page concepts.
- Compare typography, palette, density, navigation, code presentation, light
  and dark themes, responsive behavior, and brand character.
- Select one direction before writing the production theme.

### Step 16: Implement the docsite design system and shell

- Add tokens, typography, layout primitives, header, navigation, search,
  table of contents, footer, theme switching, and shared components.
- Remove superseded legacy CSS and template overrides.
- Add accessibility and visual-regression baselines.

### Step 17: Implement the new homepage

- Build the approved homepage composition.
- Add the primary code example, sync/async story, learning paths, project
  proof points, and calls to action.
- Validate mobile behavior, performance, metadata, and accessibility.

### Step 18: Implement documentation page templates

- Implement tutorial, guide, concept, reference, migration, release, and
  benchmark page patterns.
- Add sync/async tabs, API signatures, compatibility notices, steps, callouts,
  and previous/next learning navigation.

### Step 19: Rewrite and migrate the documentation content

- Rewrite the canonical quick start and progressive tutorial.
- Migrate guides and API reference to the version 3 contract.
- Publish the complete 2.x migration guide.
- Preserve version 2 documentation and add redirects/version notices.

### Step 20: Release-candidate validation

- Run the complete functional, parity, typing, packaging, documentation,
  accessibility, visual, performance, and supported-version matrices.
- Migrate the sample application.
- Update version, changelog, and release notes only after every gate passes.

## Explicit non-goals for 3.0

Do not delay the API redesign for unrelated feature work. Multi-tenancy,
aggregation endpoints, file uploads, ETags, idempotency, exports, dashboards,
webhooks, and other roadmap items can ship in later 3.x releases.

Nested update strategies and optimistic locking are strong 3.x candidates,
but should only enter 3.0 if the core facade and sync/async parity are already
stable.

## Definition of done

Version 3.0 is complete when:

- Common application code does not need `.util` or `ModelUtil`.
- Every supported database operation has an intentional sync/async contract.
- Public CRUD methods return predictable model-oriented results.
- Serialization uses `dump`/`dumps` and `adump`/`adumps` consistently.
- Schema factories no longer use the `_s` suffix.
- Django model instance behavior remains intact.
- Generated viewsets and integrations use the new public contract.
- Errors, hooks, transactions, and query behavior have sync/async parity.
- Migration documentation covers every removed or behavior-changing API.
- The docsite has a complete version 3 visual system rather than a restyled
  version of the current homepage, while version 2 documentation remains
  accessible.
- Tests, types, documentation, packaging, and performance gates pass.
