from django.db import migrations


def _drop_index_if_exists(apps, schema_editor, model_name, index_name):
    model = apps.get_model('accounts', model_name)
    table_name = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)
    if index_name not in constraints:
        return

    quoted_index = schema_editor.quote_name(index_name)
    quoted_table = schema_editor.quote_name(table_name)
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(f'DROP INDEX {quoted_index} ON {quoted_table}')
    else:
        schema_editor.execute(f'DROP INDEX {quoted_index}')


def drop_duplicate_profilelike_index(apps, schema_editor):
    _drop_index_if_exists(apps, schema_editor, 'ProfileLike', 'knowledge_p_liker_i_ea4deb_idx')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_rename_profile_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_duplicate_profilelike_index, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='profilelike',
                    name='knowledge_p_liker_i_ea4deb_idx',
                ),
            ],
        ),
    ]
