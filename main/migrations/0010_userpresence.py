from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_userprofile_developer_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPresence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_seen', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Последняя активность')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='presence', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Присутствие пользователя',
                'verbose_name_plural': 'Присутствие пользователей',
            },
        ),
    ]
