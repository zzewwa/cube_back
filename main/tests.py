import json
from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import ProfileUpdateForm, RegisterForm
from .models import PersonalRecordAttempt, PublicRecordAttempt, RankedMatchQueue, Room, RoomInvitation, RoomParticipant, UserProfile


class UserProfileTests(TestCase):
	def test_register_rejects_profane_username_in_latin(self):
		form = RegisterForm(
			data={
				'username': 'govno_player',
				'password1': 'Secret123A',
				'password2': 'Secret123A',
			}
		)

		self.assertFalse(form.is_valid())
		self.assertIn('username', form.errors)
		self.assertIn('Логин содержит недопустимые слова', form.errors['username'][0])

	def test_register_rejects_profane_username_in_cyrillic(self):
		form = RegisterForm(
			data={
				'username': 'говно_игрок',
				'password1': 'Secret123A',
				'password2': 'Secret123A',
			}
		)

		self.assertFalse(form.is_valid())
		self.assertIn('username', form.errors)
		self.assertIn('Логин содержит недопустимые слова', form.errors['username'][0])

	def test_profile_update_rejects_profane_display_name(self):
		user = User.objects.create_user(username='clean_user', password='Secret123')
		form = ProfileUpdateForm(
			data={
				'display_name': 'G0vn0 king',
				'first_name': '',
				'last_name': '',
				'email': '',
				'country': '',
				'city': '',
				'telegram': '',
				'birth_date': '',
			},
			instance=user.profile,
			user=user,
		)

		self.assertFalse(form.is_valid())
		self.assertIn('display_name', form.errors)
		self.assertIn('Отображаемое имя содержит недопустимые слова', form.errors['display_name'][0])

	def test_profile_created_automatically_for_new_user(self):
		user = User.objects.create_user(username='tester', password='Secret123')

		self.assertTrue(UserProfile.objects.filter(user=user).exists())

	def test_profile_update_saves_user_and_profile_data(self):
		user = User.objects.create_user(username='solver', password='Secret123')
		self.client.login(username='solver', password='Secret123')

		avatar = SimpleUploadedFile(
			'avatar.gif',
			(
				b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
				b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00'
				b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
			),
			content_type='image/gif',
		)

		response = self.client.post(
			reverse('profile_update'),
			{
				'display_name': 'Cube Master',
				'first_name': 'Ivan',
				'last_name': 'Petrov',
				'email': 'ivan@example.com',
				'country': 'Россия',
				'city': 'Москва',
				'telegram': '@ivan',
				'birth_date': '2000-01-01',
				'avatar': avatar,
			},
			follow=True,
		)

		user.refresh_from_db()
		profile = user.profile

		self.assertEqual(response.status_code, 200)
		self.assertEqual(user.first_name, 'Ivan')
		self.assertEqual(user.last_name, 'Petrov')
		self.assertEqual(user.email, 'ivan@example.com')
		self.assertEqual(profile.display_name, 'Cube Master')
		self.assertEqual(profile.country, 'Россия')
		self.assertEqual(profile.city, 'Москва')
		self.assertEqual(profile.birth_date, date(2000, 1, 1))
		self.assertTrue(bool(profile.avatar))

	def test_display_name_must_be_unique(self):
		first_user = User.objects.create_user(username='first', password='Secret123')
		second_user = User.objects.create_user(username='second', password='Secret123')
		first_user.profile.display_name = 'Unique Name'
		first_user.profile.save()

		self.client.login(username='second', password='Secret123')
		response = self.client.post(
			reverse('profile_update'),
			{
				'display_name': 'Unique Name',
				'first_name': '',
				'last_name': '',
				'email': '',
				'country': '',
				'city': '',
				'telegram': '',
				'birth_date': '',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Это отображаемое имя уже занято.')

	def test_dashboard_context_contains_profile_stats(self):
		user = User.objects.create_user(username='ranked', password='Secret123')
		profile = user.profile
		profile.rating_points = 1280
		profile.save()
		PersonalRecordAttempt.objects.create(user=user, solve_time_seconds=Decimal('12.34'))
		PersonalRecordAttempt.objects.create(user=user, solve_time_seconds=Decimal('13.20'))
		PublicRecordAttempt.objects.create(user=user, solve_time_seconds=Decimal('13.21'))
		self.client.login(username='ranked', password='Secret123')

		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['profile_stats']['personal_best'], '00:12.34')
		self.assertEqual(response.context['profile_stats']['public_best'], '00:13.21')
		self.assertEqual(response.context['profile_stats']['rating_points'], 1280)
		self.assertEqual(response.context['profile_stats']['personal_attempts_total'], 2)

	def test_legacy_default_rating_is_reset_for_empty_profile(self):
		user = User.objects.create_user(username='legacy', password='Secret123')
		user.profile.rating_points = 1000
		user.profile.rating_position = 0
		user.profile.save()
		self.client.login(username='legacy', password='Secret123')

		response = self.client.get(reverse('dashboard'))

		user.profile.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['profile_stats']['rating_points'], 0)
		self.assertEqual(user.profile.rating_points, 0)

	def test_public_profile_url_contains_username(self):
		user = User.objects.create_user(username='shareme', password='Secret123')
		response = self.client.get(reverse('public_profile', kwargs={'username': user.username}))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '@shareme')

	def test_create_personal_record_attempt_from_json(self):
		user = User.objects.create_user(username='timer_user', password='Secret123')
		self.client.login(username='timer_user', password='Secret123')

		response = self.client.post(
			reverse('personal_record_attempt_create'),
			data='{"solve_time_seconds": "14.37"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(PersonalRecordAttempt.objects.filter(user=user).count(), 1)
		attempt = PersonalRecordAttempt.objects.get(user=user)
		self.assertEqual(attempt.solve_time_seconds, Decimal('14.37'))

	def test_create_personal_record_attempt_with_game_history(self):
		user = User.objects.create_user(username='timer_history', password='Secret123')
		self.client.login(username='timer_history', password='Secret123')
		initial_cube_state = [['h', 'h', 'h', 'h', 'h', 'h'] for _ in range(27)]
		payload = {
			'solve_time_seconds': '18.52',
			'move_history': ['Q', '!D', '↑'],
			'initial_cube_state': initial_cube_state,
		}

		response = self.client.post(
			reverse('personal_record_attempt_create'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		attempt = PersonalRecordAttempt.objects.get(user=user)
		self.assertEqual(attempt.solve_time_seconds, Decimal('18.52'))
		self.assertEqual(attempt.move_history, ['Q', '!D', '↑'])
		self.assertEqual(attempt.initial_cube_state, initial_cube_state)

	def test_create_personal_record_attempt_rejects_invalid_value(self):
		user = User.objects.create_user(username='timer_bad', password='Secret123')
		self.client.login(username='timer_bad', password='Secret123')

		response = self.client.post(
			reverse('personal_record_attempt_create'),
			data='{"solve_time_seconds": "0"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(PersonalRecordAttempt.objects.filter(user=user).count(), 0)

	def test_create_room_adds_creator_as_organizer(self):
		user = User.objects.create_user(username='room_owner', password='Secret123')
		self.client.login(username='room_owner', password='Secret123')

		response = self.client.post(
			reverse('rooms'),
			{
				'name': 'Тестовая комната',
				'max_players': 4,
				'max_spectators': 10,
				'start_mode': 'owner',
				'countdown_seconds': 5,
				'study_seconds': 10,
				'invite_payload': '[]',
			},
		)

		self.assertEqual(response.status_code, 302)
		room = Room.objects.get(name='Тестовая комната')
		self.assertEqual(room.created_by, user)
		self.assertTrue(
			RoomParticipant.objects.filter(
				room=room,
				user=user,
				role=RoomParticipant.ParticipantRole.ORGANIZER,
			).exists()
		)

	def test_accept_room_invitation_creates_participant(self):
		owner = User.objects.create_user(username='owner', password='Secret123')
		invitee = User.objects.create_user(username='invitee', password='Secret123')
		room = Room.objects.create(
			name='Room A',
			created_by=owner,
			max_players=4,
			max_spectators=4,
		)
		invitation = RoomInvitation.objects.create(
			room=room,
			inviter=owner,
			invitee=invitee,
			as_role=RoomParticipant.ParticipantRole.PLAYER,
		)

		self.client.login(username='invitee', password='Secret123')
		response = self.client.post(reverse('room_invitation_action', kwargs={'invitation_id': invitation.id, 'action': 'accept'}))

		invitation.refresh_from_db()
		self.assertEqual(response.status_code, 302)
		self.assertEqual(invitation.status, RoomInvitation.InvitationStatus.ACCEPTED)
		self.assertTrue(RoomParticipant.objects.filter(room=room, user=invitee, role=RoomParticipant.ParticipantRole.PLAYER).exists())

	def test_room_user_search_returns_candidates(self):
		owner = User.objects.create_user(username='search_owner', password='Secret123')
		target = User.objects.create_user(username='search_target', password='Secret123')
		target.profile.display_name = 'Search Target'
		target.profile.save()

		self.client.login(username='search_owner', password='Secret123')
		response = self.client.get(reverse('room_user_search'), {'q': 'target'})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(any(item['username'] == 'search_target' for item in payload['results']))

	def test_room_detail_includes_organizer_in_active_players(self):
		owner = User.objects.create_user(username='organizer_user', password='Secret123')
		room = Room.objects.create(name='Arena', created_by=owner, max_players=4, max_spectators=4)
		RoomParticipant.objects.create(room=room, user=owner, role=RoomParticipant.ParticipantRole.ORGANIZER)

		self.client.login(username='organizer_user', password='Secret123')
		response = self.client.get(reverse('room_detail', kwargs={'room_id': room.id}))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.context['room_players']), 1)
		self.assertEqual(response.context['room_players'][0]['username'], 'organizer_user')
		self.assertTrue(response.context['room_user_can_play'])
		self.assertTrue(response.context['room_user_can_manage_timer'])

	def test_room_leave_transfers_organizer_role(self):
		owner = User.objects.create_user(username='owner_leave', password='Secret123')
		player = User.objects.create_user(username='next_player', password='Secret123')
		room = Room.objects.create(name='Transfer room', created_by=owner, max_players=4, max_spectators=4)
		RoomParticipant.objects.create(room=room, user=owner, role=RoomParticipant.ParticipantRole.ORGANIZER)
		RoomParticipant.objects.create(room=room, user=player, role=RoomParticipant.ParticipantRole.PLAYER)

		self.client.login(username='owner_leave', password='Secret123')
		response = self.client.post(reverse('room_leave', kwargs={'room_id': room.id}))

		room.refresh_from_db()
		participant = RoomParticipant.objects.get(room=room, user=player)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(room.created_by, player)
		self.assertEqual(participant.role, RoomParticipant.ParticipantRole.ORGANIZER)

	def test_ranked_queue_matches_two_players_into_room(self):
		first = User.objects.create_user(username='ranked_first', password='Secret123')
		second = User.objects.create_user(username='ranked_second', password='Secret123')

		self.client.login(username='ranked_first', password='Secret123')
		first_response = self.client.post(reverse('ranked_queue_join'))
		self.assertEqual(first_response.status_code, 200)
		self.assertFalse(first_response.json()['matched'])
		self.client.logout()

		self.client.login(username='ranked_second', password='Secret123')
		second_response = self.client.post(reverse('ranked_queue_join'))
		self.assertEqual(second_response.status_code, 200)
		self.assertTrue(second_response.json()['matched'])

		room_code = second_response.json()['room_code']
		room = Room.objects.get(room_code=room_code)
		self.assertEqual(room.match_type, Room.MatchType.RANKED)
		self.assertEqual(room.max_spectators, 0)
		self.assertEqual(room.start_mode, Room.StartMode.ALL_INVITED)
		self.assertTrue(RoomParticipant.objects.filter(room=room, user=first).exists())
		self.assertTrue(RoomParticipant.objects.filter(room=room, user=second).exists())
		self.assertEqual(RankedMatchQueue.objects.filter(status=RankedMatchQueue.QueueStatus.WAITING).count(), 0)

	def test_ranked_leave_deducts_points_only_in_running_state(self):
		owner = User.objects.create_user(username='ranked_owner', password='Secret123')
		opponent = User.objects.create_user(username='ranked_opponent', password='Secret123')
		owner.profile.rating_points = 25
		owner.profile.save()
		opponent.profile.rating_points = 30
		opponent.profile.save()

		room = Room.objects.create(
			name='Ranked Room',
			created_by=owner,
			match_type=Room.MatchType.RANKED,
			status=Room.Status.RUNNING,
			start_mode=Room.StartMode.ALL_INVITED,
			max_players=2,
			max_spectators=0,
		)
		RoomParticipant.objects.create(room=room, user=owner, role=RoomParticipant.ParticipantRole.PLAYER)
		RoomParticipant.objects.create(room=room, user=opponent, role=RoomParticipant.ParticipantRole.PLAYER)

		self.client.login(username='ranked_owner', password='Secret123')
		response = self.client.post(reverse('room_leave', kwargs={'room_code': room.room_code}))
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('ranked_game'))

		owner.profile.refresh_from_db()
		opponent.profile.refresh_from_db()
		self.assertEqual(owner.profile.rating_points, 15)
		self.assertEqual(opponent.profile.rating_points, 30)
