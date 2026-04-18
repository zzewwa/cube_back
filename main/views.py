import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Min, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .forms import LoginForm, ProfileUpdateForm, RegisterForm, RoomCreateForm
from .models import (
	PersonalRecordAttempt,
	PublicRecordAttempt,
	Room,
	RoomInvitation,
	RoomParticipant,
	RankedMatchQueue,
	UserProfile,
	CubeState,
)


def _format_record(value):
	if not value or value <= Decimal('0.00'):
		return '—'
	total_centiseconds = int((value * Decimal('100')).quantize(Decimal('1')))
	minutes = total_centiseconds // 6000
	seconds = (total_centiseconds % 6000) // 100
	centiseconds = total_centiseconds % 100
	return f'{minutes:02d}:{seconds:02d}.{centiseconds:02d}'


def _format_datetime(value):
	return timezone.localtime(value).strftime('%d.%m.%Y %H:%M')


def _calculate_average_of_five(queryset):
	recent_attempts = list(queryset[:5])
	if len(recent_attempts) < 5:
		return None
	total = sum(attempt.solve_time_seconds for attempt in recent_attempts)
	return total / Decimal('5')


def _serialize_attempts(queryset, limit=10, include_source=False):
	return [
		{
			'time': _format_record(attempt.solve_time_seconds),
			'datetime': _format_datetime(attempt.achieved_at),
			**({'source': getattr(attempt, 'source', 'single')} if include_source else {}),
		}
		for attempt in queryset[:limit]
	]


def _serialize_attempt_chart(queryset, limit=50):
	recent = list(queryset[:limit])
	recent.reverse()
	result = []
	for index, attempt in enumerate(recent, start=1):
		result.append(
			{
				'index': index,
				'seconds': float(attempt.solve_time_seconds),
				'time': _format_record(attempt.solve_time_seconds),
				'datetime': _format_datetime(attempt.achieved_at),
			}
		)
	return result


def _get_record_stats(queryset):
	best = queryset.aggregate(best=Min('solve_time_seconds'))['best']
	average = _calculate_average_of_five(queryset)
	return {
		'best': _format_record(best),
		'average_of_five': _format_record(average),
		'total_attempts': queryset.count(),
	}


def _build_achievements(profile):
	personal_exists = PersonalRecordAttempt.objects.filter(user=profile.user).exists()
	public_exists = PublicRecordAttempt.objects.filter(user=profile.user).exists()
	achievements = [
		{
			'title': 'Профиль создан',
			'description': 'Аккаунт готов к участию в тренировках и соревнованиях.',
			'earned': True,
		},
		{
			'title': 'Персонализация профиля',
			'description': 'Заполните отображаемое имя и добавьте аватар.',
			'earned': bool(profile.display_name and profile.avatar),
		},
		{
			'title': 'Первый личный рекорд',
			'description': 'Появляется после сохранения первого лучшего времени.',
			'earned': personal_exists,
		},
		{
			'title': 'Публичный зачёт',
			'description': 'Профиль попал в публичный список результатов.',
			'earned': public_exists,
		},
		{
			'title': 'Рейтинговый игрок',
			'description': 'Рейтинг выше 1200 очков.',
			'earned': profile.rating_points >= 1200,
		},
	]
	return achievements


