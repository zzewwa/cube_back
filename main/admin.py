from django.contrib import admin

from .models import CubeState, PersonalRecordAttempt, PublicRecordAttempt, Room, RoomInvitation, RoomParticipant, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'display_name', 'rating_points', 'rating_position', 'updated_at')
	search_fields = ('user__username', 'display_name', 'user__email')
	list_filter = ('country',)


@admin.register(PersonalRecordAttempt)
class PersonalRecordAttemptAdmin(admin.ModelAdmin):
	list_display = ('user', 'solve_time_seconds', 'achieved_at', 'created_at')
	search_fields = ('user__username',)
	list_filter = ('achieved_at',)


@admin.register(PublicRecordAttempt)
class PublicRecordAttemptAdmin(admin.ModelAdmin):
	list_display = ('user', 'solve_time_seconds', 'achieved_at', 'created_at')
	search_fields = ('user__username',)
	list_filter = ('achieved_at',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
	list_display = ('name', 'created_by', 'status', 'max_players', 'max_spectators', 'created_at')
	search_fields = ('name', 'created_by__username')
	list_filter = ('status', 'start_mode', 'created_at')


@admin.register(RoomParticipant)
class RoomParticipantAdmin(admin.ModelAdmin):
	list_display = ('room', 'user', 'role', 'joined_at')
	search_fields = ('room__name', 'user__username')
	list_filter = ('role', 'joined_at')


@admin.register(RoomInvitation)
class RoomInvitationAdmin(admin.ModelAdmin):
	list_display = ('room', 'invitee', 'as_role', 'status', 'created_at')
	search_fields = ('room__name', 'invitee__username', 'inviter__username')
	list_filter = ('status', 'as_role', 'created_at')


@admin.register(CubeState)
class CubeStateAdmin(admin.ModelAdmin):
	list_display = ('user', 'updated_at')
	search_fields = ('user__username', 'user__email')
	readonly_fields = ('updated_at',)
