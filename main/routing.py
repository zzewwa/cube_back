from django.urls import re_path

from .consumers import RoomLiveConsumer


websocket_urlpatterns = [
    re_path(r'^ws/rooms/(?P<room_id>\d+)/$', RoomLiveConsumer.as_asgi()),
]
