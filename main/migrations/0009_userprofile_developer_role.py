from django.db import migrations, models


def set_developer_role_for_7box7(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("main", "UserProfile")

    user = User.objects.filter(username="7box7").first()
    if not user:
        return

    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return

    profile.role = "developer"
    profile.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0008_ranked_matchmaking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("player", "Игрок"),
                    ("spectator", "Зритель"),
                    ("organizer", "Организатор"),
                    ("developer", "Разработчик"),
                ],
                default="player",
                max_length=16,
                verbose_name="Роль",
            ),
        ),
        migrations.RunPython(set_developer_role_for_7box7, migrations.RunPython.noop),
    ]
