from decimal import Decimal
import secrets
import string

from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


ROOM_CODE_ALPHABET = string.ascii_letters + string.digits


def _generate_room_code(length=12):
	return ''.join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))


class UserProfile(models.Model):
	class UserRole(models.TextChoices):
		PLAYER = 'player', 'Игрок'
		SPECTATOR = 'spectator', 'Зритель'
		ORGANIZER = 'organizer', 'Организатор'
		DEVELOPER = 'developer', 'Разработчик'

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
	display_name = models.CharField('Отображаемое имя', max_length=80, blank=True, null=True, unique=True)
	avatar = models.ImageField(
		'Аватар',
		upload_to='avatars/',
		blank=True,
		null=True,
		validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])],
	)
	city = models.CharField('Город', max_length=80, blank=True)
	country = models.CharField('Страна', max_length=80, blank=True)
	telegram = models.CharField('Telegram', max_length=64, blank=True)
	birth_date = models.DateField('Дата рождения', blank=True, null=True)
	role = models.CharField('Роль', max_length=16, choices=UserRole.choices, default=UserRole.PLAYER)
	rating_points = models.PositiveIntegerField('Рейтинг', default=0)
	rating_position = models.PositiveIntegerField('Позиция в рейтинге', default=0)
	achievements_total = models.PositiveIntegerField('Количество достижений', default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Профиль пользователя'
		verbose_name_plural = 'Профили пользователей'

	def __str__(self):
		return f'Профиль {self.user.username}'

	@property
	def visible_name(self):
		if self.display_name:
			return self.display_name
		full_name = self.user.get_full_name().strip()
		return full_name or self.user.username

	@property
	def initials(self):
		source = self.visible_name.strip() or self.user.username
		parts = [part for part in source.split() if part]
		if len(parts) >= 2:
			return f'{parts[0][0]}{parts[1][0]}'.upper()
		return source[:2].upper()


class BaseSolveAttempt(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	solve_time_seconds = models.DecimalField(
		'Время сборки',
		max_digits=6,
		decimal_places=2,
		validators=[MinValueValidator(0), MaxValueValidator(999.99)],
	)
	achieved_at = models.DateTimeField('Дата попытки', default=timezone.now)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		abstract = True
		ordering = ['-achieved_at', '-id']

	def __str__(self):
		return f'{self.user.username}: {self.solve_time_seconds:.2f} c'


class PersonalRecordAttempt(BaseSolveAttempt):
	class AttemptSource(models.TextChoices):
		SINGLE = 'single', 'single'
		ROOM = 'room', 'room'

	source = models.CharField(
		'Источник попытки',
		max_length=16,
		choices=AttemptSource.choices,
		default=AttemptSource.SINGLE,
	)

	class Meta(BaseSolveAttempt.Meta):
		verbose_name = 'Личная попытка'
		verbose_name_plural = 'Личные попытки'


class PublicRecordAttempt(BaseSolveAttempt):
	class Meta(BaseSolveAttempt.Meta):
		verbose_name = 'Публичная попытка'
		verbose_name_plural = 'Публичные попытки'


class Room(models.Model):
	class MatchType(models.TextChoices):
		CASUAL = 'casual', 'Обычная'
		RANKED = 'ranked', 'Рейтинговая'

	class StartMode(models.TextChoices):
		OWNER = 'owner', 'По решению создателя'
		ALL_INVITED = 'all_invited', 'Когда соберутся все приглашенные'

	class Status(models.TextChoices):
		WAITING = 'waiting', 'Ожидание'
		RUNNING = 'running', 'Игра идет'
		FINISHED = 'finished', 'Завершена'

	name = models.CharField('Название комнаты', max_length=120)
	room_code = models.CharField('Код комнаты', max_length=24, unique=True, null=True, blank=True, editable=False)
	created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
	match_type = models.CharField('Тип матча', max_length=16, choices=MatchType.choices, default=MatchType.CASUAL)
	max_players = models.PositiveSmallIntegerField('Лимит игроков', default=2)
	max_spectators = models.PositiveSmallIntegerField('Лимит зрителей', default=8)
	start_mode = models.CharField('Старт игры', max_length=16, choices=StartMode.choices, default=StartMode.OWNER)
	countdown_seconds = models.PositiveSmallIntegerField('Отсчет перед стартом (сек)', default=5)
	fade_in_seconds = models.DecimalField('Fade In (сек)', max_digits=4, decimal_places=2, default=Decimal('0.50'))
	fade_out_seconds = models.DecimalField('Fade Out (сек)', max_digits=4, decimal_places=2, default=Decimal('0.50'))
	study_seconds = models.PositiveSmallIntegerField('Период изучения (сек)', default=10)
	status = models.CharField('Статус комнаты', max_length=16, choices=Status.choices, default=Status.WAITING)
	ranked_auto_start_at = models.DateTimeField('Автостарт рейтинговой игры', null=True, blank=True)
	ranked_winner = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		related_name='won_ranked_rooms',
		null=True,
		blank=True,
	)
	ranked_finished_at = models.DateTimeField('Завершено в рейтинговом режиме', null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Комната'
		verbose_name_plural = 'Комнаты'
		ordering = ['-created_at', '-id']

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		if not self.room_code:
			for _ in range(20):
				candidate = _generate_room_code()
				if not self.__class__.objects.filter(room_code=candidate).exists():
					self.room_code = candidate
					break
		super().save(*args, **kwargs)


class RoomParticipant(models.Model):
	class ParticipantRole(models.TextChoices):
		ORGANIZER = 'organizer', 'Организатор'
		PLAYER = 'player', 'Игрок'
		SPECTATOR = 'spectator', 'Зритель'

	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_participations')
	role = models.CharField('Роль в комнате', max_length=16, choices=ParticipantRole.choices)
	joined_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = 'Участник комнаты'
		verbose_name_plural = 'Участники комнат'
		unique_together = ('room', 'user')

	def __str__(self):
		return f'{self.room_id}: {self.user.username} ({self.role})'


class RoomInvitation(models.Model):
	class InvitationStatus(models.TextChoices):
		PENDING = 'pending', 'Ожидает'
		ACCEPTED = 'accepted', 'Принято'
		DECLINED = 'declined', 'Отклонено'

	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invitations')
	inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_room_invitations')
	invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_room_invitations')
	as_role = models.CharField('Приглашение как', max_length=16, choices=RoomParticipant.ParticipantRole.choices)
	status = models.CharField('Статус', max_length=16, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	responded_at = models.DateTimeField(blank=True, null=True)

	class Meta:
		verbose_name = 'Приглашение в комнату'
		verbose_name_plural = 'Приглашения в комнаты'
		unique_together = ('room', 'invitee')

	def __str__(self):
		return f'{self.invitee.username} -> {self.room.name} ({self.status})'


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
	if created:
		UserProfile.objects.create(user=instance)
		return
	UserProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=UserProfile)
def delete_previous_avatar_on_change(sender, instance, **kwargs):
	if not instance.pk:
		return

	try:
		previous = UserProfile.objects.get(pk=instance.pk)
	except UserProfile.DoesNotExist:
		return

	previous_avatar = previous.avatar
	new_avatar = instance.avatar
	if previous_avatar and previous_avatar.name and previous_avatar.name != getattr(new_avatar, 'name', None):
		previous_avatar.delete(save=False)


class CubeState(models.Model):
	"""Сохранённое состояние куба пользователя"""
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cube_state')
	cube_materials = models.TextField('Состояние материалов куба', default='', blank=True)
	skin_state = models.JSONField('Состояние скина', default=dict, blank=True)
	additional_info = models.JSONField('Дополнительная информация', default=dict, blank=True)
	updated_at = models.DateTimeField('Обновлено', auto_now=True)

	class Meta:
		verbose_name = 'Состояние куба'
		verbose_name_plural = 'Состояния кубов'

	def __str__(self):
		return f'Состояние куба {self.user.username}'


class RankedMatchQueue(models.Model):
	class QueueStatus(models.TextChoices):
		WAITING = 'waiting', 'Ожидание'
		MATCHED = 'matched', 'Матч найден'

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ranked_queue_entry')
	status = models.CharField('Статус очереди', max_length=16, choices=QueueStatus.choices, default=QueueStatus.WAITING)
	matched_room = models.ForeignKey(Room, on_delete=models.SET_NULL, related_name='matched_queue_entries', null=True, blank=True)
	joined_at = models.DateTimeField('Встал в очередь', auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Очередь рейтинговой игры'
		verbose_name_plural = 'Очередь рейтинговой игры'
		ordering = ['joined_at', 'id']

	def __str__(self):
		return f'{self.user.username}: {self.status}'


class UserPresence(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='presence')
	last_seen = models.DateTimeField('Последняя активность', default=timezone.now, db_index=True)

	class Meta:
		verbose_name = 'Присутствие пользователя'
		verbose_name_plural = 'Присутствие пользователей'

	def __str__(self):
		return f'{self.user.username}: {self.last_seen.isoformat()}'


@receiver(post_save, sender=User)
def create_cube_state(sender, instance, created, **kwargs):
	if created:
		CubeState.objects.get_or_create(user=instance)


@receiver(post_delete, sender=UserProfile)
def delete_avatar_on_profile_delete(sender, instance, **kwargs):
	if instance.avatar:
		instance.avatar.delete(save=False)
