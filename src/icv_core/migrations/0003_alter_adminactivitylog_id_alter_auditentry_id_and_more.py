# State-only: 0.4.2 makes BaseModel's pk a VersionedUUIDField that
# deconstructs as a plain UUIDField(default=uuid.uuid4) (see umbrella issue
# #19). This realigns icv-core's own audit models, whose 0002 recorded
# default=_make_uuid, back to uuid.uuid4. Defaults are Python-side, so this
# emits no SQL; it only realigns migration state so makemigrations --check
# stays clean.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("icv_core", "0002_alter_adminactivitylog_id_alter_auditentry_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminactivitylog",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="auditentry",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="systemalert",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
    ]
