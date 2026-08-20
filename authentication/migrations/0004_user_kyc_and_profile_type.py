# Generated for KYC + profile_type on User

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0003_usersettings_extra_prefs"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_type",
            field=models.CharField(
                blank=True,
                choices=[("worker", "Travailleur"), ("employer", "Client")],
                default="",
                help_text="worker ou employer (client).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_status",
            field=models.CharField(
                choices=[
                    ("none", "Aucun"),
                    ("pending", "En attente"),
                    ("approved", "Approuvé"),
                    ("rejected", "Rejeté"),
                ],
                db_index=True,
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_id_type",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_id_number",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
