# Add Bulk Check Operations API

The Healthchecks codebase is at `/app/`. It's a Django app for monitoring cron jobs.

## What to build

Add an API endpoint for performing bulk operations on checks within a project — bulk pause, bulk resume, bulk delete, and bulk tag updates. Currently, users must operate on checks one at a time; this feature lets them act on many checks in a single request.

## 1. `Check.to_dict()` update (`/app/hc/api/models.py`)

Add `"tags_list"` to the dict returned by `to_dict()`. It should be a list of strings produced by splitting the `tags` field on whitespace and stripping each item (same logic as the existing `tags_list()` method). Insert it right after the existing `"tags"` key assignment. Example: if `tags` is `"prod web"`, then `tags_list` should be `["prod", "web"]`. If `tags` is empty, `tags_list` should be `[]`.

## 2. API endpoint (`/app/hc/api/views.py`)

### `POST /api/v3/checks/bulk/`

Perform a bulk operation on multiple checks.

- Use `@authorize` (write key required)
- Decorate the view `bulk_actions` with `@cors("POST")`, `@csrf_exempt`, and `@authorize`
- JSON body:
  - `action` (required): one of `"pause"`, `"resume"`, `"delete"`, `"add_tags"`
  - `checks` (required): list of UUID strings identifying the checks to act on
  - `tags` (required only for `"add_tags"` action): space-separated tag string to add

#### Validation

1. If `action` is missing or not one of the four valid values, return `400` with `{"error": "invalid action"}`
2. If `checks` is missing or not a list, return `400` with `{"error": "checks must be a list"}`
3. If `checks` is empty, return `400` with `{"error": "checks list is empty"}`
4. If `checks` has more than 50 items, return `400` with `{"error": "too many checks (max 50)"}`
5. If any UUID in `checks` is not a valid UUID string, return `400` with `{"error": "invalid uuid in checks list"}`
6. Fetch all checks matching the provided UUIDs that also belong to the authenticated project. If the count of found checks doesn't equal the count of provided UUIDs, return `400` with `{"error": "some checks not found or not in this project"}`

#### Actions

**`pause`**: For each check, follow the existing `pause()` view's logic:
- Create a flip via `check.create_flip("paused", mark_as_processed=True)`
- Set `status = "paused"`, `last_start = None`, `alert_after = None`
- Save the check

**`resume`**: For each check, follow the existing `resume()` view's logic:
- Skip any check whose status is not `"paused"` (don't error, just skip it)
- Create a flip via `check.create_flip("new", mark_as_processed=True)`
- Set `status = "new"`, `last_start = None`, `last_ping = None`, `alert_after = None`
- Save the check

**`delete`**: For each check, call `check.lock_and_delete()`

**`add_tags`**: 
- If `tags` is missing, not a string, or empty after stripping, return `400` with `{"error": "tags is required for add_tags action"}`
- For each check, merge the new tags (split on whitespace) with the check's existing tags (from `tags_list()`), sort the result, join with spaces, and save

#### Response

On success, return `200` with `{"success": true, "count": N}` where N is the number of checks that were acted upon. For `resume`, N is the number of checks that were actually resumed (i.e., were in `"paused"` status).

## 3. URL routes (`/app/hc/api/urls.py`)

Add to the `api_urls` list (works across v1/v2/v3 automatically):

```
path("checks/bulk/", views.bulk_actions, name="hc-api-bulk"),
```

Place this **before** the existing `checks/<uuid:code>` route to avoid URL conflicts.

## Constraints

- Don't modify existing tests
- Maximum 50 checks per bulk operation
- Follow existing patterns for decorators, error responses, etc.
- Use `lock_and_delete()` for deletes (not plain `.delete()`)
- The `resume` action should skip non-paused checks silently (not error)
