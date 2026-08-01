# Generated manually for marked_unread

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_messaging", "0007_clear_false_edited_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationmemberstate",
            name="marked_unread",
            field=models.BooleanField(default=False),
        ),
    ]
