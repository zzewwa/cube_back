from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_userpresence'),
    ]

    operations = [
        migrations.AddField(
            model_name='personalrecordattempt',
            name='initial_cube_state',
            field=models.JSONField(blank=True, default=list, verbose_name='Начальное состояние куба'),
        ),
        migrations.AddField(
            model_name='personalrecordattempt',
            name='move_history',
            field=models.JSONField(blank=True, default=list, verbose_name='История действий'),
        ),
    ]
