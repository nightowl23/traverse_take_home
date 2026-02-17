"""Tests for the Bulk Check Operations API feature."""
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

from hc.api.models import Check, Flip
from hc.test import BaseTestCase


class TagsListInToDictTestCase(BaseTestCase):
    """Tests for tags_list in Check.to_dict()."""

    def setUp(self):
        super().setUp()

    def test_tags_list_present(self):
        """to_dict() should include tags_list field."""
        check = Check.objects.create(project=self.project, name="Test", tags="prod web")
        d = check.to_dict()
        self.assertIn("tags_list", d)

    def test_tags_list_values(self):
        """tags_list should be a list of individual tag strings."""
        check = Check.objects.create(project=self.project, name="Test", tags="prod web api")
        d = check.to_dict()
        self.assertEqual(sorted(d["tags_list"]), ["api", "prod", "web"])

    def test_tags_list_empty(self):
        """tags_list should be [] when tags is empty."""
        check = Check.objects.create(project=self.project, name="Test", tags="")
        d = check.to_dict()
        self.assertEqual(d["tags_list"], [])


class BulkPauseTestCase(BaseTestCase):
    """Tests for bulk pause action."""

    def setUp(self):
        super().setUp()
        self.check1 = Check.objects.create(
            project=self.project, name="Check 1", status="up"
        )
        self.check2 = Check.objects.create(
            project=self.project, name="Check 2", status="up"
        )
        self.url = "/api/v3/checks/bulk/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_bulk_pause(self):
        """Bulk pause should pause all specified checks."""
        r = self.post({
            "action": "pause",
            "checks": [str(self.check1.code), str(self.check2.code)],
        })
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertTrue(doc["success"])
        self.assertEqual(doc["count"], 2)

        self.check1.refresh_from_db()
        self.check2.refresh_from_db()
        self.assertEqual(self.check1.status, "paused")
        self.assertEqual(self.check2.status, "paused")

    def test_bulk_pause_clears_alert(self):
        """Bulk pause should clear alert_after and last_start."""
        self.check1.alert_after = now() + td(hours=1)
        self.check1.last_start = now()
        self.check1.save()

        self.post({
            "action": "pause",
            "checks": [str(self.check1.code)],
        })

        self.check1.refresh_from_db()
        self.assertIsNone(self.check1.alert_after)
        self.assertIsNone(self.check1.last_start)

    def test_bulk_pause_creates_flip(self):
        """Bulk pause should create a flip record."""
        self.post({
            "action": "pause",
            "checks": [str(self.check1.code)],
        })
        flip = Flip.objects.filter(owner=self.check1).first()
        self.assertIsNotNone(flip)
        self.assertEqual(flip.new_status, "paused")


