from django.db import migrations


def create_missing_profilelike_table(apps, schema_editor):
    ProfileLike = apps.get_model('knowledge_project', 'ProfileLike')
    existing_tables = schema_editor.connection.introspection.table_names()
    if ProfileLike._meta.db_table not in existing_tables:
        schema_editor.create_model(ProfileLike)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('knowledge_project', '0028_repair_profile_missing_columns'),
    ]

    operations = [
        migrations.RunPython(create_missing_profilelike_table, migrations.RunPython.noop),
    ]
