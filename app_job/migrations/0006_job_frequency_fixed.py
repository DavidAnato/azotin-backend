from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0005_joboffer_voice_note_fixed_frequency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
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
