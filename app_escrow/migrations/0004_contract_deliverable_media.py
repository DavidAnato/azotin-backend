from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_escrow", "0003_payment_url_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="deliverable_audio",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="escrow/deliverables/audio/",
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="deliverable_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="escrow/deliverables/images/",
            ),
        ),
    ]
