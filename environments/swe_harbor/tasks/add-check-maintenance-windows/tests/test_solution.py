"""Tests for the Check Maintenance Windows feature."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta as td
from datetime import datetime, timezone

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.timezone import now

import os
import sys
sys.path.insert(0, "/app")
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hc.settings")
django.setup()

from hc.api.models import Check, Ping
from hc.test import BaseTestCase


class MaintenanceWindowModelTestCase(BaseTestCase):
    """Tests for the MaintenanceWindow model itself."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")

    def test_model_exists(self):
        """The MaintenanceWindow model should be importable."""
        from hc.api.models import MaintenanceWindow
        self.assertTrue(hasattr(MaintenanceWindow, 'objects'))

    def test_create_window(self):
        """Can create a maintenance window linked to a check."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check,
            title="Server Maintenance",
            start_time=now(),
            end_time=now() + td(hours=2),
        )
        self.assertIsNotNone(w.code)
        self.assertEqual(w.title, "Server Maintenance")

    def test_window_has_unique_uuid(self):
        """Each maintenance window should have a unique UUID code."""
        from hc.api.models import MaintenanceWindow
        w1 = MaintenanceWindow.objects.create(
            owner=self.check, title="First",
            start_time=now(), end_time=now() + td(hours=1),
        )
        w2 = MaintenanceWindow.objects.create(
            owner=self.check, title="Second",
            start_time=now(), end_time=now() + td(hours=1),
        )
        self.assertNotEqual(w1.code, w2.code)

    def test_to_dict(self):
        """to_dict() returns correct keys and values."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check,
            title="Deploy v2.0",
            start_time=now(),
            end_time=now() + td(hours=2),
        )
        d = w.to_dict()
        self.assertEqual(d["uuid"], str(w.code))
        self.assertEqual(d["title"], "Deploy v2.0")
        self.assertIn("start_time", d)
        self.assertIn("end_time", d)
        self.assertIn("created", d)

    def test_to_dict_no_microseconds(self):
        """Datetime fields in to_dict() should have no microseconds."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check, title="Test",
            start_time=now(), end_time=now() + td(hours=1),
        )
        d = w.to_dict()
        self.assertNotIn(".", d["start_time"])
        self.assertNotIn(".", d["end_time"])
        self.assertNotIn(".", d["created"])

    def test_is_active_inside_window(self):
        """is_active() returns True when now is inside the window."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check, title="Active",
            start_time=now() - td(hours=1),
            end_time=now() + td(hours=1),
        )
        self.assertTrue(w.is_active())

    def test_is_active_before_window(self):
        """is_active() returns False before the window starts."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check, title="Future",
            start_time=now() + td(hours=1),
            end_time=now() + td(hours=2),
        )
        self.assertFalse(w.is_active())

    def test_is_active_after_window(self):
        """is_active() returns False after the window ends."""
        from hc.api.models import MaintenanceWindow
        w = MaintenanceWindow.objects.create(
            owner=self.check, title="Past",
            start_time=now() - td(hours=2),
            end_time=now() - td(hours=1),
        )
        self.assertFalse(w.is_active())

    def test_ordering(self):
        """Maintenance windows should be ordered newest first by default."""
        from hc.api.models import MaintenanceWindow
        w1 = MaintenanceWindow.objects.create(
            owner=self.check, title="First",
            start_time=now(), end_time=now() + td(hours=1),
        )
        w2 = MaintenanceWindow.objects.create(
            owner=self.check, title="Second",
            start_time=now(), end_time=now() + td(hours=1),
        )
        windows = list(MaintenanceWindow.objects.filter(owner=self.check))
        self.assertEqual(windows[0].title, "Second")
        self.assertEqual(windows[1].title, "First")

    def test_cascade_delete(self):
        """Deleting a check deletes its maintenance windows."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Will be deleted",
            start_time=now(), end_time=now() + td(hours=1),
        )
        self.assertEqual(MaintenanceWindow.objects.count(), 1)
        self.check.delete()
        self.assertEqual(MaintenanceWindow.objects.count(), 0)

    def test_related_name(self):
        """check.maintenance_windows should work as reverse relation."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Via relation",
            start_time=now(), end_time=now() + td(hours=1),
        )
        self.assertEqual(self.check.maintenance_windows.count(), 1)


class CheckIsInMaintenanceTestCase(BaseTestCase):
    """Tests for Check.is_in_maintenance() method."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")

    def test_no_windows(self):
        """is_in_maintenance() returns False when no windows exist."""
        self.assertFalse(self.check.is_in_maintenance())

    def test_active_window(self):
        """is_in_maintenance() returns True with an active window."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Active",
            start_time=now() - td(hours=1),
            end_time=now() + td(hours=1),
        )
        self.assertTrue(self.check.is_in_maintenance())

    def test_inactive_window(self):
        """is_in_maintenance() returns False when all windows are inactive."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Past",
            start_time=now() - td(hours=2),
            end_time=now() - td(hours=1),
        )
        self.assertFalse(self.check.is_in_maintenance())

    def test_future_window(self):
        """is_in_maintenance() returns False for future windows."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Future",
            start_time=now() + td(hours=1),
            end_time=now() + td(hours=2),
        )
        self.assertFalse(self.check.is_in_maintenance())


class CheckGetStatusMaintenanceTestCase(BaseTestCase):
    """Tests for maintenance window integration with Check.get_status()."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(
            project=self.project, name="Test Check", status="up"
        )
        self.check.last_ping = now()
        self.check.save()

    def test_status_paused_during_maintenance(self):
        """get_status() should return 'paused' during an active maintenance window."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Maintenance",
            start_time=now() - td(hours=1),
            end_time=now() + td(hours=1),
        )
        self.assertEqual(self.check.get_status(), "paused")

    def test_status_normal_without_maintenance(self):
        """get_status() should return normal status without maintenance windows."""
        self.assertEqual(self.check.get_status(), "up")

    def test_status_normal_after_maintenance(self):
        """get_status() should return normal status after maintenance window ends."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Past Maintenance",
            start_time=now() - td(hours=2),
            end_time=now() - td(hours=1),
        )
        self.assertEqual(self.check.get_status(), "up")

    def test_down_check_shows_paused_during_maintenance(self):
        """A down check should show 'paused' during maintenance."""
        from hc.api.models import MaintenanceWindow
        self.check.status = "down"
        self.check.save()
        MaintenanceWindow.objects.create(
            owner=self.check, title="Maintenance",
            start_time=now() - td(hours=1),
            end_time=now() + td(hours=1),
        )
        self.assertEqual(self.check.get_status(), "paused")


