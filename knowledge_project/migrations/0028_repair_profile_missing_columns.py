from django.db import migrations


def add_missing_profile_columns(apps, schema_editor):
    Profile = apps.get_model('knowledge_project', 'Profile')
    table_name = Profile._meta.db_table
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }

    for field in Profile._meta.local_fields:
        if field.column in existing_columns:
            continue
        schema_editor.add_field(Profile, field)
        existing_columns.add(field.column)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('knowledge_project', '0027_backfill_merged_forward_searchable_text'),
    ]

    operations = [
        migrations.RunPython(add_missing_profile_columns, migrations.RunPython.noop),
    ]
