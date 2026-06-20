from django.db import migrations, models


def _drop_index_if_exists(apps, schema_editor, model_name, index_name):
    model = apps.get_model('messaging', model_name)
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


def drop_legacy_message_unread_index(apps, schema_editor):
    _drop_index_if_exists(apps, schema_editor, 'Message', 'messaging_m_recipie_f6f3c4_idx')


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0003_rename_knowledge_p_user_id_2aafeb_idx_messaging_c_user_id_c428d6_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_legacy_message_unread_index, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='message',
                    name='messaging_m_recipie_f6f3c4_idx',
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['recipient', 'is_read', 'deleted_for_recipient', 'is_recalled', '-created_at'],
                name='message_recipient_unread_idx',
            ),
        ),
    ]
