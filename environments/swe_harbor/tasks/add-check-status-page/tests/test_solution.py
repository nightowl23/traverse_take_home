"""Tests for the Public Status Pages feature."""
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
from hc.accounts.models import Project
from hc.test import BaseTestCase


class StatusPageModelTestCase(BaseTestCase):
    """Tests for the StatusPage model itself."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check", status="up")
        self.check.last_ping = now()
        self.check.save()

    def test_model_exists(self):
        """The StatusPage model should be importable."""
        from hc.api.models import StatusPage
        self.assertTrue(hasattr(StatusPage, 'objects'))

    def test_create_status_page(self):
        """Can create a status page linked to a project."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project,
            name="My Status Page",
            slug="my-status",
        )
        self.assertIsNotNone(page.code)
        self.assertEqual(page.name, "My Status Page")
        self.assertEqual(page.slug, "my-status")

    def test_unique_uuid(self):
        """Each status page should have a unique UUID."""
        from hc.api.models import StatusPage
        p1 = StatusPage.objects.create(
            project=self.project, name="First", slug="first"
        )
        p2 = StatusPage.objects.create(
            project=self.project, name="Second", slug="second"
        )
        self.assertNotEqual(p1.code, p2.code)

    def test_unique_slug(self):
        """Slugs must be unique across all status pages."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project, name="First", slug="unique-slug"
        )
        with self.assertRaises(Exception):
            StatusPage.objects.create(
                project=self.bobs_project, name="Second", slug="unique-slug"
            )

    def test_default_description_empty(self):
        """Description should default to empty string."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project, name="Test", slug="test-desc"
        )
        self.assertEqual(page.description, "")

    def test_default_is_public_false(self):
        """is_public should default to False."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project, name="Test", slug="test-public"
        )
        self.assertFalse(page.is_public)

    def test_m2m_checks(self):
        """Can assign checks to a status page via M2M."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project, name="Test", slug="test-m2m"
        )
        page.checks.add(self.check)
        self.assertEqual(page.checks.count(), 1)

    def test_cascade_delete(self):
        """Deleting a project deletes its status pages."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.charlies_project, name="Test", slug="test-cascade"
        )
        self.charlies_project.delete()
        self.assertEqual(StatusPage.objects.filter(code=page.code).count(), 0)

    def test_ordering(self):
        """Status pages should be ordered newest first by default."""
        from hc.api.models import StatusPage
        p1 = StatusPage.objects.create(
            project=self.project, name="Older", slug="older"
        )
        p2 = StatusPage.objects.create(
            project=self.project, name="Newer", slug="newer"
        )
        pages = list(StatusPage.objects.filter(project=self.project))
        self.assertEqual(pages[0].name, "Newer")
        self.assertEqual(pages[1].name, "Older")

    def test_to_dict(self):
        """to_dict() returns correct keys and values."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project,
            name="My Page",
            slug="my-page",
            description="A test page",
            is_public=True,
        )
        page.checks.add(self.check)
        d = page.to_dict()
        self.assertEqual(d["uuid"], str(page.code))
        self.assertEqual(d["name"], "My Page")
        self.assertEqual(d["slug"], "my-page")
        self.assertEqual(d["description"], "A test page")
        self.assertTrue(d["is_public"])
        self.assertIn("created", d)
        self.assertEqual(len(d["checks"]), 1)
        self.assertEqual(d["checks"][0], str(self.check.code))
        self.assertIn("status", d)

    def test_to_dict_created_no_microseconds(self):
        """created in to_dict() should have no microseconds."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project, name="Test", slug="test-micro"
        )
        d = page.to_dict()
        self.assertNotIn(".", d["created"])


class AggregateStatusTestCase(BaseTestCase):
    """Tests for StatusPage.aggregate_status()."""

    def setUp(self):
        super().setUp()

    def test_no_checks(self):
        """aggregate_status() returns 'no_checks' when no checks assigned."""
        from hc.api.models import StatusPage
        page = StatusPage.objects.create(
            project=self.project, name="Empty", slug="empty-status"
        )
        self.assertEqual(page.aggregate_status(), "no_checks")

    def test_all_up(self):
        """aggregate_status() returns 'up' when all checks are up."""
        from hc.api.models import StatusPage
        c1 = Check.objects.create(project=self.project, name="C1", status="up")
        c1.last_ping = now()
        c1.save()
        c2 = Check.objects.create(project=self.project, name="C2", status="up")
        c2.last_ping = now()
        c2.save()
        page = StatusPage.objects.create(
            project=self.project, name="Up", slug="all-up"
        )
        page.checks.set([c1, c2])
        self.assertEqual(page.aggregate_status(), "up")

    def test_any_down(self):
        """aggregate_status() returns 'down' if any check is down."""
        from hc.api.models import StatusPage
        c1 = Check.objects.create(project=self.project, name="C1", status="up")
        c1.last_ping = now()
        c1.save()
        c2 = Check.objects.create(project=self.project, name="C2", status="down")
        page = StatusPage.objects.create(
            project=self.project, name="Down", slug="any-down"
        )
        page.checks.set([c1, c2])
        self.assertEqual(page.aggregate_status(), "down")

    def test_all_paused(self):
        """aggregate_status() returns 'paused' when all checks are paused."""
        from hc.api.models import StatusPage
        c1 = Check.objects.create(project=self.project, name="C1", status="paused")
        c2 = Check.objects.create(project=self.project, name="C2", status="paused")
        page = StatusPage.objects.create(
            project=self.project, name="Paused", slug="all-paused"
        )
        page.checks.set([c1, c2])
        self.assertEqual(page.aggregate_status(), "paused")

    def test_mixed_up_and_new(self):
        """aggregate_status() returns 'up' if any check is up."""
        from hc.api.models import StatusPage
        c1 = Check.objects.create(project=self.project, name="C1", status="up")
        c1.last_ping = now()
        c1.save()
        c2 = Check.objects.create(project=self.project, name="C2", status="new")
        page = StatusPage.objects.create(
            project=self.project, name="Mixed", slug="mixed-up-new"
        )
        page.checks.set([c1, c2])
        self.assertEqual(page.aggregate_status(), "up")


class ProjectNumStatusPagesTestCase(BaseTestCase):
    """Tests for Project.num_status_pages_available()."""

    def test_method_exists(self):
        """Project should have num_status_pages_available() method."""
        self.assertTrue(hasattr(self.project, "num_status_pages_available"))

    def test_initially_five(self):
        """A fresh project should have 5 status pages available."""
        self.assertEqual(self.project.num_status_pages_available(), 5)

    def test_decreases_with_pages(self):
        """Available count should decrease as pages are created."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project, name="Page 1", slug="page-avail-1"
        )
        self.assertEqual(self.project.num_status_pages_available(), 4)

    def test_zero_at_limit(self):
        """Available count should be 0 when 5 pages exist."""
        from hc.api.models import StatusPage
        for i in range(5):
            StatusPage.objects.create(
                project=self.project, name=f"Page {i}", slug=f"page-limit-{i}"
            )
        self.assertEqual(self.project.num_status_pages_available(), 0)


