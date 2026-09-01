from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0006_kycsubmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="kycsubmission",
            name="id_document_back",
            field=models.ImageField(
                blank=True, null=True, upload_to="kyc/id_documents/"
            ),
        ),
    ]
