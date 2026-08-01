from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0004_paidservice_remove_jobapplication_feature_price_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="joboffer",
            name="voice_note",
            field=models.FileField(
                blank=True,
                help_text="Note vocale décrivant la mission (alternative au texte).",
                null=True,
                upload_to="job_offers/voice/",
            ),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="responsability",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="frequency",
            field=models.CharField(
                blank=True,
                choices=[
                    ("hour", "Hour"),
                    ("day", "Day"),
                    ("week", "Week"),
                    ("month", "Month"),
                    ("fixed", "Fixed / forfait"),
                ],
                help_text="Frequency of the job.",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="jobapplication",
            name="frequency",
            field=models.CharField(
                blank=True,
                choices=[
                    ("hour", "Hour"),
                    ("day", "Day"),
                    ("week", "Week"),
                    ("month", "Month"),
                    ("fixed", "Fixed / forfait"),
                ],
                help_text="Frequency of the job.",
                max_length=50,
            ),
        ),
    ]