class CreateStatusPageApiTestCase(BaseTestCase):
    """Tests for POST /api/v3/status-pages/"""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")
        self.url = "/api/v3/status-pages/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_create_status_page(self):
        """POST should create a status page and return 201."""
        r = self.post({
            "name": "My Status",
            "slug": "my-status-create",
            "description": "Test page",
            "is_public": True,
            "checks": [str(self.check.code)],
        })
        self.assertEqual(r.status_code, 201)
        doc = r.json()
        self.assertEqual(doc["name"], "My Status")
        self.assertEqual(doc["slug"], "my-status-create")
        self.assertEqual(doc["description"], "Test page")
        self.assertTrue(doc["is_public"])
        self.assertEqual(len(doc["checks"]), 1)

    def test_create_minimal(self):
        """POST with only name and slug should work."""
        r = self.post({"name": "Minimal", "slug": "minimal-page"})
        self.assertEqual(r.status_code, 201)
        doc = r.json()
        self.assertFalse(doc["is_public"])
        self.assertEqual(doc["description"], "")
        self.assertEqual(doc["checks"], [])

    def test_missing_name(self):
        """POST without name should return 400."""
        r = self.post({"slug": "no-name"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("name is required", r.json()["error"])

    def test_empty_name(self):
        """POST with empty name should return 400."""
        r = self.post({"name": "", "slug": "empty-name"})
        self.assertEqual(r.status_code, 400)

    def test_name_too_long(self):
        """POST with name > 100 chars should return 400."""
        r = self.post({"name": "x" * 101, "slug": "long-name"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("too long", r.json()["error"])

    def test_missing_slug(self):
        """POST without slug should return 400."""
        r = self.post({"name": "No Slug"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("slug is required", r.json()["error"])

    def test_invalid_slug_uppercase(self):
        """POST with uppercase slug should return 400."""
        r = self.post({"name": "Test", "slug": "UPPERCASE"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid slug", r.json()["error"])

    def test_invalid_slug_spaces(self):
        """POST with spaces in slug should return 400."""
        r = self.post({"name": "Test", "slug": "has spaces"})
        self.assertEqual(r.status_code, 400)

    def test_slug_too_long(self):
        """POST with slug > 100 chars should return 400."""
        r = self.post({"name": "Test", "slug": "x" * 101})
        self.assertEqual(r.status_code, 400)

    def test_duplicate_slug(self):
        """POST with an already-used slug should return 400."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project, name="Existing", slug="taken-slug"
        )
        r = self.post({"name": "New", "slug": "taken-slug"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("already in use", r.json()["error"])

    def test_invalid_check_uuid(self):
        """POST with invalid check UUID should return 400."""
        r = self.post({"name": "Test", "slug": "bad-check", "checks": ["not-a-uuid"]})
        self.assertEqual(r.status_code, 400)

    def test_check_from_other_project(self):
        """POST with check from another project should return 400."""
        other_check = Check.objects.create(project=self.bobs_project, name="Bob's")
        r = self.post({
            "name": "Test",
            "slug": "other-proj-check",
            "checks": [str(other_check.code)],
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("unauthorized", r.json()["error"])

    def test_is_public_not_boolean(self):
        """POST with non-boolean is_public should return 400."""
        r = self.post({"name": "Test", "slug": "bool-test", "is_public": "yes"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("is_public must be a boolean", r.json()["error"])

    def test_status_page_limit(self):
        """POST should return 403 when project has 5 status pages."""
        from hc.api.models import StatusPage
        for i in range(5):
            StatusPage.objects.create(
                project=self.project, name=f"Page {i}", slug=f"limit-test-{i}"
            )
        r = self.post({"name": "Too Many", "slug": "limit-test-overflow"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("too many", r.json()["error"])

    def test_wrong_api_key(self):
        """POST with wrong API key should return 401."""
        r = self.post({"name": "Test", "slug": "wrong-key"}, api_key="Y" * 32)
        self.assertEqual(r.status_code, 401)


class ListStatusPagesApiTestCase(BaseTestCase):
    """Tests for GET /api/v3/status-pages/"""

    def setUp(self):
        super().setUp()
        self.url = "/api/v3/status-pages/"

    def get(self, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.get(self.url, HTTP_X_API_KEY=api_key)

    def test_list_empty(self):
        """GET should return empty list when no status pages exist."""
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status_pages"], [])

    def test_list_pages(self):
        """GET should return status pages for the project."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project, name="Page 1", slug="list-page-1"
        )
        StatusPage.objects.create(
            project=self.project, name="Page 2", slug="list-page-2"
        )
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["status_pages"]), 2)

    def test_list_only_own_pages(self):
        """GET should not return pages from other projects."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project, name="Mine", slug="list-mine"
        )
        StatusPage.objects.create(
            project=self.bobs_project, name="Bob's", slug="list-bobs"
        )
        r = self.get()
        pages = r.json()["status_pages"]
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["name"], "Mine")

    def test_wrong_api_key(self):
        """GET with wrong API key should return 401."""
        r = self.get(api_key="Y" * 32)
        self.assertEqual(r.status_code, 401)


class GetStatusPageApiTestCase(BaseTestCase):
    """Tests for GET /api/v3/status-pages/<code>/"""

    def setUp(self):
        super().setUp()
        from hc.api.models import StatusPage
        self.page = StatusPage.objects.create(
            project=self.project, name="Test Page", slug="get-detail"
        )
        self.url = f"/api/v3/status-pages/{self.page.code}/"

    def test_get_page(self):
        """GET should return the status page."""
        r = self.client.get(self.url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "Test Page")

    def test_wrong_project(self):
        """GET for a page in another project should return 403."""
        from hc.api.models import StatusPage
        other_page = StatusPage.objects.create(
            project=self.bobs_project, name="Bob's Page", slug="get-bobs"
        )
        url = f"/api/v3/status-pages/{other_page.code}/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 403)

    def test_nonexistent_page(self):
        """GET for a nonexistent page should return 404."""
        url = f"/api/v3/status-pages/{uuid.uuid4()}/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 404)


class DeleteStatusPageApiTestCase(BaseTestCase):
    """Tests for DELETE /api/v3/status-pages/<code>/"""

    def setUp(self):
        super().setUp()
        from hc.api.models import StatusPage
        self.page = StatusPage.objects.create(
            project=self.project, name="Test Page", slug="delete-test"
        )
        self.url = f"/api/v3/status-pages/{self.page.code}/"

    def test_delete_page(self):
        """DELETE should remove the status page."""
        from hc.api.models import StatusPage
        r = self.client.delete(self.url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertFalse(StatusPage.objects.filter(code=self.page.code).exists())

    def test_delete_wrong_project(self):
        """DELETE for a page in another project should return 403."""
        from hc.api.models import StatusPage
        other_page = StatusPage.objects.create(
            project=self.bobs_project, name="Bob's", slug="delete-bobs"
        )
        url = f"/api/v3/status-pages/{other_page.code}/"
        r = self.client.delete(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 403)

    def test_delete_nonexistent(self):
        """DELETE for a nonexistent page should return 404."""
        url = f"/api/v3/status-pages/{uuid.uuid4()}/"
        r = self.client.delete(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 404)

    def test_delete_wrong_api_key(self):
        """DELETE with wrong API key should return 401."""
        r = self.client.delete(self.url, HTTP_X_API_KEY="Y" * 32)
        self.assertEqual(r.status_code, 401)


class PublicStatusPageApiTestCase(BaseTestCase):
    """Tests for GET /api/v3/status-pages/public/<slug>/"""

    def setUp(self):
        super().setUp()
        from hc.api.models import StatusPage
        self.check = Check.objects.create(project=self.project, name="C1", status="up")
        self.check.last_ping = now()
        self.check.save()

        self.page = StatusPage.objects.create(
            project=self.project,
            name="Public Page",
            slug="public-test",
            is_public=True,
        )
        self.page.checks.add(self.check)
        self.url = "/api/v3/status-pages/public/public-test/"

    def test_public_page(self):
        """GET should return the status page without authentication."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc["name"], "Public Page")
        self.assertIn("status", doc)

    def test_public_page_has_status(self):
        """Public page should include aggregated status."""
        r = self.client.get(self.url)
        doc = r.json()
        self.assertEqual(doc["status"], "up")

    def test_private_page_returns_404(self):
        """GET for a private page should return 404."""
        from hc.api.models import StatusPage
        StatusPage.objects.create(
            project=self.project,
            name="Private",
            slug="private-test",
            is_public=False,
        )
        r = self.client.get("/api/v3/status-pages/public/private-test/")
        self.assertEqual(r.status_code, 404)

    def test_nonexistent_slug(self):
        """GET for a nonexistent slug should return 404."""
        r = self.client.get("/api/v3/status-pages/public/does-not-exist/")
        self.assertEqual(r.status_code, 404)

    def test_cors_headers(self):
        """Public endpoint should include CORS headers."""
        r = self.client.get(self.url)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")


class StatusPageUrlRoutingTestCase(BaseTestCase):
    """Tests that URL routing works for all API versions."""

    def setUp(self):
        super().setUp()

    def test_v1_list_endpoint(self):
        """The status-pages endpoint should work under /api/v1/."""
        r = self.client.get("/api/v1/status-pages/", HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_v2_list_endpoint(self):
        """The status-pages endpoint should work under /api/v2/."""
        r = self.client.get("/api/v2/status-pages/", HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_v3_list_endpoint(self):
        """The status-pages endpoint should work under /api/v3/."""
        r = self.client.get("/api/v3/status-pages/", HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_options_request(self):
        """OPTIONS should return 204 with CORS headers."""
        r = self.client.options("/api/v3/status-pages/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
