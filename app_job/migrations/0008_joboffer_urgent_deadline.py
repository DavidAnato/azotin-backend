from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0007_jobapplication_voice_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="joboffer",
            name="deadline",
            field=models.DateField(
                blank=True,
                help_text="Date limite pour postuler / réaliser la mission.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="joboffer",
            name="is_urgent",
            field=models.BooleanField(default=False, help_text="Offre urgente."),
        ),
    ]