class CreateMaintenanceApiTestCase(BaseTestCase):
    """Tests for POST /api/v3/checks/<code>/maintenance/"""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")
        self.url = f"/api/v3/checks/{self.check.code}/maintenance/"

    def post(self, data, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.post(
            self.url,
            json.dumps({**data, "api_key": api_key}),
            content_type="application/json",
        )

    def test_create_window(self):
        """POST should create a maintenance window and return 201."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "Deploy v2.0", "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 201)
        doc = r.json()
        self.assertEqual(doc["title"], "Deploy v2.0")
        self.assertIn("uuid", doc)
        self.assertIn("start_time", doc)
        self.assertIn("end_time", doc)
        self.assertIn("created", doc)

    def test_missing_title(self):
        """POST without title should return 400."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_empty_title(self):
        """POST with empty title should return 400."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "", "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_whitespace_only_title(self):
        """POST with whitespace-only title should return 400."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "   ", "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_title_too_long(self):
        """POST with title > 100 chars should return 400."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "x" * 101, "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_missing_start_time(self):
        """POST without start_time should return 400."""
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "Test", "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_missing_end_time(self):
        """POST without end_time should return 400."""
        start = (now() + td(hours=1)).isoformat()
        r = self.post({"title": "Test", "start_time": start})
        self.assertEqual(r.status_code, 400)

    def test_invalid_start_time(self):
        """POST with invalid start_time should return 400."""
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "Test", "start_time": "not-a-date", "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_invalid_end_time(self):
        """POST with invalid end_time should return 400."""
        start = (now() + td(hours=1)).isoformat()
        r = self.post({"title": "Test", "start_time": start, "end_time": "not-a-date"})
        self.assertEqual(r.status_code, 400)

    def test_end_before_start(self):
        """POST with end_time before start_time should return 400."""
        start = (now() + td(hours=3)).isoformat()
        end = (now() + td(hours=1)).isoformat()
        r = self.post({"title": "Test", "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)

    def test_end_equals_start(self):
        """POST with end_time equal to start_time should return 400."""
        t = (now() + td(hours=1)).isoformat()
        r = self.post({"title": "Test", "start_time": t, "end_time": t})
        self.assertEqual(r.status_code, 400)

    def test_window_limit(self):
        """POST should return 403 when check has 10 maintenance windows."""
        from hc.api.models import MaintenanceWindow
        for i in range(10):
            MaintenanceWindow.objects.create(
                owner=self.check, title=f"Window {i}",
                start_time=now() + td(hours=i), end_time=now() + td(hours=i+1),
            )
        start = (now() + td(hours=20)).isoformat()
        end = (now() + td(hours=21)).isoformat()
        r = self.post({"title": "One too many", "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 403)
        self.assertIn("too many", r.json()["error"].lower())

    def test_wrong_api_key(self):
        """POST with wrong API key should return 401."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": "Test", "start_time": start, "end_time": end}, api_key="Y" * 32)
        self.assertEqual(r.status_code, 401)

    def test_wrong_project(self):
        """POST for a check in a different project should return 403."""
        other_check = Check.objects.create(project=self.bobs_project, name="Bob's Check")
        url = f"/api/v3/checks/{other_check.code}/maintenance/"
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.client.post(
            url,
            json.dumps({"title": "Hacking", "start_time": start, "end_time": end, "api_key": "X" * 32}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)

    def test_nonexistent_check(self):
        """POST for a nonexistent check should return 404."""
        fake_uuid = uuid.uuid4()
        url = f"/api/v3/checks/{fake_uuid}/maintenance/"
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.client.post(
            url,
            json.dumps({"title": "Ghost", "start_time": start, "end_time": end, "api_key": "X" * 32}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)

    def test_title_not_string(self):
        """POST with non-string title should return 400."""
        start = (now() + td(hours=1)).isoformat()
        end = (now() + td(hours=3)).isoformat()
        r = self.post({"title": 123, "start_time": start, "end_time": end})
        self.assertEqual(r.status_code, 400)


class ListMaintenanceApiTestCase(BaseTestCase):
    """Tests for GET /api/v3/checks/<code>/maintenance/"""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")
        self.url = f"/api/v3/checks/{self.check.code}/maintenance/"

    def get(self, api_key=None):
        if api_key is None:
            api_key = "X" * 32
        return self.client.get(self.url, HTTP_X_API_KEY=api_key)

    def test_list_empty(self):
        """GET should return empty list when no windows exist."""
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["maintenance_windows"], [])

    def test_list_windows(self):
        """GET should return all maintenance windows."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="First",
            start_time=now(), end_time=now() + td(hours=1),
        )
        MaintenanceWindow.objects.create(
            owner=self.check, title="Second",
            start_time=now(), end_time=now() + td(hours=2),
        )
        r = self.get()
        self.assertEqual(r.status_code, 200)
        windows = r.json()["maintenance_windows"]
        self.assertEqual(len(windows), 2)

    def test_list_newest_first(self):
        """GET should return windows newest first."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Older",
            start_time=now(), end_time=now() + td(hours=1),
        )
        MaintenanceWindow.objects.create(
            owner=self.check, title="Newer",
            start_time=now(), end_time=now() + td(hours=2),
        )
        r = self.get()
        windows = r.json()["maintenance_windows"]
        self.assertEqual(windows[0]["title"], "Newer")
        self.assertEqual(windows[1]["title"], "Older")

    def test_wrong_api_key(self):
        """GET with wrong API key should return 401."""
        r = self.get(api_key="Y" * 32)
        self.assertEqual(r.status_code, 401)

    def test_wrong_project(self):
        """GET for a check in a different project should return 403."""
        other_check = Check.objects.create(project=self.bobs_project, name="Bob's Check")
        url = f"/api/v3/checks/{other_check.code}/maintenance/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 403)

    def test_nonexistent_check(self):
        """GET for a nonexistent check should return 404."""
        fake_uuid = uuid.uuid4()
        url = f"/api/v3/checks/{fake_uuid}/maintenance/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 404)

    def test_cors_headers(self):
        """Response should include CORS headers."""
        r = self.get()
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")