def _build_profile_context(target_user, profile_form=None):
	profile, _ = UserProfile.objects.get_or_create(user=target_user)
	form = profile_form or ProfileUpdateForm(instance=profile, user=target_user)
	personal_records = PersonalRecordAttempt.objects.filter(user=target_user)
	public_records = PublicRecordAttempt.objects.filter(user=target_user)
	if profile.rating_points == 1000 and profile.rating_position == 0 and not personal_records.exists() and not public_records.exists():
		profile.rating_points = 0
		profile.save(update_fields=['rating_points'])
	personal_stats = _get_record_stats(personal_records)
	public_stats = _get_record_stats(public_records)
	achievements = _build_achievements(profile)
	earned_count = sum(1 for achievement in achievements if achievement['earned'])

	return {
		'profile': profile,
		'profile_form': form,
		'profile_summary': {
			'personal_best': personal_stats['best'],
			'public_best': public_stats['best'],
			'rating_position': profile.rating_position,
		},
		'profile_stats': {
			'personal_best': personal_stats['best'],
			'public_best': public_stats['best'],
			'personal_attempts_total': personal_stats['total_attempts'],
			'public_attempts_total': public_stats['total_attempts'],
			'rating_points': profile.rating_points,
			'rating_position': profile.rating_position,
			'achievements_total': max(profile.achievements_total, earned_count),
		},
		'personal_record_history': _serialize_attempts(personal_records, limit=50, include_source=True),
		'public_record_history': _serialize_attempts(public_records),
		'personal_attempt_chart': _serialize_attempt_chart(personal_records, limit=50),
		'public_attempt_chart': _serialize_attempt_chart(public_records, limit=50),
		'profile_achievements': achievements,
	}


def _build_dashboard_context(request, profile_form=None):
	context = _build_profile_context(request.user, profile_form=profile_form)
	context.update(
		{
			'profile_modal_open': request.GET.get('profile') == '1' or context['profile_form'].errors,
			'profile_active_tab': request.GET.get('tab') or 'info',
			'profile_share_path': reverse('public_profile', kwargs={'username': request.user.username}),
			'pending_room_invites_count': RoomInvitation.objects.filter(
				invitee=request.user,
				status=RoomInvitation.InvitationStatus.PENDING,
			).count(),
		}
	)
	return context


def _get_rating_leaderboard(limit=None):
	queryset = UserProfile.objects.select_related('user').order_by('-rating_points', 'user__username')
	if isinstance(limit, int) and limit > 0:
		queryset = queryset[:limit]
	profiles = list(queryset)
	result = []
	for index, profile in enumerate(profiles, start=1):
		result.append(
			{
				'position': index,
				'username': profile.user.username,
				'display_name': profile.visible_name,
				'avatar_url': profile.avatar.url if profile.avatar else '',
				'rating_points': profile.rating_points,
			}
		)
	return result


def _get_user_rating_place(user_id):
	profile = UserProfile.objects.get(user_id=user_id)
	higher = UserProfile.objects.filter(rating_points__gt=profile.rating_points).count()
	return higher + 1, profile.rating_points


def _normalize_ranked_rating(value):
	if value < 0:
		return 0
	return value


@transaction.atomic
def _resolve_ranked_winner(room_id, winner_user_id, winner_elapsed_ms):
	room = Room.objects.select_for_update().get(id=room_id)
	if room.match_type != Room.MatchType.RANKED:
		return None
	if room.ranked_winner_id or room.ranked_finished_at:
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

	winner_participant = next((item for item in participants if item.user_id == winner_user_id), None)
	if not winner_participant:
		return None

	loser_participant = next((item for item in participants if item.user_id != winner_user_id), None)
	if not loser_participant:
		return None

	winner_profile = winner_participant.user.profile
	loser_profile = loser_participant.user.profile
	winner_profile.rating_points = winner_profile.rating_points + 10
	loser_profile.rating_points = _normalize_ranked_rating(loser_profile.rating_points - 10)
	winner_profile.save(update_fields=['rating_points'])
	loser_profile.save(update_fields=['rating_points'])

	winner_seconds = Decimal(str(max(0, winner_elapsed_ms))) / Decimal('1000')
	winner_seconds = winner_seconds.quantize(Decimal('0.01'))
	if winner_seconds > Decimal('0.00'):
		PublicRecordAttempt.objects.create(
			user=winner_participant.user,
			solve_time_seconds=winner_seconds,
		)

	room.status = Room.Status.FINISHED
	room.ranked_winner = winner_participant.user
	room.ranked_finished_at = timezone.now()
	room.save(update_fields=['status', 'ranked_winner', 'ranked_finished_at', 'updated_at'])

	return {
		'room_code': room.room_code,
		'winner_username': winner_participant.user.username,
		'winner_display_name': winner_participant.user.profile.visible_name,
		'winner_user_id': winner_participant.user_id,
		'loser_username': loser_participant.user.username,
		'loser_display_name': loser_participant.user.profile.visible_name,
		'loser_user_id': loser_participant.user_id,
		'winner_elapsed_ms': max(0, int(winner_elapsed_ms)),
	}


