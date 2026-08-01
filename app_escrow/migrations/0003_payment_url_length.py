from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_escrow", "0002_contract_job"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="payment_token",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AlterField(
            model_name="payment",
            name="payment_url",
            field=models.URLField(blank=True, default="", max_length=1024),
        ),
    ]
