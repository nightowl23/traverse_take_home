# Add Check Maintenance Windows

The Healthchecks codebase is at `/app/`. It's a Django app for monitoring cron jobs.

## What to build

Add maintenance windows to checks so users can schedule planned downtime periods. During a maintenance window, the check's status should report as `"paused"` regardless of its underlying state. This lets users avoid false alerts during deployments, server maintenance, etc.

## 1. `MaintenanceWindow` model (`/app/hc/api/models.py`)

New model with these fields:

| Field | Type | Details |
|-------|------|---------|
| `code` | `UUIDField` | `default=uuid.uuid4, editable=False, unique=True` |
| `owner` | `ForeignKey` to `Check` | `on_delete=models.CASCADE, related_name="maintenance_windows"` |
| `title` | `CharField` | `max_length=100` |
| `start_time` | `DateTimeField` | |
| `end_time` | `DateTimeField` | |
| `created` | `DateTimeField` | `default=now` |

Add `to_dict()` returning: `uuid`, `title`, `start_time` (ISO 8601, no microseconds), `end_time` (ISO 8601, no microseconds), `created` (ISO 8601, no microseconds).

Add `is_active()` method that returns `True` if `now()` is >= `start_time` and < `end_time`.

`Meta` class: `ordering = ["-created"]`.

## 2. `Check.is_in_maintenance()` method (`/app/hc/api/models.py`)

Add a method on the `Check` model that returns `True` if any of the check's maintenance windows are currently active. Use a database query: filter `maintenance_windows` where `start_time__lte=now()` and `end_time__gt=now()`, then call `.exists()`.

## 3. Modify `Check.get_status()` (`/app/hc/api/models.py`)

At the very beginning of `get_status()`, before the `frozen_now = now()` line, add:

```python
if self.is_in_maintenance():
    return "paused"
```

This ensures that during a maintenance window, the check always appears paused.

## 4. `Check.to_dict()` (`/app/hc/api/models.py`)

Add `"in_maintenance"` (boolean, result of `self.is_in_maintenance()`) to the dict returned by `to_dict()`. Insert it before the `if self.kind == "simple":` block.

## 5. Migration (`/app/hc/api/migrations/`)

Generate with `python manage.py makemigrations api`.

## 6. API endpoints (`/app/hc/api/views.py`)

### `POST /api/v3/checks/<uuid:code>/maintenance/`

Create a maintenance window.

- Use `@authorize` (write key required)
- JSON body: `title` (required, string, max 100), `start_time` (required, ISO 8601 datetime string), `end_time` (required, ISO 8601 datetime string)
- Validate that `title` is present and non-empty (after stripping whitespace)
- Validate that `title` is a string (return `400` if not)
- Validate `title` length <= 100 chars
- Validate that `start_time` and `end_time` are present and are valid ISO 8601 datetime strings
- Validate that `end_time` is strictly after `start_time`
- Return the maintenance window JSON with status `201`
- `400` for validation errors (with `{"error": "..."}`)
- `403` if check is in a different project
- `404` if check doesn't exist
- Max 10 maintenance windows per check. Return `403` with `{"error": "too many maintenance windows"}` if at limit

### `GET /api/v3/checks/<uuid:code>/maintenance/`

List maintenance windows for a check.

- Use `@authorize_read`
- Returns `{"maintenance_windows": [...]}`, newest first
- `403` if wrong project, `404` if check doesn't exist

Wire these up with a dispatcher called `check_maintenance` that sends GET to the list handler and POST to the create handler. Decorate with `@csrf_exempt` and `@cors("GET", "POST")`.

### `DELETE /api/v3/checks/<uuid:code>/maintenance/<uuid:window_code>/`

Delete a specific maintenance window.

- Use `@authorize` (write key required, via header `X-Api-Key`)
- `404` if check or maintenance window doesn't exist
- `403` if check is in a different project
- Return `200` with `{"ok": true}`

Create a view called `check_maintenance_detail`. Decorate with `@cors("DELETE")`, `@csrf_exempt`, and `@authorize`.

## 7. URL routes (`/app/hc/api/urls.py`)

Add to the `api_urls` list (works across v1/v2/v3 automatically):

```
path("checks/<uuid:code>/maintenance/", views.check_maintenance, name="hc-api-maintenance"),
path("checks/<uuid:code>/maintenance/<uuid:window_code>/", views.check_maintenance_detail, name="hc-api-maintenance-detail"),
```

## Constraints

- Don't modify existing tests
- Maintenance window limit is 10 per check
- Use `isostring()` for datetime formatting (already in the codebase)
- Follow existing patterns for decorators, error responses, etc.
