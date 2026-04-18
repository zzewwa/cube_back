from django.db import migrations, models
import secrets
import string


ALPHABET = string.ascii_letters + string.digits


def _generate_code(length=12):
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))


def populate_room_codes(apps, schema_editor):
    Room = apps.get_model('main', 'Room')
    existing = set(Room.objects.exclude(room_code__isnull=True).values_list('room_code', flat=True))

    for room in Room.objects.filter(room_code__isnull=True):
        code = _generate_code()
        while code in existing:
            code = _generate_code()
        room.room_code = code
        room.save(update_fields=['room_code'])
        existing.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_cubestate'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='room_code',
            field=models.CharField(blank=True, editable=False, max_length=24, null=True, unique=True, verbose_name='Код комнаты'),
        ),
        migrations.RunPython(populate_room_codes, migrations.RunPython.noop),
    ]
