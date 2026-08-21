# Generated manually: KycSubmission + migrate User.kyc_* data

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_migrate_kyc(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    KycSubmission = apps.get_model("authentication", "KycSubmission")
    for user in User.objects.all().iterator():
        status = (getattr(user, "kyc_status", None) or "none").strip() or "none"
        if user.is_certified and status in ("", "none"):
            status = "approved"
        has_data = (
            status not in ("", "none")
            or bool(getattr(user, "kyc_id_type", "") or "")
            or bool(getattr(user, "kyc_id_number", "") or "")
            or bool(getattr(user, "kyc_id_document", None))
            or bool(getattr(user, "kyc_selfie", None))
            or bool(getattr(user, "kyc_submitted_at", None))
            or user.is_certified
        )
        if not has_data:
            continue
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        KycSubmission.objects.update_or_create(
            user_id=user.id,
            defaults={
                "status": status if status in ("none", "pending", "approved", "rejected") else "none",
                "full_name": full_name,
                "id_type": getattr(user, "kyc_id_type", "") or "",
                "id_number": getattr(user, "kyc_id_number", "") or "",
                "id_document": getattr(user, "kyc_id_document", None) or None,
                "selfie": getattr(user, "kyc_selfie", None) or None,
                "submitted_at": getattr(user, "kyc_submitted_at", None),
                "reviewed_at": getattr(user, "kyc_submitted_at", None)
                if status in ("approved", "rejected")
                else None,
                "review_notes": "",
            },
        )
        if status == "approved" and not user.is_certified:
            User.objects.filter(pk=user.pk).update(is_certified=True)


def backwards_migrate_kyc(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    KycSubmission = apps.get_model("authentication", "KycSubmission")
    for submission in KycSubmission.objects.all().iterator():
        User.objects.filter(pk=submission.user_id).update(
            kyc_status=submission.status or "none",
            kyc_submitted_at=submission.submitted_at,
            kyc_id_type=submission.id_type or "",
            kyc_id_number=submission.id_number or "",
            kyc_id_document=submission.id_document or None,
            kyc_selfie=submission.selfie or None,
            is_certified=submission.status == "approved",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0005_user_kyc_documents"),
    ]

    operations = [
        migrations.CreateModel(
            name="KycSubmission",
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
                    "status",
                    models.CharField(
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
                ("full_name", models.CharField(blank=True, default="", max_length=200)),
                ("id_type", models.CharField(blank=True, default="", max_length=50)),
                ("id_number", models.CharField(blank=True, default="", max_length=100)),
                (
                    "id_document",
                    models.ImageField(
                        blank=True, null=True, upload_to="kyc/id_documents/"
                    ),
                ),
                (
                    "selfie",
                    models.ImageField(
                        blank=True, null=True, upload_to="kyc/selfies/"
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kyc_submission",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Dossier KYC",
                "verbose_name_plural": "Dossiers KYC",
            },
        ),
        migrations.RunPython(forwards_migrate_kyc, backwards_migrate_kyc),
        migrations.RemoveField(model_name="user", name="kyc_id_document"),
        migrations.RemoveField(model_name="user", name="kyc_id_number"),
        migrations.RemoveField(model_name="user", name="kyc_id_type"),
        migrations.RemoveField(model_name="user", name="kyc_selfie"),
        migrations.RemoveField(model_name="user", name="kyc_status"),
        migrations.RemoveField(model_name="user", name="kyc_submitted_at"),
    ]
