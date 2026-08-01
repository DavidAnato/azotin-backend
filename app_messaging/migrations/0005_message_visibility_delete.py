# Generated manually for message visibility / delete-for-everyone

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app_messaging", "0004_conversationmemberstate"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="deleted_for_everyone",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="message",
            name="deleted_for_everyone_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="hidden_for",
            field=models.ManyToManyField(
                blank=True,
                related_name="hidden_messages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
