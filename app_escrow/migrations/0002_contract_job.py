from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app_job", "0007_jobapplication_voice_note"),
        ("app_escrow", "0001_escrow_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="job",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="escrow_contract",
                to="app_job.job",
            ),
        ),
    ]
