from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_profile", "0004_workerprofile_job_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workerprofile",
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
                default="hour",
                help_text="Frequency of the job.",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="workerprofile",
            name="price",
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=9, null=True
            ),
        ),
    ]
