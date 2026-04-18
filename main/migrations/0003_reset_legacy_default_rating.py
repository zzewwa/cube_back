from django.db import migrations


def reset_legacy_default_rating(apps, schema_editor):
    UserProfile = apps.get_model('main', 'UserProfile')
    PersonalRecordAttempt = apps.get_model('main', 'PersonalRecordAttempt')
    PublicRecordAttempt = apps.get_model('main', 'PublicRecordAttempt')

    personal_users = set(PersonalRecordAttempt.objects.values_list('user_id', flat=True))
    public_users = set(PublicRecordAttempt.objects.values_list('user_id', flat=True))

    for profile in UserProfile.objects.filter(rating_points=1000, rating_position=0):
        if profile.user_id in personal_users or profile.user_id in public_users:
            continue
        profile.rating_points = 0
        profile.save(update_fields=['rating_points'])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_profile_records_refactor'),
    ]

    operations = [
        migrations.RunPython(reset_legacy_default_rating, migrations.RunPython.noop),
    ]