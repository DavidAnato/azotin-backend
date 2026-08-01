from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0002_usersettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="show_phone_number",
            field=models.BooleanField(
                default=True,
                help_text="Afficher le numéro de téléphone sur le profil",
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="show_online_status",
            field=models.BooleanField(
                default=True, help_text="Afficher le statut en ligne"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="allow_messages",
            field=models.BooleanField(
                default=True, help_text="Autoriser les messages entrants"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="allow_calls",
            field=models.BooleanField(
                default=True, help_text="Autoriser les appels entrants"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="sound_enabled",
            field=models.BooleanField(
                default=True, help_text="Sons de l'application"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="haptics_enabled",
            field=models.BooleanField(
                default=True, help_text="Retours haptiques"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="marketing_notifications",
            field=models.BooleanField(
                default=False, help_text="Offres et nouveautés AZƆTƐN"
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="language",
            field=models.CharField(
                choices=[("fr", "Français"), ("fon", "Fongbé"), ("en", "English")],
                default="fr",
                help_text="Langue de l'application",
                max_length=10,
            ),
        ),
    ]
