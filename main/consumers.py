import json
from decimal import Decimal

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.utils import timezone

from .models import PublicRecordAttempt, Room, RoomParticipant


class RoomLiveConsumer(AsyncWebsocketConsumer):
    ROOM_STATE = {}

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.room_id = str(self.scope['url_route']['kwargs']['room_id'])
        room_context = await self._get_room_context(user.id, self.room_id)
        if not room_context:
            await self.close(code=4403)
            return

        self.room_group_name = f'room_live_{self.room_id}'
        self.username = user.username
        self.participant_role = room_context['role']
        self.room_start_mode = room_context['start_mode']

        room_state = self.ROOM_STATE.setdefault(self.room_id, {'players': {}, 'connections': {}, 'game': None})
        room_state['connections'][self.channel_name] = self.username

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(
            text_data=json.dumps(
                {
                    'type': 'snapshot',
                    'players': room_state['players'],
                    'game': room_state.get('game'),
                    'participants': await self._get_room_participants_payload(self.room_id),
                }
            )
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'presence_event',
                'username': self.username,
                'online': True,
            },
        )
        await self._broadcast_participants()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        room_state = self.ROOM_STATE.get(getattr(self, 'room_id', ''))
        if not room_state:
            return

        room_state['connections'].pop(self.channel_name, None)

        if hasattr(self, 'room_group_name') and hasattr(self, 'username'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'presence_event',
                    'username': self.username,
                    'online': False,
                },
            )
            await self._broadcast_participants()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = payload.get('type')
        if message_type not in ('cube_state', 'camera_state', 'game_event'):
            return

        room_state = self.ROOM_STATE.setdefault(self.room_id, {'players': {}, 'connections': {}, 'game': None})
        player_state = room_state['players'].setdefault(self.username, {})

        if message_type == 'game_event':
            action = payload.get('action')
            if action == 'ranked_round_started':
                if room_context := await self._mark_ranked_room_running(self.room_id):
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'game_event_message',
                            'event': {
                                'action': 'ranked_round_started',
                                'started_at_ms': room_context['started_at_ms'],
                            },
                        },
                    )
                return

            if action == 'solve_complete':
                elapsed_ms = payload.get('elapsed_ms')
                if not isinstance(elapsed_ms, (int, float)):
                    return
                result = await self._resolve_ranked_winner(
                    room_id=int(self.room_id),
                    winner_user_id=self.scope['user'].id,
                    winner_elapsed_ms=int(elapsed_ms),
                )
                if result:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'game_event_message',
                            'event': {
                                'action': 'ranked_finished',
                                'winner_username': result['winner_username'],
                                'winner_display_name': result['winner_display_name'],
                                'loser_username': result['loser_username'],
                                'loser_display_name': result['loser_display_name'],
                                'winner_elapsed_ms': result['winner_elapsed_ms'],
                            },
                        },
                    )
                return

            if (
                self.participant_role != RoomParticipant.ParticipantRole.ORGANIZER
                or self.room_start_mode != Room.StartMode.OWNER
                or action != 'start_round'
            ):
                return

            countdown_seconds = payload.get('countdown_seconds')
            study_seconds = payload.get('study_seconds')
            game_payload = {
                'action': 'start_round',
                'started_at_ms': int(timezone.now().timestamp() * 1000),
                'countdown_seconds': int(countdown_seconds) if isinstance(countdown_seconds, int) else 5,
                'study_seconds': int(study_seconds) if isinstance(study_seconds, int) else 10,
                'initiated_by': self.username,
            }
            room_state['game'] = game_payload
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_event_message',
                    'event': game_payload,
                },
            )
            return

        if message_type == 'cube_state':
            materials = payload.get('materials')
            skin_id = payload.get('skin_id')
            appearance = payload.get('appearance')
            if isinstance(materials, list):
                player_state['materials'] = materials
                if isinstance(skin_id, str) and skin_id:
                    player_state['skin_id'] = skin_id
                if isinstance(appearance, dict):
                    player_state['appearance'] = appearance
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'cube_state_event',
                        'username': self.username,
                        'materials': materials,
                        'skin_id': player_state.get('skin_id') or '',
                        'appearance': player_state.get('appearance') or {},
                    },
                )
            return

        camera = payload.get('camera')
        if isinstance(camera, dict):
            player_state['camera'] = {
                'position': camera.get('position'),
                'target': camera.get('target'),
            }
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'camera_state_event',
                    'username': self.username,
                    'camera': player_state['camera'],
                },
            )

    @staticmethod
    @sync_to_async
    def _mark_ranked_room_running(room_id):
        room = Room.objects.filter(id=room_id, match_type=Room.MatchType.RANKED).first()
        if not room:
            return None
        if room.status == Room.Status.WAITING:
            room.status = Room.Status.RUNNING
            room.save(update_fields=['status', 'updated_at'])
        return {'started_at_ms': int(timezone.now().timestamp() * 1000)}

    @staticmethod
    @sync_to_async
    def _resolve_ranked_winner(room_id, winner_user_id, winner_elapsed_ms):
        with transaction.atomic():
            room = Room.objects.select_for_update().filter(id=room_id).first()
            if not room or room.match_type != Room.MatchType.RANKED:
                return None
            if room.ranked_winner_id or room.ranked_finished_at:
                return None
            if room.status != Room.Status.RUNNING:
                return None

            participants = list(
                RoomParticipant.objects.select_related('user__profile')
                .filter(
                    room=room,
                    role__in=(RoomParticipant.ParticipantRole.PLAYER, RoomParticipant.ParticipantRole.ORGANIZER),
                )
                .order_by('joined_at', 'id')
            )
            if len(participants) < 2:
                return None

            winner = next((item for item in participants if item.user_id == winner_user_id), None)
            if not winner:
                return None
            loser = next((item for item in participants if item.user_id != winner_user_id), None)
            if not loser:
                return None

            winner_profile = winner.user.profile
            loser_profile = loser.user.profile
            winner_profile.rating_points = winner_profile.rating_points + 10
            loser_profile.rating_points = max(0, loser_profile.rating_points - 10)
            winner_profile.save(update_fields=['rating_points'])
            loser_profile.save(update_fields=['rating_points'])

            winner_seconds = (Decimal(str(max(0, int(winner_elapsed_ms)))) / Decimal('1000')).quantize(Decimal('0.01'))
            if winner_seconds > Decimal('0.00'):
                PublicRecordAttempt.objects.create(
                    user=winner.user,
                    solve_time_seconds=winner_seconds,
                )

            room.status = Room.Status.FINISHED
            room.ranked_winner = winner.user
            room.ranked_finished_at = timezone.now()
            room.save(update_fields=['status', 'ranked_winner', 'ranked_finished_at', 'updated_at'])

            return {
                'winner_username': winner.user.username,
                'winner_display_name': winner.user.profile.visible_name,
                'loser_username': loser.user.username,
                'loser_display_name': loser.user.profile.visible_name,
                'winner_elapsed_ms': max(0, int(winner_elapsed_ms)),
            }

    async def cube_state_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'cube_state',
                    'username': event['username'],
                    'materials': event['materials'],
                    'skin_id': event.get('skin_id') or '',
                    'appearance': event.get('appearance') or {},
                }
            )
        )

    async def camera_state_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'camera_state',
                    'username': event['username'],
                    'camera': event['camera'],
                }
            )
        )

    async def presence_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'presence',
                    'username': event['username'],
                    'online': event['online'],
                }
            )
        )

    @staticmethod
    @sync_to_async
    def _get_room_context(user_id, room_id):
        participant = (
            RoomParticipant.objects.select_related('room')
            .filter(room_id=room_id, user_id=user_id)
            .first()
        )
        if not participant:
            return None
        return {
            'role': participant.role,
            'start_mode': participant.room.start_mode,
        }

    async def game_event_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'game_event',
                    'event': event['event'],
                }
            )
        )

    async def participants_event_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'participants',
                    'participants': event['participants'],
                }
            )
        )

    async def _broadcast_participants(self):
        participants = await self._get_room_participants_payload(self.room_id)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'participants_event_message',
                'participants': participants,
            },
        )

    @staticmethod
    @sync_to_async
    def _get_room_participants_payload(room_id):
        participants = list(
            RoomParticipant.objects.filter(room_id=room_id)
            .select_related('user__profile')
            .order_by('joined_at', 'id')
        )
        payload = {
            'players': [],
            'spectators': [],
        }
        for participant in participants:
            item = {
                'username': participant.user.username,
                'display_name': participant.user.profile.visible_name,
                'avatar_url': participant.user.profile.avatar.url if participant.user.profile.avatar else '',
                'role': participant.role,
                'is_organizer': participant.role == RoomParticipant.ParticipantRole.ORGANIZER,
            }
            if participant.role in (RoomParticipant.ParticipantRole.PLAYER, RoomParticipant.ParticipantRole.ORGANIZER):
                payload['players'].append(item)
            else:
                payload['spectators'].append(item)
        return payload
