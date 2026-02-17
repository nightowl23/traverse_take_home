#!/bin/bash
set -e

###############################################################################
# 1. Add the MaintenanceWindow model to hc/api/models.py
###############################################################################

cat >> /app/hc/api/models.py << 'PYEOF'


class MaintenanceWindow(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(Check, models.CASCADE, related_name="maintenance_windows")
    title = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created = models.DateTimeField(default=now)

    class Meta:
        ordering = ["-created"]

    def to_dict(self) -> dict:
        return {
            "uuid": str(self.code),
            "title": self.title,
            "start_time": isostring(self.start_time),
            "end_time": isostring(self.end_time),
            "created": isostring(self.created),
        }

    def is_active(self) -> bool:
        current = now()
        return self.start_time <= current < self.end_time
PYEOF

###############################################################################
# 2. Add Check.is_in_maintenance() method
###############################################################################

cd /app

python3 << 'PATCH1'
with open("hc/api/models.py", "r") as f:
    content = f.read()

old = '''    def assign_all_channels(self) -> None:
        channels = Channel.objects.filter(project=self.project)
        self.channel_set.set(channels)'''

new = '''    def is_in_maintenance(self) -> bool:
        return self.maintenance_windows.filter(
            start_time__lte=now(),
            end_time__gt=now(),
        ).exists()

    def assign_all_channels(self) -> None:
        channels = Channel.objects.filter(project=self.project)
        self.channel_set.set(channels)'''

content = content.replace(old, new, 1)

with open("hc/api/models.py", "w") as f:
    f.write(content)
PATCH1

###############################################################################
# 3. Modify Check.get_status() to check maintenance windows
###############################################################################

python3 << 'PATCH2'
with open("hc/api/models.py", "r") as f:
    content = f.read()

old = '''    def get_status(self, *, with_started: bool = False) -> str:
        """Return current status for display."""
        frozen_now = now()

        if self.last_start:'''

new = '''    def get_status(self, *, with_started: bool = False) -> str:
        """Return current status for display."""
        if self.is_in_maintenance():
            return "paused"

        frozen_now = now()

        if self.last_start:'''

content = content.replace(old, new, 1)

with open("hc/api/models.py", "w") as f:
    f.write(content)
PATCH2

###############################################################################
# 4. Add in_maintenance to Check.to_dict()
###############################################################################

python3 << 'PATCH3'
with open("hc/api/models.py", "r") as f:
    content = f.read()

old = '''        if self.kind == "simple":
            result["timeout"] = int(self.timeout.total_seconds())
        elif self.kind in ("cron", "oncalendar"):
            result["schedule"] = self.schedule
            result["tz"] = self.tz

        return result'''

new = '''        result["in_maintenance"] = self.is_in_maintenance()

        if self.kind == "simple":
            result["timeout"] = int(self.timeout.total_seconds())
        elif self.kind in ("cron", "oncalendar"):
            result["schedule"] = self.schedule
            result["tz"] = self.tz

        return result'''

content = content.replace(old, new, 1)

with open("hc/api/models.py", "w") as f:
    f.write(content)
PATCH3

###############################################################################
# 5. Add API views for maintenance windows
###############################################################################

cat >> /app/hc/api/views.py << 'VIEWEOF'


@authorize_read
def list_maintenance(request: ApiRequest, code: UUID) -> HttpResponse:
    check = get_object_or_404(Check, code=code)
    if check.project_id != request.project.id:
        return HttpResponseForbidden()

    from hc.api.models import MaintenanceWindow

    windows = MaintenanceWindow.objects.filter(owner=check)
    return JsonResponse({"maintenance_windows": [w.to_dict() for w in windows]})


@authorize
def create_maintenance(request: ApiRequest, code: UUID) -> HttpResponse:
    check = get_object_or_404(Check, code=code)
    if check.project_id != request.project.id:
        return HttpResponseForbidden()

    from hc.api.models import MaintenanceWindow

    if check.maintenance_windows.count() >= 10:
        return JsonResponse({"error": "too many maintenance windows"}, status=403)

    title = request.json.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return JsonResponse({"error": "title is required"}, status=400)

    if len(title) > 100:
        return JsonResponse({"error": "title is too long"}, status=400)

    start_str = request.json.get("start_time", "")
    if not isinstance(start_str, str) or not start_str:
        return JsonResponse({"error": "start_time is required"}, status=400)

    end_str = request.json.get("end_time", "")
    if not isinstance(end_str, str) or not end_str:
        return JsonResponse({"error": "end_time is required"}, status=400)

    try:
        start_time = datetime.fromisoformat(start_str)
    except ValueError:
        return JsonResponse({"error": "invalid start_time format"}, status=400)

    try:
        end_time = datetime.fromisoformat(end_str)
    except ValueError:
        return JsonResponse({"error": "invalid end_time format"}, status=400)

    if end_time <= start_time:
        return JsonResponse({"error": "end_time must be after start_time"}, status=400)

    window = MaintenanceWindow(
        owner=check,
        title=title.strip(),
        start_time=start_time,
        end_time=end_time,
    )
    window.save()

    return JsonResponse(window.to_dict(), status=201)


@csrf_exempt
@cors("GET", "POST")
def check_maintenance(request: HttpRequest, code: UUID) -> HttpResponse:
    if request.method == "POST":
        return create_maintenance(request, code)

    return list_maintenance(request, code)


@cors("DELETE")
@csrf_exempt
@authorize
def check_maintenance_detail(request: ApiRequest, code: UUID, window_code: UUID) -> HttpResponse:
    check = get_object_or_404(Check, code=code)
    if check.project_id != request.project.id:
        return HttpResponseForbidden()

    from hc.api.models import MaintenanceWindow

    window = get_object_or_404(MaintenanceWindow, code=window_code, owner=check)
    window.delete()

    return JsonResponse({"ok": True})
VIEWEOF

###############################################################################
# 6. Add URL routes
###############################################################################

python3 << 'PATCH4'
with open("hc/api/urls.py", "r") as f:
    content = f.read()

old = '    path("channels/", views.channels),'

new = '''    path(
        "checks/<uuid:code>/maintenance/",
        views.check_maintenance,
        name="hc-api-maintenance",
    ),
    path(
        "checks/<uuid:code>/maintenance/<uuid:window_code>/",
        views.check_maintenance_detail,
        name="hc-api-maintenance-detail",
    ),
    path("channels/", views.channels),'''

content = content.replace(old, new, 1)

with open("hc/api/urls.py", "w") as f:
    f.write(content)
PATCH4

###############################################################################
# 7. Create the migration
###############################################################################

cd /app
python manage.py makemigrations api --name maintenancewindow 2>&1
python manage.py migrate 2>&1
