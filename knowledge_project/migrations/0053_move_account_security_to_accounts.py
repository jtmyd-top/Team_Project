from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('knowledge_project', '0052_move_moderation_core_to_moderation'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name='AccessLog'),
                migrations.DeleteModel(name='PasswordResetAttempt'),
                migrations.DeleteModel(name='PasswordResetToken'),
                migrations.DeleteModel(name='SecurityAuditLog'),
            ],
        ),
    ]
