# Generated manually for edited_at (no auto_now) + reply_to

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app_messaging", "0005_message_visibility_delete"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="edited_at",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="reply_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replies",
                to="app_messaging.message",
            ),
        ),
    ]
