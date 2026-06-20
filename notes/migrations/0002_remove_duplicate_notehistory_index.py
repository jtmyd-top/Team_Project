from django.db import migrations


def _drop_index_if_exists(apps, schema_editor, model_name, index_name):
    model = apps.get_model('notes', model_name)
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


def drop_duplicate_notehistory_index(apps, schema_editor):
    _drop_index_if_exists(apps, schema_editor, 'NoteHistory', 'knowledge_p_user_id_2f835b_idx')


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_duplicate_notehistory_index, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='notehistory',
                    name='knowledge_p_user_id_2f835b_idx',
                ),
            ],
        ),
    ]
