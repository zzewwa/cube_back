from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(blank=True, max_length=80, verbose_name='Отображаемое имя')),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/', validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])], verbose_name='Аватар')),
                ('bio', models.TextField(blank=True, max_length=500, verbose_name='О себе')),
                ('city', models.CharField(blank=True, max_length=80, verbose_name='Город')),
                ('country', models.CharField(blank=True, max_length=80, verbose_name='Страна')),
                ('telegram', models.CharField(blank=True, max_length=64, verbose_name='Telegram')),
                ('favorite_event', models.CharField(blank=True, max_length=80, verbose_name='Любимая дисциплина')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('personal_best_seconds', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('999.99'))], verbose_name='Лучший результат')),
                ('average_of_five_seconds', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('999.99'))], verbose_name='Среднее из 5')),
                ('public_best_seconds', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('999.99'))], verbose_name='Публичный лучший результат')),
                ('public_average_seconds', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('999.99'))], verbose_name='Публичное среднее')),
                ('rating_points', models.PositiveIntegerField(default=1000, verbose_name='Рейтинг')),
                ('rating_position', models.PositiveIntegerField(default=0, verbose_name='Позиция в рейтинге')),
                ('achievements_total', models.PositiveIntegerField(default=0, verbose_name='Количество достижений')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Профиль пользователя',
                'verbose_name_plural': 'Профили пользователей',
            },
        ),
    ]