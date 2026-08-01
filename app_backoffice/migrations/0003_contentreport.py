from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app_backoffice", "0002_rename_notification_backofficenotification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[
                            ("job_offer", "Offre d'emploi"),
                            ("user", "Profil utilisateur"),
                        ],
                        max_length=20,
                    ),
                ),
                ("target_id", models.PositiveIntegerField()),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("spam", "Spam / publicité"),
                            ("scam", "Arnaque / fraude"),
                            ("inappropriate", "Contenu inapproprié"),
                            ("fake", "Fausse information"),
                            ("harassment", "Harcèlement"),
                            ("other", "Autre"),
                        ],
                        max_length=30,
                    ),
                ),
                ("details", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("reviewed", "Examiné"),
                            ("dismissed", "Rejeté"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reporter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Signalement",
                "verbose_name_plural": "Signalements",
                "ordering": ["-created_at"],
            },
        ),
    ]