@transaction.atomic
def _resolve_ranked_player_left(room_id, leaver_user_id):
	room = Room.objects.select_for_update().get(id=room_id)
	if room.match_type != Room.MatchType.RANKED:
		return None
	if room.ranked_winner_id or room.ranked_finished_at:
		return None

	leaver_participant = RoomParticipant.objects.select_related('user__profile').filter(room=room, user_id=leaver_user_id).first()
	if not leaver_participant:
		return None

	opponent_participant = (
		RoomParticipant.objects.select_related('user__profile')
		.filter(room=room)
		.exclude(user_id=leaver_user_id)
		.order_by('joined_at', 'id')
		.first()
	)

	leaver_profile = leaver_participant.user.profile
	leaver_profile.rating_points = _normalize_ranked_rating(leaver_profile.rating_points - 10)
	leaver_profile.save(update_fields=['rating_points'])

	room.status = Room.Status.FINISHED
	room.ranked_finished_at = timezone.now()
	room.save(update_fields=['status', 'ranked_finished_at', 'updated_at'])

	return {
		'room_code': room.room_code,
		'leaver_username': leaver_participant.user.username,
		'leaver_display_name': leaver_participant.user.profile.visible_name,
		'opponent_username': opponent_participant.user.username if opponent_participant else '',
		'opponent_display_name': opponent_participant.user.profile.visible_name if opponent_participant else '',
	}


def _serialize_room_user(user):
	profile = getattr(user, 'profile', None)
	if profile and profile.avatar:
		avatar_url = profile.avatar.url
	else:
		avatar_url = ''
	return {
		'username': user.username,
		'display_name': profile.visible_name if profile else user.username,
		'avatar_url': avatar_url,
	}


def _serialize_room_participants_payload(room_id):
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


def _broadcast_room_participants(room_id):
	channel_layer = get_channel_layer()
	if not channel_layer:
		return
	async_to_sync(channel_layer.group_send)(
		f'room_live_{room_id}',
		{
			'type': 'participants_event_message',
			'participants': _serialize_room_participants_payload(room_id),
		},
	)


@login_required
def cube_state_load_view(request):
	"""Загрузить сохранённое состояние куба"""
	if request.method != 'GET':
		return HttpResponseNotAllowed(['GET'])
	
	cube_state = CubeState.objects.get_or_create(user=request.user)[0]
	return JsonResponse({
		'cube_materials': cube_state.cube_materials,
		'skin_state': cube_state.skin_state,
		'additional_info': cube_state.additional_info,
	})


@login_required
def cube_state_save_view(request):
	"""Сохранить состояние куба"""
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])
	
	try:
		data = json.loads(request.body)
		cube_state, _ = CubeState.objects.get_or_create(user=request.user)
		cube_state.cube_materials = data.get('cube_materials', '')
		cube_state.skin_state = data.get('skin_state', {})
		cube_state.additional_info = data.get('additional_info', {})
		cube_state.save()
		return JsonResponse({'success': True})
	except (json.JSONDecodeError, ValueError):
		return JsonResponse({'error': 'Invalid payload format'}, status=400)


@login_required
def room_profile_card_view(request, username):
	"""Получить данные профиля игрока для быстрого просмотра"""
	target_user = get_object_or_404(User, username=username)
	profile = UserProfile.objects.get_or_create(user=target_user)[0]
	personal_records = PersonalRecordAttempt.objects.filter(user=target_user)
	public_records = PublicRecordAttempt.objects.filter(user=target_user)
	
	if profile.rating_points == 1000 and profile.rating_position == 0 and not personal_records.exists() and not public_records.exists():
		rating_points = 0
		rating_position = 0
	else:
		rating_points = profile.rating_points
		rating_position = profile.rating_position
	
	personal_stats = _get_record_stats(personal_records)
	public_stats = _get_record_stats(public_records)
	
	if profile.avatar:
		avatar_url = profile.avatar.url
	else:
		avatar_url = ''
	
	return JsonResponse({
		'username': target_user.username,
		'display_name': profile.visible_name or target_user.username,
		'avatar_url': avatar_url,
		'personal_best': personal_stats['best'],
		'public_best': public_stats['best'],
		'rating_points': rating_points,
		'rating_position': rating_position,
		'profile_url': reverse('public_profile', kwargs={'username': target_user.username}),
	})


