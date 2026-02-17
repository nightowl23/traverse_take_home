#!/bin/bash
set -e

###############################################################################
# 1. Add tags_list to Check.to_dict()
###############################################################################

cd /app

python3 << 'PATCH1'
with open("hc/api/models.py", "r") as f:
    content = f.read()

old = '''            "name": self.name,
            "slug": self.slug,
            "tags": self.tags,'''

new = '''            "name": self.name,
            "slug": self.slug,
            "tags": self.tags,
            "tags_list": self.tags_list(),'''

content = content.replace(old, new, 1)

with open("hc/api/models.py", "w") as f:
    f.write(content)
PATCH1

###############################################################################
# 2. Add bulk_actions view to hc/api/views.py
###############################################################################

cat >> /app/hc/api/views.py << 'VIEWEOF'


@cors("POST")
@csrf_exempt
@authorize
def bulk_actions(request: ApiRequest) -> HttpResponse:
    action = request.json.get("action", "")
    if action not in ("pause", "resume", "delete", "add_tags"):
        return JsonResponse({"error": "invalid action"}, status=400)

    check_uuids = request.json.get("checks")
    if not isinstance(check_uuids, list):
        return JsonResponse({"error": "checks must be a list"}, status=400)

    if len(check_uuids) == 0:
        return JsonResponse({"error": "checks list is empty"}, status=400)

    if len(check_uuids) > 50:
        return JsonResponse({"error": "too many checks (max 50)"}, status=400)

    uuids = []
    for u in check_uuids:
        try:
            uuids.append(UUID(str(u)))
        except (ValueError, AttributeError):
            return JsonResponse({"error": "invalid uuid in checks list"}, status=400)

    checks = list(Check.objects.filter(code__in=uuids, project=request.project))
    if len(checks) != len(uuids):
        return JsonResponse(
            {"error": "some checks not found or not in this project"}, status=400
        )

    if action == "pause":
        for check in checks:
            check.create_flip("paused", mark_as_processed=True)
            check.status = "paused"
            check.last_start = None
            check.alert_after = None
            check.save()
        return JsonResponse({"success": True, "count": len(checks)})

    elif action == "resume":
        count = 0
        for check in checks:
            if check.status != "paused":
                continue
            check.create_flip("new", mark_as_processed=True)
            check.status = "new"
            check.last_start = None
            check.last_ping = None
            check.alert_after = None
            check.save()
            count += 1
        return JsonResponse({"success": True, "count": count})

    elif action == "delete":
        count = len(checks)
        for check in checks:
            check.lock_and_delete()
        return JsonResponse({"success": True, "count": count})

    elif action == "add_tags":
        tags = request.json.get("tags", "")
        if not isinstance(tags, str) or not tags.strip():
            return JsonResponse(
                {"error": "tags is required for add_tags action"}, status=400
            )
        new_tags = tags.strip().split()
        for check in checks:
            existing = set(check.tags_list())
            for tag in new_tags:
                existing.add(tag)
            check.tags = " ".join(sorted(existing))
            check.save()
        return JsonResponse({"success": True, "count": len(checks)})
VIEWEOF

###############################################################################
# 3. Add URL route
###############################################################################

python3 << 'PATCH2'
with open("hc/api/urls.py", "r") as f:
    content = f.read()

old = '    path("checks/", views.checks),'

new = '''    path("checks/bulk/", views.bulk_actions, name="hc-api-bulk"),
    path("checks/", views.checks),'''

content = content.replace(old, new, 1)

with open("hc/api/urls.py", "w") as f:
    f.write(content)
PATCH2
