# Generated migration to fix foreign key constraint

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_auto_20260122_1938'),
    ]

    operations = [
        migrations.RunSQL(
            "PRAGMA foreign_keys=OFF;",
            reverse_sql="PRAGMA foreign_keys=ON;"
        ),
        migrations.AlterField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student_profile',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.RunSQL(
            "PRAGMA foreign_keys=ON;",
            reverse_sql="PRAGMA foreign_keys=OFF;"
        ),
    ]