#!/bin/bash
set -e

###############################################################################
# 1. Add the StatusPage model to hc/api/models.py
###############################################################################

cat >> /app/hc/api/models.py << 'PYEOF'


class StatusPage(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    project = models.ForeignKey(
        "accounts.Project", models.CASCADE, related_name="status_pages"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    checks = models.ManyToManyField(Check, blank=True, related_name="status_pages")
    is_public = models.BooleanField(default=False)
    created = models.DateTimeField(default=now)

    class Meta:
        ordering = ["-created"]

    def aggregate_status(self) -> str:
        check_list = self.checks.all()
        if not check_list:
            return "no_checks"

        statuses = set()
        for check in check_list:
            statuses.add(check.get_status())

        if "down" in statuses:
            return "down"
        if "grace" in statuses:
            return "grace"
        if "up" in statuses:
            return "up"
        return "paused"

    def to_dict(self) -> dict:
        return {
            "uuid": str(self.code),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "is_public": self.is_public,
            "created": isostring(self.created),
            "checks": [str(c.code) for c in self.checks.all()],
            "status": self.aggregate_status(),
        }
PYEOF

###############################################################################
# 2. Add Project.num_status_pages_available() to accounts/models.py
###############################################################################

cd /app

python3 << 'PATCH1'
with open("hc/accounts/models.py", "r") as f:
    content = f.read()

old = '''    def num_checks_available(self) -> int:
        return self.owner_profile.num_checks_available()'''

new = '''    def num_checks_available(self) -> int:
        return self.owner_profile.num_checks_available()

    def num_status_pages_available(self) -> int:
        from hc.api.models import StatusPage
        return 5 - StatusPage.objects.filter(project=self).count()'''

content = content.replace(old, new, 1)

with open("hc/accounts/models.py", "w") as f:
    f.write(content)
PATCH1

###############################################################################
# 3. Add API views for status pages
###############################################################################

cat >> /app/hc/api/views.py << 'VIEWEOF'


@authorize_read
def list_status_pages(request: ApiRequest) -> HttpResponse:
    from hc.api.models import StatusPage

    pages = StatusPage.objects.filter(project=request.project)
    return JsonResponse({"status_pages": [p.to_dict() for p in pages]})


@authorize
def create_status_page(request: ApiRequest) -> HttpResponse:
    import re
    from hc.api.models import StatusPage

    if request.project.num_status_pages_available() <= 0:
        return JsonResponse({"error": "too many status pages"}, status=403)

    name = request.json.get("name", "")
    if not isinstance(name, str) or not name.strip():
        return JsonResponse({"error": "name is required"}, status=400)

    if len(name) > 100:
        return JsonResponse({"error": "name is too long"}, status=400)

    slug = request.json.get("slug", "")
    if not isinstance(slug, str) or not slug.strip():
        return JsonResponse({"error": "slug is required"}, status=400)

    if len(slug) > 100:
        return JsonResponse({"error": "slug is too long"}, status=400)

    if not re.match(r"^[a-z0-9-]+$", slug):
        return JsonResponse({"error": "invalid slug format"}, status=400)

    if StatusPage.objects.filter(slug=slug).exists():
        return JsonResponse({"error": "slug already in use"}, status=400)

    description = request.json.get("description", "")
    if not isinstance(description, str):
        description = ""

    is_public = request.json.get("is_public", False)
    if not isinstance(is_public, bool):
        return JsonResponse({"error": "is_public must be a boolean"}, status=400)

    check_uuids = request.json.get("checks", [])
    check_objects = []
    if check_uuids:
        if not isinstance(check_uuids, list):
            return JsonResponse({"error": "checks must be a list"}, status=400)
        for u in check_uuids:
            try:
                check = Check.objects.get(code=UUID(str(u)), project=request.project)
                check_objects.append(check)
            except (Check.DoesNotExist, ValueError, AttributeError):
                return JsonResponse(
                    {"error": "invalid or unauthorized check uuid"}, status=400
                )

    page = StatusPage(
        project=request.project,
        name=name.strip(),
        slug=slug,
        description=description,
        is_public=is_public,
    )
    page.save()

    if check_objects:
        page.checks.set(check_objects)

    return JsonResponse(page.to_dict(), status=201)


@csrf_exempt
@cors("GET", "POST")
def status_pages(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return create_status_page(request)

    return list_status_pages(request)


@authorize_read
def get_status_page(request: ApiRequest, code: UUID) -> HttpResponse:
    from hc.api.models import StatusPage

    page = get_object_or_404(StatusPage, code=code)
    if page.project_id != request.project.id:
        return HttpResponseForbidden()

    return JsonResponse(page.to_dict())


@authorize
def delete_status_page(request: ApiRequest, code: UUID) -> HttpResponse:
    from hc.api.models import StatusPage

    page = get_object_or_404(StatusPage, code=code)
    if page.project_id != request.project.id:
        return HttpResponseForbidden()

    page.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@cors("GET", "DELETE")
def status_page_detail(request: HttpRequest, code: UUID) -> HttpResponse:
    if request.method == "DELETE":
        return delete_status_page(request, code)

    return get_status_page(request, code)


@csrf_exempt
@cors("GET")
def status_page_public(request: HttpRequest, slug: str) -> HttpResponse:
    from hc.api.models import StatusPage

    try:
        page = StatusPage.objects.get(slug=slug)
    except StatusPage.DoesNotExist:
        return HttpResponseNotFound()

    if not page.is_public:
        return HttpResponseNotFound()

    return JsonResponse(page.to_dict())
VIEWEOF

###############################################################################
# 4. Add URL routes
###############################################################################

python3 << 'PATCH2'
with open("hc/api/urls.py", "r") as f:
    content = f.read()

old = '    path("channels/", views.channels),'

new = '''    path("status-pages/", views.status_pages, name="hc-api-status-pages"),
    path(
        "status-pages/public/<slug:slug>/",
        views.status_page_public,
        name="hc-api-status-page-public",
    ),
    path(
        "status-pages/<uuid:code>/",
        views.status_page_detail,
        name="hc-api-status-page-detail",
    ),
    path("channels/", views.channels),'''

content = content.replace(old, new, 1)

with open("hc/api/urls.py", "w") as f:
    f.write(content)
PATCH2

###############################################################################
# 5. Create the migration
###############################################################################

cd /app
python manage.py makemigrations api --name statuspage 2>&1
python manage.py migrate 2>&1
