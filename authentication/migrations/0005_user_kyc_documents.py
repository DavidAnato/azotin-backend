# Generated for KYC identity document + selfie images

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0004_user_kyc_and_profile_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="kyc_id_document",
            field=models.ImageField(
                blank=True, null=True, upload_to="kyc/id_documents/"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_selfie",
            field=models.ImageField(blank=True, null=True, upload_to="kyc/selfies/"),
        ),
    ]
