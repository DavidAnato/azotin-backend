# Generated manually for JobApplication.voice_note

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0006_job_frequency_fixed"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobapplication",
            name="voice_note",
            field=models.FileField(
                blank=True,
                help_text="Note vocale de candidature (alternative au texte).",
                null=True,
                upload_to="job_applications/voice/",
            ),
        ),
    ]
