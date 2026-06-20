from django.db import migrations


MODELS = (
    'message',
    'messageattachment',
    'messagepreference',
    'userblocklist',
    'userfollow',
    'newconversationquotalog',
    'conversationsettings',
    'messagegrouppolicy',
    'messagegroup',
    'messagegroupmember',
    'messagegroupinvitelink',
    'messagegroupinviteuse',
    'messagegroupannouncementhistory',
    'messagegroupannouncementread',
    'groupmessage',
    'groupmessagedeletion',
    'messagegroupban',
    'messagegroupauditlog',
    'groupmessagemention',
    'groupmessagereaction',
    'groupjoinrequest',
    'grouptag',
    'grouptagrelation',
)


def _copy_permission_relations(old_permission, new_permission, Group, User):
    for group_id in old_permission.group_set.values_list('id', flat=True):
        Group.permissions.through.objects.get_or_create(
            group_id=group_id,
            permission_id=new_permission.id,
        )

    for user_id in old_permission.user_set.values_list('id', flat=True):
        User.user_permissions.through.objects.get_or_create(
            user_id=user_id,
            permission_id=new_permission.id,
        )


def forwards(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    LogEntry = apps.get_model('admin', 'LogEntry')

    for model_name in MODELS:
        old_ct = ContentType.objects.filter(
            app_label='knowledge_project',
            model=model_name,
        ).first()
        new_ct, _ = ContentType.objects.get_or_create(
            app_label='messaging',
            model=model_name,
        )

        if old_ct is None:
            continue

        for old_permission in Permission.objects.filter(content_type=old_ct):
            new_permission, _ = Permission.objects.get_or_create(
                content_type=new_ct,
                codename=old_permission.codename,
                defaults={'name': old_permission.name},
            )
            _copy_permission_relations(old_permission, new_permission, Group, User)

        LogEntry.objects.filter(content_type=old_ct).update(content_type=new_ct)
        Permission.objects.filter(content_type=old_ct).delete()

        if not LogEntry.objects.filter(content_type=old_ct).exists():
            old_ct.delete()


def backwards(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    LogEntry = apps.get_model('admin', 'LogEntry')

    for model_name in MODELS:
        old_ct, _ = ContentType.objects.get_or_create(
            app_label='knowledge_project',
            model=model_name,
        )
        new_ct = ContentType.objects.filter(
            app_label='messaging',
            model=model_name,
        ).first()

        if new_ct is None:
            continue

        for new_permission in Permission.objects.filter(content_type=new_ct):
            old_permission, _ = Permission.objects.get_or_create(
                content_type=old_ct,
                codename=new_permission.codename,
                defaults={'name': new_permission.name},
            )
            _copy_permission_relations(new_permission, old_permission, Group, User)

        LogEntry.objects.filter(content_type=new_ct).update(content_type=old_ct)


class Migration(migrations.Migration):

    dependencies = [
        ('admin', '0003_logentry_add_action_flag_choices'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('messaging', '0001_initial'),
        ('knowledge_project', '0057_alter_conversationsettings_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
