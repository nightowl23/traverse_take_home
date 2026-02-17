# SWE Harbor Task Authoring Guide

A practical guide to setting up the environment, understanding how tasks work, and creating your own from scratch.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Understanding the Architecture](#2-understanding-the-architecture)
3. [Anatomy of a Task](#3-anatomy-of-a-task)
4. [How the Three Tasks Were Created](#4-how-the-three-tasks-were-created)
5. [Step-by-Step: Creating a New Task](#5-step-by-step-creating-a-new-task)
6. [Writing Good Solutions (solve.sh)](#6-writing-good-solutions-solvesh)
7. [Writing Good Tests (test_solution.py)](#7-writing-good-tests-test_solutionpy)
8. [Verification Workflow](#8-verification-workflow)
9. [Common Pitfalls](#9-common-pitfalls)
10. [Quick Reference](#10-quick-reference)

---

## 1. Environment Setup

### Prerequisites

- **Docker Desktop** installed and running
- A terminal (bash or zsh)
- A code editor (VS Code, Cursor, etc.)
- Basic familiarity with Python, Django, and REST APIs

### First-Time Setup

```bash
# 1. Clone the repo and navigate to the working directory
cd take-home/environments/swe_harbor

# 2. Build the Docker image (only needed once, or after changing environment/app/)
docker build -t swe-harbor environment/

# 3. Verify the build works by running an example task
docker run --rm \
    -v $(pwd)/tasks/add-check-annotations/solution:/solution \
    -v $(pwd)/tasks/add-check-annotations/tests:/tests \
    swe-harbor \
    bash -c "mkdir -p /logs/verifier && cd /app && bash /solution/solve.sh && bash /tests/test.sh && cat /logs/verifier/reward.txt"
# Should print: 1
```

If you see `1` at the end of the output, your environment is working.

### Exploring the Codebase Interactively

To poke around the Healthchecks app inside the container:

```bash
docker run --rm -it swe-harbor bash
# Now you're inside the container at /app
ls hc/api/          # models.py, views.py, urls.py -- where most tasks live
python manage.py shell  # Django shell for testing queries
```

This is invaluable when designing a task. Spend time reading the existing code before writing anything.

---

## 2. Understanding the Architecture

### The Big Picture

```
┌─────────────────────────────────────────────────────┐
│  Docker Container (swe-harbor image)                │
│                                                     │
│  /app/                  ← Healthchecks Django app   │
│  /solution/solve.sh     ← Mounted from your task    │
│  /tests/test_solution.py← Mounted from your task    │
│  /tests/test.sh         ← Mounted from your task    │
│  /logs/verifier/reward.txt ← Output: 1 or 0        │
│                                                     │
│  Flow:                                              │
│  1. solve.sh modifies /app/ (patches code, runs     │
│     migrations)                                     │
│  2. test.sh runs pytest against test_solution.py    │
│  3. reward.txt gets "1" if all tests pass, "0" if   │
│     any fail                                        │
└─────────────────────────────────────────────────────┘
```

### What the AI Agent Sees

When deployed in the real pipeline, an AI agent receives **only** `instruction.md`. It never sees the tests or the solution. It reads the instructions, explores the codebase with tools (bash, file read/write), and tries to make the tests pass. The tests are the ground truth.

### Key Files in the Healthchecks App

| File | What It Contains |
|------|-----------------|
| `hc/api/models.py` | All data models (`Check`, `Ping`, `Channel`, `Flip`, etc.) |
| `hc/api/views.py` | API endpoint handlers (decorated with `@authorize`, etc.) |
| `hc/api/urls.py` | URL routing (`api_urls` list, versioned under `/api/v1/`, `/v2/`, `/v3/`) |
| `hc/accounts/models.py` | `Project` and `Member` models |
| `hc/test.py` | `BaseTestCase` -- provides test fixtures (`self.project`, `self.alice`, API keys) |

---

## 3. Anatomy of a Task

Every task lives in `tasks/<task-name>/` and contains exactly 5 files:

### `task.toml` -- Metadata

```toml
version = "1.0"

[metadata]
author_name = "Your Name"
author_email = "you@example.com"
difficulty = "medium"        # easy | medium | hard
category = "programming"
tags = ["python", "django", "rest-api", "validation"]

[verifier]
timeout_sec = 180.0          # How long tests can run

[agent]
timeout_sec = 900.0          # How long the AI agent gets to work
```

### `instruction.md` -- What the Agent Reads

This is the problem statement. It should be:
- **Specific**: exact field names, types, status codes, error messages
- **Structured**: numbered sections for each file that needs changes
- **Constrained**: clear limits (max items, required fields, etc.)
- **Self-contained**: the agent shouldn't need to guess anything

### `solution/solve.sh` -- The Reference Solution

A deterministic bash script that applies all changes inside the container. Patterns:
- `cat >> file << 'EOF'` to append new classes/functions
- Inline `python3 << 'PATCH'` scripts to do string replacements in existing files
- `python manage.py makemigrations` and `migrate` for new models

### `tests/test_solution.py` -- The Test Suite

Pytest tests using Django's test infrastructure. Extends `BaseTestCase` for fixtures. Should cover:
- Model creation and field defaults
- `to_dict()` output
- API happy paths (correct status codes, response bodies)
- Validation errors (400s for bad input)
- Authorization errors (401/403)
- Not found (404)
- Edge cases (limits, empty inputs, duplicates)
- URL routing across API versions (v1/v2/v3)
- CORS headers

### `tests/test.sh` -- The Test Runner

Always the same boilerplate:

```bash
#!/bin/bash
cd /app
pip install pytest > /dev/null 2>&1
mkdir -p /logs/verifier
python manage.py migrate --run-syncdb > /dev/null 2>&1

PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hc.settings pytest /tests/test_solution.py -v 2>&1
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
```

---

## 4. How the Three Tasks Were Created

Here's the thinking process behind each task, from idea to verified implementation.

### Task 1: `add-check-maintenance-windows` (hard)

**Idea**: Users need to schedule planned downtime so checks don't fire false alerts during deployments. This requires a new model *and* modifying the existing `Check.get_status()` logic -- meaning partial solutions that just add the model won't pass all tests.

**Design decisions**:
- New `MaintenanceWindow` model linked to `Check` via ForeignKey
- `is_active()` on the window, `is_in_maintenance()` on the check
- `get_status()` returns `"paused"` during active maintenance -- this is the tricky part because it requires understanding existing status calculation logic
- CRUD API: create, list, delete (no update to keep scope reasonable)
- Limit of 10 windows per check (forces validation logic)

**Why it's a good task**: The agent must read and understand `get_status()` before modifying it. Just appending new code won't work -- it needs to insert a check *before* the existing `frozen_now = now()` line.

### Task 2: `add-check-bulk-operations` (medium)

**Idea**: The existing API only operates on one check at a time. Bulk operations require careful validation (all UUIDs valid? all in the same project?) and different behavior per action.

**Design decisions**:
- Single endpoint (`POST /checks/bulk/`) with an `action` field, not separate endpoints per action
- Four actions: pause, resume, delete, add_tags -- each mimics existing single-check logic
- Resume skips non-paused checks silently (doesn't error)
- Validation is layered: check action, check list format, check UUID validity, check project ownership
- No new model (keeps it medium difficulty)

**Why it's a good task**: Lots of validation edge cases. The agent needs to read existing `pause()` and `resume()` views to replicate their exact behavior (create flips, clear fields). The URL must go *before* `checks/<uuid:code>` to avoid routing conflicts.

### Task 3: `add-check-status-page` (hard)

**Idea**: A public status page that aggregates health across multiple checks. Requires ManyToMany relationships, slug-based public URLs, and aggregate status calculation.

**Design decisions**:
- New `StatusPage` model with M2M to `Check` and FK to `Project`
- `aggregate_status()` with priority: down > grace > up > paused
- Public endpoint (`/status-pages/public/<slug>/`) requires no auth if `is_public=True`
- `num_status_pages_available()` on Project (limit of 5) -- touches a second app (`accounts`)
- Slug validation with regex

**Why it's a good task**: Touches 4 files across 2 Django apps. The public endpoint pattern (no auth) is different from every other endpoint in the codebase. M2M relationships add complexity to both the model and the create API.

### Common Pattern Across All Three

Each task was built by:
1. **Reading the codebase** to find natural extension points
2. **Identifying the patch targets** -- exact strings in models.py, views.py, urls.py that the solution script will match against
3. **Writing the instruction first** -- this forces precise thinking about the API contract
4. **Writing the solution script** -- testing each patch step
5. **Writing tests that catch partial solutions** -- e.g., model exists but `get_status()` wasn't modified
6. **Verifying both directions** -- solution passes, no-solution fails

---

## 5. Step-by-Step: Creating a New Task

### Step 1: Pick a Feature

Browse the Healthchecks codebase interactively:

```bash
docker run --rm -it swe-harbor bash
cd /app
# Read models to find extension points
less hc/api/models.py
# Read views to understand API patterns
less hc/api/views.py
# Read urls to understand routing
less hc/api/urls.py
```

Good features touch 3+ files and require understanding existing code. Ask yourself: "Would a partial solution (e.g., model without API) pass my tests?" If yes, add more tests.

### Step 2: Copy the Template

```bash
cd environments/swe_harbor/tasks
cp -r _template my-new-task
```

### Step 3: Write `instruction.md`

Start with the instruction, not the solution. This forces you to think precisely about the API contract. Use tables for model fields, specify exact status codes and error messages, and note which decorators to use.

Look at the existing instructions for formatting conventions:
- Numbered sections per file
- Field tables with Type and Details columns
- Code blocks for URL patterns
- A Constraints section at the end

### Step 4: Write `solution/solve.sh`

The solution must be deterministic -- no randomness, no network calls. Key techniques:

**Appending new classes** (for new models, views):
```bash
cat >> /app/hc/api/models.py << 'PYEOF'
class MyModel(models.Model):
    ...
PYEOF
```

**Patching existing code** (for modifying `to_dict()`, `get_status()`, etc.):
```bash
python3 << 'PATCH'
with open("hc/api/models.py", "r") as f:
    content = f.read()

old = '''    exact string to find
    including indentation'''

new = '''    replacement string
    with your additions'''

content = content.replace(old, new, 1)

with open("hc/api/models.py", "w") as f:
    f.write(content)
PATCH
```

**Critical**: The `old` string must exactly match the source code, including whitespace and indentation. Copy it directly from the codebase.

**Adding URL routes** (always insert before an existing line):
```bash
python3 << 'PATCH'
with open("hc/api/urls.py", "r") as f:
    content = f.read()

old = '    path("channels/", views.channels),'
new = '''    path("my-endpoint/", views.my_view, name="hc-api-mine"),
    path("channels/", views.channels),'''

content = content.replace(old, new, 1)

with open("hc/api/urls.py", "w") as f:
    f.write(content)
PATCH
```

**Running migrations** (always at the end):
```bash
cd /app
python manage.py makemigrations api --name mymodel 2>&1
python manage.py migrate 2>&1
```

### Step 5: Write `tests/test_solution.py`

Start with the boilerplate:

```python
"""Tests for the My Feature feature."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta as td

from django.test import TestCase
from django.utils.timezone import now

import os
import sys
sys.path.insert(0, "/app")
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hc.settings")
django.setup()

from hc.api.models import Check
from hc.test import BaseTestCase
```

`BaseTestCase` gives you:
- `self.project` -- Alice's project
- `self.bobs_project` -- Bob's project
- `self.charlies_project` -- Charlie's project
- `self.alice`, `self.bob`, `self.charlie` -- User objects
- API key `"X" * 32` authenticates as Alice's project

Organize tests by category:

```python
class MyModelTestCase(BaseTestCase):
    """Model-level tests."""
    # test_create, test_to_dict, test_ordering, test_cascade_delete, etc.

class MyCreateApiTestCase(BaseTestCase):
    """POST endpoint tests."""
    # test_happy_path, test_missing_field, test_wrong_api_key, etc.

class MyListApiTestCase(BaseTestCase):
    """GET endpoint tests."""
    # test_list_empty, test_list_items, test_wrong_project, etc.

class MyUrlRoutingTestCase(BaseTestCase):
    """URL routing across API versions."""
    # test_v1, test_v2, test_v3, test_options_request
```

### Step 6: Fill in `task.toml`

```toml
version = "1.0"

[metadata]
author_name = "Your Name"
author_email = "you@example.com"
difficulty = "medium"
category = "programming"
tags = ["python", "django", "rest-api"]

[verifier]
timeout_sec = 180.0

[agent]
timeout_sec = 900.0
```

### Step 7: Verify (see next section)

---

## 6. Writing Good Solutions (solve.sh)

### Do's

- **Use `set -e`** at the top so the script stops on errors
- **Use heredocs with single-quoted delimiters** (`<< 'EOF'`) to prevent variable expansion
- **Use `python3 << 'PATCH'`** for surgical edits to existing files
- **Copy exact strings** from the source code for replacements -- check whitespace carefully
- **Run migrations last** after all code changes are in place
- **Redirect stderr** with `2>&1` on migration commands

### Don'ts

- Don't use `sed` for multi-line patches (fragile, hard to debug)
- Don't assume line numbers (they can shift)
- Don't install packages unless absolutely necessary
- Don't modify code outside of `hc/api/` and `hc/accounts/` unless required

### Debugging a Broken Solution

```bash
# Run the container interactively and apply the solution step by step
docker run --rm -it \
    -v $(pwd)/tasks/my-task/solution:/solution \
    -v $(pwd)/tasks/my-task/tests:/tests \
    swe-harbor bash

# Inside the container:
cd /app
bash -x /solution/solve.sh  # -x shows each command as it runs
# Or run steps manually to find where it breaks
```

---

## 7. Writing Good Tests (test_solution.py)

### Test Categories Checklist

For every task, aim to cover:

| Category | Example Tests |
|----------|--------------|
| **Model existence** | Can import the model, has expected fields |
| **Model creation** | Create instance, verify field values |
| **UUIDs** | Each instance gets a unique code |
| **to_dict()** | Returns correct keys, values, no microseconds in datetimes |
| **Ordering** | Default ordering is newest-first |
| **Cascade delete** | Deleting parent deletes children |
| **Related names** | Reverse relations work (`check.my_things.count()`) |
| **API happy path** | POST creates, GET lists, DELETE removes |
| **Missing required fields** | Returns 400 with error message |
| **Invalid field values** | Wrong types, too long, bad format |
| **Auth errors** | Wrong API key returns 401 |
| **Wrong project** | Accessing another project's resources returns 403 |
| **Not found** | Nonexistent UUID returns 404 |
| **Limits** | Exceeding max count returns 403 |
| **CORS** | Response includes `Access-Control-Allow-Origin: *` |
| **URL routing** | Works under `/api/v1/`, `/api/v2/`, `/api/v3/` |
| **OPTIONS** | Returns 204 with CORS headers |

### Gotchas

- **Checks with `status="up"` need `last_ping` set.** The `get_status()` method calls `get_grace_start()` which asserts `self.last_ping is not None` for "up" checks. Always do:
  ```python
  check = Check.objects.create(project=self.project, name="C1", status="up")
  check.last_ping = now()
  check.save()
  ```

- **Import new models inside test methods**, not at the top of the file. The model doesn't exist until the solution runs migrations:
  ```python
  def test_something(self):
      from hc.api.models import MyNewModel  # Import here, not at module level
  ```

- **Use `self.client.post(url, json.dumps(data), content_type="application/json")`** for API posts. The `api_key` goes inside the JSON body for POST, or as `HTTP_X_API_KEY` header for GET/DELETE.

---

## 8. Verification Workflow

From `environments/swe_harbor/`:

```bash
# Build (or rebuild) the image
docker build -t swe-harbor environment/

# Test WITH solution (must print 1)
docker run --rm \
    -v $(pwd)/tasks/MY-TASK/solution:/solution \
    -v $(pwd)/tasks/MY-TASK/tests:/tests \
    swe-harbor \
    bash -c "mkdir -p /logs/verifier && cd /app && bash /solution/solve.sh && bash /tests/test.sh && cat /logs/verifier/reward.txt"

# Test WITHOUT solution (must print 0)
docker run --rm \
    -v $(pwd)/tasks/MY-TASK/tests:/tests \
    swe-harbor \
    bash -c "mkdir -p /logs/verifier && bash /tests/test.sh && cat /logs/verifier/reward.txt"
```

**Both checks must pass:**
- With solution = `1` means your solution is correct
- Without solution = `0` means your tests actually verify something

If both print `1`, your tests are too loose. If with-solution prints `0`, your solution has a bug.

---

## 9. Common Pitfalls

### Pitfall 1: String Replacement Doesn't Match

The most common cause of broken solutions. The `old` string in your python patch must **exactly** match the source code, including:
- Indentation (spaces vs tabs)
- Trailing whitespace
- Blank lines between code blocks

**Fix**: Copy the target string directly from the container:
```bash
docker run --rm swe-harbor cat /app/hc/api/models.py | less
```

### Pitfall 2: URL Route Order Matters

Django matches URLs top-to-bottom. If you add `checks/bulk/` *after* `checks/<uuid:code>/`, Django will try to interpret `"bulk"` as a UUID and return 404.

**Fix**: Insert new routes before more generic patterns.

### Pitfall 3: Missing Module in Environment

The base Docker image may be missing files referenced in settings. We encountered a missing `hc/logs.py` module that was referenced in `LOGGING` config. The fix was adding a minimal stub to `environment/app/hc/logs.py`.

**Fix**: If Django commands fail with import errors, check if the referenced module exists and add a stub if needed. Rebuild the Docker image afterward.

### Pitfall 4: Tests Pass for Wrong Reasons

If your tests only check that a model exists and has certain fields, an agent could pass them by creating a minimal model without any of the API logic.

**Fix**: Always include API-level tests that exercise the full stack (HTTP request -> view -> model -> response).

### Pitfall 5: Forgetting About `set -e`

Without `set -e`, your `solve.sh` will silently continue past failures (e.g., a failed patch), and you'll get confusing test failures.

**Fix**: Always start solve.sh with `#!/bin/bash` and `set -e`.

---

## 10. Quick Reference

### Decorators for API Views

| Decorator | Meaning |
|-----------|---------|
| `@authorize` | Requires write API key (POST, DELETE) |
| `@authorize_read` | Requires read or write API key (GET) |
| `@csrf_exempt` | Disables Django's CSRF protection |
| `@cors("GET", "POST")` | Adds CORS headers, handles OPTIONS for listed methods |

### Error Response Pattern

```python
return JsonResponse({"error": "descriptive message"}, status=400)
```

### Standard Status Codes

| Code | When |
|------|------|
| 200 | Success (GET, DELETE) |
| 201 | Created (POST) |
| 204 | OPTIONS preflight |
| 400 | Validation error |
| 401 | Bad API key |
| 403 | Wrong project / limit reached |
| 404 | Resource not found |

### Dispatcher Pattern

For endpoints that handle multiple HTTP methods:

```python
@csrf_exempt
@cors("GET", "POST")
def my_dispatcher(request, code):
    if request.method == "POST":
        return create_handler(request, code)
    return list_handler(request, code)
```

### `BaseTestCase` Fixtures

| Fixture | Value |
|---------|-------|
| `self.project` | Alice's project |
| `self.bobs_project` | Bob's project |
| `self.charlies_project` | Charlie's project |
| `self.alice` | Alice user object |
| API key `"X" * 32` | Authenticates as Alice's project |
| `HTTP_X_API_KEY="X" * 32` | Header auth for GET/DELETE |

### Datetime Formatting

The codebase uses `isostring()` (defined in models.py) for formatting datetimes without microseconds. Always use it in `to_dict()` methods.