def login_view(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = LoginForm(request, data=request.POST or None)
	if request.method == 'POST' and form.is_valid():
		login(request, form.get_user())
		return redirect('dashboard')

	return render(
		request,
		'main/auth.html',
		{
			'form': form,
			'title': 'Авторизация',
			'subtitle': 'Вход в соревновательную платформу',
			'submit_label': 'Войти',
			'switch_label': 'Нет аккаунта?',
			'switch_url': 'register',
			'switch_text': 'Создать',
		},
	)


def register_view(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = RegisterForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect('dashboard')

	return render(
		request,
		'main/auth.html',
		{
			'form': form,
			'title': 'Регистрация',
			'subtitle': 'Создание профиля без лишних шагов',
			'submit_label': 'Зарегистрироваться',
			'switch_label': 'Уже есть аккаунт?',
			'switch_url': 'login',
			'switch_text': 'Войти',
		},
	)


@login_required
def dashboard_view(request):
	return render(request, 'main/dashboard.html', _build_dashboard_context(request))


@login_required
def profile_update_view(request):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	profile = get_object_or_404(UserProfile, user=request.user)
	form = ProfileUpdateForm(request.POST, request.FILES, instance=profile, user=request.user)

	if form.is_valid():
		with transaction.atomic():
			form.save()
		messages.success(request, 'Профиль обновлён.')
		return redirect(f"{reverse('dashboard')}?profile=1&tab=info")

	return render(request, 'main/dashboard.html', _build_dashboard_context(request, profile_form=form))


def public_profile_view(request, username):
	target_user = get_object_or_404(User, username=username)
	context = _build_profile_context(target_user)
	context.update({'target_user': target_user})
	return render(request, 'main/public_profile.html', context)


@login_required
def rooms_view(request):
	if request.method == 'POST':
		form = RoomCreateForm(request.POST)
		if form.is_valid():
			room = form.save(commit=False)
			room.created_by = request.user
			room.save()

			RoomParticipant.objects.create(
				room=room,
				user=request.user,
				role=RoomParticipant.ParticipantRole.ORGANIZER,
			)

			raw_payload = (form.cleaned_data.get('invite_payload') or '').strip()
			if raw_payload:
				try:
					payload = json.loads(raw_payload)
				except json.JSONDecodeError:
					payload = []

				for item in payload:
					username = str(item.get('username', '')).strip()
					invited_role = str(item.get('role', '')).strip()
					if not username or username == request.user.username:
						continue
					if invited_role not in (
						RoomParticipant.ParticipantRole.PLAYER,
						RoomParticipant.ParticipantRole.SPECTATOR,
					):
						continue
					invitee = User.objects.filter(username=username).first()
					if not invitee:
						continue
					RoomInvitation.objects.update_or_create(
						room=room,
						invitee=invitee,
						defaults={
							'inviter': request.user,
							'as_role': invited_role,
							'status': RoomInvitation.InvitationStatus.PENDING,
							'responded_at': None,
						},
					)

			messages.success(request, 'Комната создана.')
			return redirect('room_detail', room_code=room.room_code)
	else:
		form = RoomCreateForm()

	owned_rooms = Room.objects.filter(created_by=request.user).prefetch_related('participants', 'invitations')
	joined_rooms = Room.objects.filter(participants__user=request.user).exclude(created_by=request.user).distinct()
	pending_invitations = RoomInvitation.objects.filter(
		invitee=request.user,
		status=RoomInvitation.InvitationStatus.PENDING,
	).select_related('room', 'inviter')

	context = {
		'room_form': form,
		'owned_rooms': owned_rooms,
		'joined_rooms': joined_rooms,
		'pending_invitations': pending_invitations,
		'pending_room_invites_count': pending_invitations.count(),
	}
	return render(request, 'main/rooms.html', context)


@login_required
def ranked_game_view(request):
	position, rating_points = _get_user_rating_place(request.user.id)
	context = {
		'leaderboard': _get_rating_leaderboard(),
		'my_rating_position': position,
		'my_rating_points': rating_points,
		'pending_room_invites_count': RoomInvitation.objects.filter(
			invitee=request.user,
			status=RoomInvitation.InvitationStatus.PENDING,
		).count(),
	}
	return render(request, 'main/ranked_game.html', context)


@login_required
def ranked_queue_join_view(request):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	active_ranked_room = (
		RoomParticipant.objects.select_related('room')
		.filter(
			user=request.user,
			room__match_type=Room.MatchType.RANKED,
			room__status__in=(Room.Status.WAITING, Room.Status.RUNNING),
		)
		.order_by('-joined_at')
		.first()
	)
	if active_ranked_room:
		return JsonResponse({'ok': True, 'matched': True, 'room_code': active_ranked_room.room.room_code})

	with transaction.atomic():
		entry, _ = RankedMatchQueue.objects.select_for_update().get_or_create(user=request.user)
		if entry.status == RankedMatchQueue.QueueStatus.MATCHED and entry.matched_room_id:
			return JsonResponse({'ok': True, 'matched': True, 'room_code': entry.matched_room.room_code})

		opponent_entry = (
			RankedMatchQueue.objects.select_for_update()
			.filter(status=RankedMatchQueue.QueueStatus.WAITING)
			.exclude(user=request.user)
			.order_by('joined_at', 'id')
			.first()
		)

		if not opponent_entry:
			entry.status = RankedMatchQueue.QueueStatus.WAITING
			entry.matched_room = None
			entry.save(update_fields=['status', 'matched_room', 'updated_at'])
			waiting_count = RankedMatchQueue.objects.filter(status=RankedMatchQueue.QueueStatus.WAITING).count()
			return JsonResponse({'ok': True, 'matched': False, 'waiting_count': waiting_count})

		room = Room.objects.create(
			name=f'{opponent_entry.user.username} vs {request.user.username}',
			created_by=opponent_entry.user,
			match_type=Room.MatchType.RANKED,
			max_players=2,
			max_spectators=0,
			start_mode=Room.StartMode.ALL_INVITED,
			countdown_seconds=5,
			study_seconds=10,
			ranked_auto_start_at=timezone.now() + timedelta(minutes=1),
		)

		RoomParticipant.objects.get_or_create(
			room=room,
			user=opponent_entry.user,
			defaults={'role': RoomParticipant.ParticipantRole.PLAYER},
		)
		RoomParticipant.objects.get_or_create(
			room=room,
			user=request.user,
			defaults={'role': RoomParticipant.ParticipantRole.PLAYER},
		)

		opponent_entry.status = RankedMatchQueue.QueueStatus.MATCHED
		opponent_entry.matched_room = room
		opponent_entry.save(update_fields=['status', 'matched_room', 'updated_at'])

		entry.status = RankedMatchQueue.QueueStatus.MATCHED
		entry.matched_room = room
		entry.save(update_fields=['status', 'matched_room', 'updated_at'])

	return JsonResponse({'ok': True, 'matched': True, 'room_code': room.room_code})


@login_required
def ranked_queue_status_view(request):
	entry = RankedMatchQueue.objects.filter(user=request.user).select_related('matched_room').first()
	if entry and entry.status == RankedMatchQueue.QueueStatus.MATCHED and entry.matched_room_id:
		return JsonResponse({'ok': True, 'in_queue': False, 'matched': True, 'room_code': entry.matched_room.room_code})

	if not entry or entry.status != RankedMatchQueue.QueueStatus.WAITING:
		waiting_count = RankedMatchQueue.objects.filter(status=RankedMatchQueue.QueueStatus.WAITING).count()
		return JsonResponse({'ok': True, 'in_queue': False, 'matched': False, 'waiting_count': waiting_count, 'wait_seconds': 0})

	wait_seconds = max(0, int((timezone.now() - entry.joined_at).total_seconds()))
	waiting_count = RankedMatchQueue.objects.filter(status=RankedMatchQueue.QueueStatus.WAITING).count()
	return JsonResponse(
		{
			'ok': True,
			'in_queue': True,
			'matched': False,
			'waiting_count': waiting_count,
			'wait_seconds': wait_seconds,
		}
	)


@login_required
def room_user_search_view(request):
	query = (request.GET.get('q') or '').strip()
	if len(query) < 2:
		return JsonResponse({'results': []})

	users = (
		User.objects.select_related('profile')
		.exclude(pk=request.user.pk)
		.filter(Q(username__icontains=query) | Q(profile__display_name__icontains=query))[:10]
	)
	return JsonResponse({'results': [_serialize_room_user(user) for user in users]})


@login_required
def room_pending_invitations_view(request):
	pending_invitations = RoomInvitation.objects.filter(
		invitee=request.user,
		status=RoomInvitation.InvitationStatus.PENDING,
	).select_related('room', 'inviter')

	return JsonResponse(
		{
			'count': pending_invitations.count(),
			'invitations': [
				{
					'id': invitation.id,
					'room_name': invitation.room.name,
					'room_code': invitation.room.room_code,
					'inviter_username': invitation.inviter.username,
					'as_role_display': invitation.get_as_role_display(),
				}
				for invitation in pending_invitations
			],
		}
	)


@login_required
def room_invitation_action_view(request, invitation_id, action):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	invitation = get_object_or_404(RoomInvitation, id=invitation_id, invitee=request.user)
	if invitation.status != RoomInvitation.InvitationStatus.PENDING:
		return redirect('rooms')

	if action == 'accept':
		invitation.status = RoomInvitation.InvitationStatus.ACCEPTED
		invitation.responded_at = timezone.now()
		invitation.save(update_fields=['status', 'responded_at'])
		RoomParticipant.objects.get_or_create(
			room=invitation.room,
			user=request.user,
			defaults={'role': invitation.as_role},
		)
		_broadcast_room_participants(invitation.room_id)
		return redirect('room_detail', room_code=invitation.room.room_code)

	if action == 'decline':
		invitation.status = RoomInvitation.InvitationStatus.DECLINED
		invitation.responded_at = timezone.now()
		invitation.save(update_fields=['status', 'responded_at'])

	return redirect('rooms')


@login_required
def room_invite_create_view(request, room_code):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	room = get_object_or_404(Room, room_code=room_code)
	organizer_participation = RoomParticipant.objects.filter(
		room=room,
		user=request.user,
		role=RoomParticipant.ParticipantRole.ORGANIZER,
	).exists()
	if not organizer_participation:
		return JsonResponse({'error': 'Недостаточно прав'}, status=403)

	try:
		if request.content_type and 'application/json' in request.content_type:
			payload = json.loads(request.body.decode('utf-8') or '{}')
		else:
			payload = request.POST
	except (json.JSONDecodeError, ValueError):
		return JsonResponse({'error': 'Неверный формат данных'}, status=400)

	username = str(payload.get('username') or '').strip()
	role = str(payload.get('role') or '').strip()
	if not username:
		return JsonResponse({'error': 'username обязателен'}, status=400)
	if role not in (RoomParticipant.ParticipantRole.PLAYER, RoomParticipant.ParticipantRole.SPECTATOR):
		return JsonResponse({'error': 'Некорректная роль'}, status=400)

	invitee = User.objects.filter(username=username).first()
	if not invitee:
		return JsonResponse({'error': 'Пользователь не найден'}, status=404)
	if invitee.id == request.user.id:
		return JsonResponse({'error': 'Нельзя приглашать самого себя'}, status=400)

	already_participant = RoomParticipant.objects.filter(room=room, user=invitee).exists()
	if already_participant:
		return JsonResponse({'error': 'Пользователь уже в комнате'}, status=400)

	invitation, _ = RoomInvitation.objects.update_or_create(
		room=room,
		invitee=invitee,
		defaults={
			'inviter': request.user,
			'as_role': role,
			'status': RoomInvitation.InvitationStatus.PENDING,
			'responded_at': None,
		},
	)

	return JsonResponse(
		{
			'ok': True,
			'invitation_id': invitation.id,
			'invitee': _serialize_room_user(invitee),
			'role': role,
		}
	)


@login_required
def room_detail_view(request, room_code):
	room = get_object_or_404(Room.objects.select_related('created_by'), room_code=room_code)
	participant = RoomParticipant.objects.filter(room=room, user=request.user).first()

	if not participant:
		return redirect('rooms')

	all_participants = list(
		RoomParticipant.objects.filter(room=room)
		.select_related('user__profile')
		.order_by('joined_at', 'id')
	)
	players = [
		item
		for item in all_participants
		if item.role in (RoomParticipant.ParticipantRole.PLAYER, RoomParticipant.ParticipantRole.ORGANIZER)
	]
	spectators = [item for item in all_participants if item.role == RoomParticipant.ParticipantRole.SPECTATOR]
	organizers = [item for item in all_participants if item.role == RoomParticipant.ParticipantRole.ORGANIZER]
	can_play = participant.role in (RoomParticipant.ParticipantRole.PLAYER, RoomParticipant.ParticipantRole.ORGANIZER)
	can_manage_timer = participant.role == RoomParticipant.ParticipantRole.ORGANIZER and room.match_type != Room.MatchType.RANKED

	RankedMatchQueue.objects.filter(user=request.user).delete()

	player_payload = []
	for index, entry in enumerate(players):
		player_payload.append(
			{
				'index': index,
				'is_self': entry.user_id == request.user.id,
				'is_organizer': entry.role == RoomParticipant.ParticipantRole.ORGANIZER,
				'role': entry.role,
				'username': entry.user.username,
				'display_name': entry.user.profile.visible_name,
				'avatar_url': entry.user.profile.avatar.url if entry.user.profile.avatar else '',
			}
		)

	spectator_payload = [
		{
			'username': entry.user.username,
			'display_name': entry.user.profile.visible_name,
			'avatar_url': entry.user.profile.avatar.url if entry.user.profile.avatar else '',
		}
		for entry in spectators
	]

	display_room_name = room.name
	if room.match_type == Room.MatchType.RANKED and display_room_name.startswith('Рейтинговая игра:'):
		display_room_name = display_room_name.split(':', 1)[1].strip()

	context = {
		'room': room,
		'room_display_name': display_room_name,
		'room_participant': participant,
		'room_players': player_payload,
		'room_spectators': spectator_payload,
		'room_organizers': organizers,
		'room_user_can_play': can_play,
		'room_user_can_manage_timer': can_manage_timer,
		'room_live_payload': {
			'roomId': room.id,
			'roomCode': room.room_code,
			'matchType': room.match_type,
			'rankedAutoStartAtMs': int(room.ranked_auto_start_at.timestamp() * 1000) if room.ranked_auto_start_at else None,
			'selfUsername': request.user.username,
			'selfRole': participant.role,
			'canPlay': can_play,
			'canManageTimer': can_manage_timer,
			'startMode': room.start_mode,
			'countdownSeconds': room.countdown_seconds,
			'studySeconds': room.study_seconds,
			'players': player_payload,
			'spectators': spectator_payload,
		},
		'pending_room_invites_count': RoomInvitation.objects.filter(
			invitee=request.user,
			status=RoomInvitation.InvitationStatus.PENDING,
		).count(),
	}
	return render(request, 'main/room_detail.html', context)


@login_required
def room_leave_view(request, room_code):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	participant = get_object_or_404(
		RoomParticipant.objects.select_related('room'),
		room__room_code=room_code,
		user=request.user,
	)
	room = participant.room
	if room.match_type == Room.MatchType.RANKED and room.status == Room.Status.WAITING:
		remaining_opponents = list(
			RoomParticipant.objects.select_related('user__profile')
			.filter(room=room)
			.exclude(user_id=request.user.id)
		)

		channel_layer = get_channel_layer()
		if channel_layer:
			async_to_sync(channel_layer.group_send)(
				f'room_live_{room.id}',
				{
					'type': 'game_event_message',
					'event': {
						'action': 'ranked_room_cancelled',
						'leaver_username': request.user.username,
						'opponents': [item.user.username for item in remaining_opponents],
					},
				},
			)

		room.delete()
		return redirect('ranked_game')

	if room.match_type == Room.MatchType.RANKED and room.status == Room.Status.RUNNING:
		resolved = _resolve_ranked_player_left(room.id, request.user.id)
		if resolved:
			channel_layer = get_channel_layer()
			if channel_layer:
				async_to_sync(channel_layer.group_send)(
					f'room_live_{room.id}',
					{
						'type': 'game_event_message',
						'event': {
							'action': 'opponent_left',
							'leaver_username': resolved['leaver_username'],
							'leaver_display_name': resolved['leaver_display_name'],
							'opponent_username': resolved['opponent_username'],
							'opponent_display_name': resolved['opponent_display_name'],
						},
					},
				)

	was_organizer = participant.role == RoomParticipant.ParticipantRole.ORGANIZER
	participant.delete()

	remaining_participants = list(
		RoomParticipant.objects.filter(room=room)
		.select_related('user')
		.order_by('joined_at', 'id')
	)
	if not remaining_participants:
		room.delete()
		if room.match_type == Room.MatchType.RANKED:
			return redirect('ranked_game')
		return redirect('rooms')

	if was_organizer:
		preferred_roles = {
			RoomParticipant.ParticipantRole.PLAYER: 0,
			RoomParticipant.ParticipantRole.ORGANIZER: 0,
			RoomParticipant.ParticipantRole.SPECTATOR: 1,
		}
		successor = sorted(
			remaining_participants,
			key=lambda item: (preferred_roles.get(item.role, 2), item.joined_at, item.id),
		)[0]
		if successor.role != RoomParticipant.ParticipantRole.ORGANIZER:
			successor.role = RoomParticipant.ParticipantRole.ORGANIZER
			successor.save(update_fields=['role'])
		if room.created_by_id != successor.user_id:
			room.created_by = successor.user
			room.save(update_fields=['created_by'])

	_broadcast_room_participants(room.id)

	if room.match_type == Room.MatchType.RANKED:
		return redirect('ranked_game')
	return redirect('rooms')


@csrf_exempt
@login_required
def personal_record_attempt_create_view(request):
	if request.method != 'POST':
		return HttpResponseNotAllowed(['POST'])

	try:
		if request.content_type and 'application/json' in request.content_type:
			payload = json.loads(request.body.decode('utf-8') or '{}')
		else:
			payload = request.POST

		raw_value = payload.get('solve_time_seconds')
		if raw_value is None:
			return JsonResponse({'error': 'solve_time_seconds is required'}, status=400)

		attempt_source = str(payload.get('attempt_source') or PersonalRecordAttempt.AttemptSource.SINGLE).strip().lower()
		if attempt_source not in (
			PersonalRecordAttempt.AttemptSource.SINGLE,
			PersonalRecordAttempt.AttemptSource.ROOM,
		):
			attempt_source = PersonalRecordAttempt.AttemptSource.SINGLE

		solve_time = Decimal(str(raw_value)).quantize(Decimal('0.01'))
		if solve_time <= Decimal('0') or solve_time > Decimal('999.99'):
			return JsonResponse({'error': 'solve_time_seconds must be between 0 and 999.99'}, status=400)
	except (json.JSONDecodeError, TypeError, ValueError, InvalidOperation):
		return JsonResponse({'error': 'Invalid payload format'}, status=400)

	attempt = PersonalRecordAttempt.objects.create(
		user=request.user,
		solve_time_seconds=solve_time,
		source=attempt_source,
	)
	return JsonResponse(
		{
			'ok': True,
			'attempt': {
				'id': attempt.id,
				'solve_time_seconds': f'{attempt.solve_time_seconds:.2f}',
				'achieved_at': _format_datetime(attempt.achieved_at),
			},
		}
	)


def logout_view(request):
	logout(request)
	return redirect('login')
