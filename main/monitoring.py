from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from .consumers import RoomLiveConsumer
from .models import RankedMatchQueue, Room

online_users_gauge = Gauge("mycube_online_users", "Current online users in websocket rooms")
open_rooms_gauge = Gauge("mycube_open_rooms", "Rooms in waiting or running status")
total_users_gauge = Gauge("mycube_total_users", "Total registered users")
queue_users_gauge = Gauge("mycube_ranked_queue_users", "Users currently waiting in ranked queue")


def _online_users_count():
    usernames = set()
    for room_state in RoomLiveConsumer.ROOM_STATE.values():
        for username in room_state.get("connections", {}).values():
            usernames.add(username)
    return len(usernames)


def collect_platform_metrics():
    total_users_gauge.set(User.objects.count())
    open_rooms_gauge.set(
        Room.objects.filter(status__in=(Room.Status.WAITING, Room.Status.RUNNING)).count()
    )
    queue_users_gauge.set(
        RankedMatchQueue.objects.filter(status=RankedMatchQueue.QueueStatus.WAITING).count()
    )
    online_users_gauge.set(_online_users_count())


def _developer_access_allowed(request):
    user = request.user
    if not user or not user.is_authenticated:
        return False
    if user.username != "7box7":
        return False
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    return profile.role == "developer"


def _internal_token_allowed(request):
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.METRICS_BEARER_TOKEN}"
    if auth_header == expected:
        return True
    query_token = request.GET.get("token", "")
    return query_token == settings.METRICS_BEARER_TOKEN


@require_GET
def metrics_view(request):
    if not _developer_access_allowed(request):
        return HttpResponse("Forbidden", status=403)

    collect_platform_metrics()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


@require_GET
def internal_metrics_view(request):
    if not _internal_token_allowed(request):
        return HttpResponse("Forbidden", status=403)

    collect_platform_metrics()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
