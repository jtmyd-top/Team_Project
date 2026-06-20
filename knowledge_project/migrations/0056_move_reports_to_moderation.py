from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0055_move_profiles_to_accounts'),
        ('moderation', '0004_move_report_models_to_moderation_state'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='commentreport',
                    name='comment',
                ),
                migrations.RemoveField(
                    model_name='commentreport',
                    name='handled_by',
                ),
                migrations.RemoveField(
                    model_name='commentreport',
                    name='note',
                ),
                migrations.RemoveField(
                    model_name='commentreport',
                    name='reported_user',
                ),
                migrations.RemoveField(
                    model_name='commentreport',
                    name='reporter',
                ),
                migrations.RemoveField(
                    model_name='messagereport',
                    name='group_message',
                ),
                migrations.RemoveField(
                    model_name='messagereport',
                    name='handled_by',
                ),
                migrations.RemoveField(
                    model_name='messagereport',
                    name='message',
                ),
                migrations.RemoveField(
                    model_name='messagereport',
                    name='reported_user',
                ),
                migrations.RemoveField(
                    model_name='messagereport',
                    name='reporter',
                ),
                migrations.RemoveField(
                    model_name='notereport',
                    name='handled_by',
                ),
                migrations.RemoveField(
                    model_name='notereport',
                    name='note',
                ),
                migrations.RemoveField(
                    model_name='notereport',
                    name='reported_user',
                ),
                migrations.RemoveField(
                    model_name='notereport',
                    name='reporter',
                ),
                migrations.DeleteModel(name='AttachmentReport'),
                migrations.DeleteModel(name='CommentReport'),
                migrations.DeleteModel(name='MessageReport'),
                migrations.DeleteModel(name='NoteReport'),
            ],
        ),
    ]
