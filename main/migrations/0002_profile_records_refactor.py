from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_profile_record_fields_to_attempts(apps, schema_editor):
    UserProfile = apps.get_model('main', 'UserProfile')
    PersonalRecordAttempt = apps.get_model('main', 'PersonalRecordAttempt')
    PublicRecordAttempt = apps.get_model('main', 'PublicRecordAttempt')

    for profile in UserProfile.objects.select_related('user').all():
        if profile.personal_best_seconds and profile.personal_best_seconds > Decimal('0.00'):
            PersonalRecordAttempt.objects.create(
                user=profile.user,
                solve_time_seconds=profile.personal_best_seconds,
                achieved_at=profile.updated_at or django.utils.timezone.now(),
            )

        if profile.public_best_seconds and profile.public_best_seconds > Decimal('0.00'):
            PublicRecordAttempt.objects.create(
                user=profile.user,
                solve_time_seconds=profile.public_best_seconds,
                achieved_at=profile.updated_at or django.utils.timezone.now(),
            )


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicRecordAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('solve_time_seconds', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Время сборки')),
                ('achieved_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата попытки')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'verbose_name': 'Публичная попытка',
                'verbose_name_plural': 'Публичные попытки',
                'ordering': ['-achieved_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='PersonalRecordAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('solve_time_seconds', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Время сборки')),
                ('achieved_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата попытки')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'verbose_name': 'Личная попытка',
                'verbose_name_plural': 'Личные попытки',
                'ordering': ['-achieved_at', '-id'],
            },
        ),
        migrations.RunPython(migrate_profile_record_fields_to_attempts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userprofile',
            name='display_name',
            field=models.CharField(blank=True, max_length=80, null=True, unique=True, verbose_name='Отображаемое имя'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='rating_points',
            field=models.PositiveIntegerField(default=0, verbose_name='Рейтинг'),
        ),
        migrations.RemoveField(model_name='userprofile', name='average_of_five_seconds'),
        migrations.RemoveField(model_name='userprofile', name='bio'),
        migrations.RemoveField(model_name='userprofile', name='favorite_event'),
        migrations.RemoveField(model_name='userprofile', name='personal_best_seconds'),
        migrations.RemoveField(model_name='userprofile', name='public_average_seconds'),
        migrations.RemoveField(model_name='userprofile', name='public_best_seconds'),
    ]