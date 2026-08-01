# Generated manually for platform commission + FedaPay payout fields

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_escrow", "0004_contract_deliverable_media"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "commission_percent",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("10"),
                        max_digits=5,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Paramètres plateforme",
                "verbose_name_plural": "Paramètres plateforme",
            },
        ),
        migrations.AddField(
            model_name="contract",
            name="platform_fee",
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="freelancer_net",
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="withdrawal",
            name="error_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="withdrawal",
            name="fedapay_payout_id",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="withdrawal",
            name="fedapay_status",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AlterField(
            model_name="wallettransaction",
            name="type",
            field=models.CharField(
                choices=[
                    ("credit", "Crédit"),
                    ("debit", "Débit"),
                    ("escrow_release", "Libération séquestre"),
                    ("withdrawal", "Retrait"),
                    ("refund", "Remboursement"),
                    ("platform_fee", "Commission plateforme"),
                ],
                max_length=32,
            ),
        ),
    ]
