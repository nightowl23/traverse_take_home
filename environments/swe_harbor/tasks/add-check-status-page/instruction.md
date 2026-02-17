# Add Public Status Pages

The Healthchecks codebase is at `/app/`. It's a Django app for monitoring cron jobs.

## What to build

Add a status page system that lets users create public (or private) status pages for their projects. A status page aggregates the health of selected checks and exposes it as a JSON endpoint. Public status pages can be accessed without authentication via a slug-based URL.

## 1. `StatusPage` model (`/app/hc/api/models.py`)

New model with these fields:

| Field | Type | Details |
|-------|------|---------|
| `code` | `UUIDField` | `default=uuid.uuid4, editable=False, unique=True` |
| `project` | `ForeignKey` to `Project` | `on_delete=models.CASCADE, related_name="status_pages"` |
| `name` | `CharField` | `max_length=100` |
| `slug` | `SlugField` | `max_length=100, unique=True` |
| `description` | `TextField` | `blank=True, default=""` |
| `checks` | `ManyToManyField` to `Check` | `blank=True, related_name="status_pages"` |
| `is_public` | `BooleanField` | `default=False` |
| `created` | `DateTimeField` | `default=now` |

Add `aggregate_status()` method that calculates the overall status across all associated checks:
- If no checks are assigned, return `"no_checks"`
- Collect each check's status via `check.get_status()`
- If any check is `"down"`, return `"down"`
- If any check is `"grace"`, return `"grace"`
- If any check is `"up"`, return `"up"`
- Otherwise (all paused/new), return `"paused"`

Add `to_dict()` returning:
```python
{
    "uuid": str(self.code),
    "name": self.name,
    "slug": self.slug,
    "description": self.description,
    "is_public": self.is_public,
    "created": isostring(self.created),
    "checks": [str(c.code) for c in self.checks.all()],
    "status": self.aggregate_status(),
}
```

`Meta` class: `ordering = ["-created"]`.

## 2. `Project.num_status_pages_available()` method (`/app/hc/accounts/models.py`)

Add a method on the `Project` model that returns how many more status pages the project can create. The limit is 5 status pages per project:

```python
def num_status_pages_available(self) -> int:
    from hc.api.models import StatusPage
    return 5 - StatusPage.objects.filter(project=self).count()
```

Add it right after the existing `num_checks_available` method.

## 3. Migration (`/app/hc/api/migrations/`)

Generate with `python manage.py makemigrations api`.

## 4. API endpoints (`/app/hc/api/views.py`)

### `POST /api/v3/status-pages/`

Create a status page.

- Use `@authorize` (write key required)
- JSON body:
  - `name` (required, string, max 100)
  - `slug` (required, string, must be a valid slug — lowercase letters, numbers, hyphens; max 100)
  - `description` (optional, string)
  - `checks` (optional, list of UUID strings — must all belong to the same project)
  - `is_public` (optional, boolean, default `False`)
- Validation:
  - `name` must be present and non-empty after stripping; return `400` with `{"error": "name is required"}`
  - `name` must be <= 100 characters; return `400` with `{"error": "name is too long"}`
  - `slug` must be present and non-empty; return `400` with `{"error": "slug is required"}`
  - `slug` must match `^[a-z0-9-]+$`; return `400` with `{"error": "invalid slug format"}`
  - `slug` must be unique; return `400` with `{"error": "slug already in use"}`
  - `slug` must be <= 100 characters; return `400` with `{"error": "slug is too long"}`
  - If `checks` is provided, each UUID must be valid and the corresponding check must belong to the authenticated project; return `400` with `{"error": "invalid or unauthorized check uuid"}` if not
  - If `is_public` is provided, it must be a boolean; return `400` with `{"error": "is_public must be a boolean"}`
  - If the project has reached the 5 status page limit, return `403` with `{"error": "too many status pages"}`
- Return the status page JSON with status `201`

### `GET /api/v3/status-pages/`

List status pages for the authenticated project.

- Use `@authorize_read`
- Returns `{"status_pages": [...]}`

### `GET /api/v3/status-pages/<uuid:code>/`

Get a single status page.

- Use `@authorize_read`
- `403` if the status page belongs to a different project
- `404` if not found
- Returns the status page JSON

### `DELETE /api/v3/status-pages/<uuid:code>/`

Delete a status page.

- Use `@authorize` (write key required, via header `X-Api-Key`)
- `403` if the status page belongs to a different project
- `404` if not found
- Returns `{"ok": true}`

Wire up dispatchers:
- `status_pages` dispatcher: sends GET to list handler, POST to create handler. Decorate with `@csrf_exempt` and `@cors("GET", "POST")`.
- `status_page_detail` dispatcher: sends GET to get handler, DELETE to delete handler. Decorate with `@csrf_exempt` and `@cors("GET", "DELETE")`.

### `GET /api/v3/status-pages/public/<slug:slug>/`

Public endpoint — **no authentication required**.

- If the status page with this slug exists and `is_public` is `True`, return the status page JSON with status `200`
- If the status page doesn't exist or `is_public` is `False`, return `404`

Create a view called `status_page_public`. Decorate with `@csrf_exempt` and `@cors("GET")`.

## 5. URL routes (`/app/hc/api/urls.py`)

Add to the `api_urls` list (works across v1/v2/v3 automatically):

```
path("status-pages/", views.status_pages, name="hc-api-status-pages"),
path("status-pages/public/<slug:slug>/", views.status_page_public, name="hc-api-status-page-public"),
path("status-pages/<uuid:code>/", views.status_page_detail, name="hc-api-status-page-detail"),
```

## Constraints

- Don't modify existing tests
- Status page limit is 5 per project
- Slugs must be lowercase alphanumeric with hyphens only
- Use `isostring()` for datetime formatting (already in the codebase)
- Follow existing patterns for decorators, error responses, etc.
- Import `Project` from `hc.accounts.models` (already imported in views.py)
