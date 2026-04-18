from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_room_room_code'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='match_type',
            field=models.CharField(choices=[('casual', 'Обычная'), ('ranked', 'Рейтинговая')], default='casual', max_length=16, verbose_name='Тип матча'),
        ),
        migrations.AddField(
            model_name='room',
            name='ranked_auto_start_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Автостарт рейтинговой игры'),
        ),
        migrations.AddField(
            model_name='room',
            name='ranked_finished_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Завершено в рейтинговом режиме'),
        ),
        migrations.AddField(
            model_name='room',
            name='ranked_winner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='won_ranked_rooms', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='RankedMatchQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('waiting', 'Ожидание'), ('matched', 'Матч найден')], default='waiting', max_length=16, verbose_name='Статус очереди')),
                ('joined_at', models.DateTimeField(auto_now_add=True, verbose_name='Встал в очередь')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('matched_room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_queue_entries', to='main.room')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ranked_queue_entry', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Очередь рейтинговой игры',
                'verbose_name_plural': 'Очередь рейтинговой игры',
                'ordering': ['joined_at', 'id'],
            },
        ),
    ]
