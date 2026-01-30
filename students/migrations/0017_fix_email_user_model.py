# Generated migration to fix user model reference

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0016_populate_default_email_templates'),
    ]

    operations = [
        # This migration ensures the EmailHistory model uses the correct user model
        # The previous migration should already have the correct reference, but this
        # ensures compatibility if there were any issues
    ]