class BulkResumeTestCase(BaseTestCase):
    """Tests for bulk resume action."""

    def setUp(self):
        super().setUp()
        self.check1 = Check.objects.create(
            project=self.project, name="Check 1", status="paused"
        )
        self.check2 = Check.objects.create(
            project=self.project, name="Check 2", status="paused"
        )
        self.url = "/api/v3/checks/bulk/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_bulk_resume(self):
        """Bulk resume should resume all paused checks."""
        r = self.post({
            "action": "resume",
            "checks": [str(self.check1.code), str(self.check2.code)],
        })
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertTrue(doc["success"])
        self.assertEqual(doc["count"], 2)

        self.check1.refresh_from_db()
        self.check2.refresh_from_db()
        self.assertEqual(self.check1.status, "new")
        self.assertEqual(self.check2.status, "new")

    def test_resume_skips_non_paused(self):
        """Bulk resume should skip checks that are not paused."""
        self.check2.status = "up"
        self.check2.save()

        r = self.post({
            "action": "resume",
            "checks": [str(self.check1.code), str(self.check2.code)],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

        self.check2.refresh_from_db()
        self.assertEqual(self.check2.status, "up")

    def test_resume_clears_last_ping(self):
        """Bulk resume should clear last_ping."""
        self.check1.last_ping = now()
        self.check1.save()

        self.post({
            "action": "resume",
            "checks": [str(self.check1.code)],
        })

        self.check1.refresh_from_db()
        self.assertIsNone(self.check1.last_ping)

    def test_resume_creates_flip(self):
        """Bulk resume should create a flip record."""
        self.post({
            "action": "resume",
            "checks": [str(self.check1.code)],
        })
        flip = Flip.objects.filter(owner=self.check1).first()
        self.assertIsNotNone(flip)
        self.assertEqual(flip.new_status, "new")


class BulkDeleteTestCase(BaseTestCase):
    """Tests for bulk delete action."""

    def setUp(self):
        super().setUp()
        self.check1 = Check.objects.create(project=self.project, name="Check 1")
        self.check2 = Check.objects.create(project=self.project, name="Check 2")
        self.url = "/api/v3/checks/bulk/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_bulk_delete(self):
        """Bulk delete should remove all specified checks."""
        r = self.post({
            "action": "delete",
            "checks": [str(self.check1.code), str(self.check2.code)],
        })
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertTrue(doc["success"])
        self.assertEqual(doc["count"], 2)
        self.assertFalse(Check.objects.filter(code=self.check1.code).exists())
        self.assertFalse(Check.objects.filter(code=self.check2.code).exists())


class BulkAddTagsTestCase(BaseTestCase):
    """Tests for bulk add_tags action."""

    def setUp(self):
        super().setUp()
        self.check1 = Check.objects.create(
            project=self.project, name="Check 1", tags="prod"
        )
        self.check2 = Check.objects.create(
            project=self.project, name="Check 2", tags="staging"
        )
        self.url = "/api/v3/checks/bulk/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_add_tags(self):
        """add_tags should merge new tags with existing ones."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code), str(self.check2.code)],
            "tags": "web api",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)

        self.check1.refresh_from_db()
        self.assertIn("web", self.check1.tags)
        self.assertIn("api", self.check1.tags)
        self.assertIn("prod", self.check1.tags)

    def test_add_tags_no_duplicates(self):
        """add_tags should not create duplicate tags."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code)],
            "tags": "prod web",
        })
        self.assertEqual(r.status_code, 200)

        self.check1.refresh_from_db()
        tags = self.check1.tags.split()
        self.assertEqual(len(tags), len(set(tags)))

    def test_add_tags_sorted(self):
        """add_tags should store tags in sorted order."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code)],
            "tags": "zebra alpha",
        })
        self.assertEqual(r.status_code, 200)

        self.check1.refresh_from_db()
        tags = self.check1.tags.split()
        self.assertEqual(tags, sorted(tags))

    def test_add_tags_missing(self):
        """add_tags without tags field should return 400."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code)],
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("tags is required", r.json()["error"])

    def test_add_tags_empty(self):
        """add_tags with empty tags should return 400."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code)],
            "tags": "",
        })
        self.assertEqual(r.status_code, 400)

    def test_add_tags_not_string(self):
        """add_tags with non-string tags should return 400."""
        r = self.post({
            "action": "add_tags",
            "checks": [str(self.check1.code)],
            "tags": 123,
        })
        self.assertEqual(r.status_code, 400)


class BulkValidationTestCase(BaseTestCase):
    """Tests for input validation on the bulk endpoint."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Check 1")
        self.url = "/api/v3/checks/bulk/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_missing_action(self):
        """POST without action should return 400."""
        r = self.post({"checks": [str(self.check.code)]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid action", r.json()["error"])

    def test_invalid_action(self):
        """POST with an unknown action should return 400."""
        r = self.post({"action": "explode", "checks": [str(self.check.code)]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid action", r.json()["error"])

    def test_missing_checks(self):
        """POST without checks should return 400."""
        r = self.post({"action": "pause"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("checks must be a list", r.json()["error"])

    def test_checks_not_list(self):
        """POST with checks as string should return 400."""
        r = self.post({"action": "pause", "checks": "not-a-list"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("checks must be a list", r.json()["error"])

    def test_empty_checks(self):
        """POST with empty checks list should return 400."""
        r = self.post({"action": "pause", "checks": []})
        self.assertEqual(r.status_code, 400)
        self.assertIn("checks list is empty", r.json()["error"])

    def test_too_many_checks(self):
        """POST with more than 50 checks should return 400."""
        uuids = [str(uuid.uuid4()) for _ in range(51)]
        r = self.post({"action": "pause", "checks": uuids})
        self.assertEqual(r.status_code, 400)
        self.assertIn("too many checks", r.json()["error"])

    def test_invalid_uuid(self):
        """POST with invalid UUID in checks should return 400."""
        r = self.post({"action": "pause", "checks": ["not-a-uuid"]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid uuid", r.json()["error"])

    def test_nonexistent_check(self):
        """POST with nonexistent check UUID should return 400."""
        fake = str(uuid.uuid4())
        r = self.post({"action": "pause", "checks": [fake]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not found", r.json()["error"])

    def test_check_in_other_project(self):
        """POST with check from another project should return 400."""
        other_check = Check.objects.create(project=self.bobs_project, name="Bob's")
        r = self.post({"action": "pause", "checks": [str(other_check.code)]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not found", r.json()["error"])

    def test_wrong_api_key(self):
        """POST with wrong API key should return 401."""
        r = self.post(
            {"action": "pause", "checks": [str(self.check.code)]},
            api_key="Y" * 32,
        )
        self.assertEqual(r.status_code, 401)


class BulkUrlRoutingTestCase(BaseTestCase):
    """Tests that URL routing works for all API versions."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")

    def _post(self, version):
        url = f"/api/v{version}/checks/bulk/"
        return self.client.post(
            url,
            json.dumps({
                "action": "pause",
                "checks": [str(self.check.code)],
                "api_key": "X" * 32,
            }),
            content_type="application/json",
        )

    def test_v1_endpoint(self):
        """The bulk endpoint should work under /api/v1/."""
        r = self._post(1)
        self.assertEqual(r.status_code, 200)

    def test_v2_endpoint(self):
        """The bulk endpoint should work under /api/v2/."""
        r = self._post(2)
        self.assertEqual(r.status_code, 200)

    def test_v3_endpoint(self):
        """The bulk endpoint should work under /api/v3/."""
        r = self._post(3)
        self.assertEqual(r.status_code, 200)

    def test_cors_headers(self):
        """Response should include CORS headers."""
        r = self._post(3)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_options_request(self):
        """OPTIONS should return 204 with CORS headers."""
        url = "/api/v3/checks/bulk/"
        r = self.client.options(url)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
