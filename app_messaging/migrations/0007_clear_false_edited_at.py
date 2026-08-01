# Clear edited_at leftover from when the field had auto_now=True
# (every create/save set edited_at → false "modifié" on media messages).

from django.db import migrations


def clear_false_edits(apps, schema_editor):
    Message = apps.get_model("app_messaging", "Message")
    # Null edited_at that look like create-time auto_now (within 2 min of timestamp).
    # Real content edits after that window keep their edited_at.
    qs = Message.objects.filter(edited_at__isnull=False)
    for msg in qs.iterator(chunk_size=500):
        if not msg.timestamp or not msg.edited_at:
            continue
        delta = (msg.edited_at - msg.timestamp).total_seconds()
        if delta < 120:
            msg.edited_at = None
            msg.save(update_fields=["edited_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app_messaging", "0006_message_edited_at_reply_to"),
    ]

    operations = [
        migrations.RunPython(clear_false_edits, noop_reverse),
    ]
