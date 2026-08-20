from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0008_joboffer_urgent_deadline"),
        ("app_profile", "0003_remove_clientprofile_feature_price_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workerprofile",
            name="job_types",
            field=models.ManyToManyField(
                blank=True,
                help_text="Types de jobs additionnels (multi-sélection).",
                related_name="worker_profiles_job_types",
                to="app_job.subcategory",
            ),
        ),
    ]