class DeleteMaintenanceApiTestCase(BaseTestCase):
    """Tests for DELETE /api/v3/checks/<code>/maintenance/<window_code>/"""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")
        from hc.api.models import MaintenanceWindow
        self.window = MaintenanceWindow.objects.create(
            owner=self.check, title="To Delete",
            start_time=now() + td(hours=1), end_time=now() + td(hours=2),
        )
        self.url = f"/api/v3/checks/{self.check.code}/maintenance/{self.window.code}/"

    def test_delete_window(self):
        """DELETE should remove the maintenance window and return 200."""
        from hc.api.models import MaintenanceWindow
        r = self.client.delete(self.url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(MaintenanceWindow.objects.count(), 0)

    def test_delete_nonexistent_window(self):
        """DELETE for a nonexistent window should return 404."""
        fake_uuid = uuid.uuid4()
        url = f"/api/v3/checks/{self.check.code}/maintenance/{fake_uuid}/"
        r = self.client.delete(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 404)

    def test_delete_wrong_api_key(self):
        """DELETE with wrong API key should return 401."""
        r = self.client.delete(self.url, HTTP_X_API_KEY="Y" * 32)
        self.assertEqual(r.status_code, 401)

    def test_delete_wrong_project(self):
        """DELETE for a check in a different project should return 403."""
        other_check = Check.objects.create(project=self.bobs_project, name="Bob's Check")
        from hc.api.models import MaintenanceWindow
        window = MaintenanceWindow.objects.create(
            owner=other_check, title="Other",
            start_time=now() + td(hours=1), end_time=now() + td(hours=2),
        )
        url = f"/api/v3/checks/{other_check.code}/maintenance/{window.code}/"
        r = self.client.delete(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 403)


class CheckToDictMaintenanceTestCase(BaseTestCase):
    """Tests for in_maintenance in Check.to_dict()."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")

    def test_in_maintenance_false(self):
        """to_dict() should include in_maintenance=False when no active windows."""
        d = self.check.to_dict()
        self.assertIn("in_maintenance", d)
        self.assertFalse(d["in_maintenance"])

    def test_in_maintenance_true(self):
        """to_dict() should include in_maintenance=True during active window."""
        from hc.api.models import MaintenanceWindow
        MaintenanceWindow.objects.create(
            owner=self.check, title="Active",
            start_time=now() - td(hours=1),
            end_time=now() + td(hours=1),
        )
        d = self.check.to_dict()
        self.assertTrue(d["in_maintenance"])


class MaintenanceUrlRoutingTestCase(BaseTestCase):
    """Tests that URL routing works for all API versions."""

    def setUp(self):
        super().setUp()
        self.check = Check.objects.create(project=self.project, name="Test Check")

    def test_v1_endpoint(self):
        """The maintenance endpoint should work under /api/v1/."""
        url = f"/api/v1/checks/{self.check.code}/maintenance/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_v2_endpoint(self):
        """The maintenance endpoint should work under /api/v2/."""
        url = f"/api/v2/checks/{self.check.code}/maintenance/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_v3_endpoint(self):
        """The maintenance endpoint should work under /api/v3/."""
        url = f"/api/v3/checks/{self.check.code}/maintenance/"
        r = self.client.get(url, HTTP_X_API_KEY="X" * 32)
        self.assertEqual(r.status_code, 200)

    def test_options_request(self):
        """OPTIONS should return 204 with CORS headers."""
        url = f"/api/v3/checks/{self.check.code}/maintenance/"
        r = self.client.options(url)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
