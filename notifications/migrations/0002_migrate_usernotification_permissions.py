from django.db import migrations


def forwards(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    LogEntry = apps.get_model('admin', 'LogEntry')

    old_ct = ContentType.objects.filter(
        app_label='knowledge_project',
        model='usernotification',
    ).first()
    new_ct, _ = ContentType.objects.get_or_create(
        app_label='notifications',
        model='usernotification',
    )

    if old_ct is None:
        return

    old_permissions = list(Permission.objects.filter(content_type=old_ct))
    for old_permission in old_permissions:
        new_permission, _ = Permission.objects.get_or_create(
            content_type=new_ct,
            codename=old_permission.codename,
            defaults={'name': old_permission.name},
        )

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

    old_ct, _ = ContentType.objects.get_or_create(
        app_label='knowledge_project',
        model='usernotification',
    )
    new_ct = ContentType.objects.filter(
        app_label='notifications',
        model='usernotification',
    ).first()

    if new_ct is None:
        return

    for new_permission in Permission.objects.filter(content_type=new_ct):
        old_permission, _ = Permission.objects.get_or_create(
            content_type=old_ct,
            codename=new_permission.codename,
            defaults={'name': new_permission.name},
        )

        for group_id in new_permission.group_set.values_list('id', flat=True):
            Group.permissions.through.objects.get_or_create(
                group_id=group_id,
                permission_id=old_permission.id,
            )

        for user_id in new_permission.user_set.values_list('id', flat=True):
            User.user_permissions.through.objects.get_or_create(
                user_id=user_id,
                permission_id=old_permission.id,
            )

    LogEntry.objects.filter(content_type=new_ct).update(content_type=old_ct)


class Migration(migrations.Migration):

    dependencies = [
        ('admin', '0003_logentry_add_action_flag_choices'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('knowledge_project', '0051_move_usernotification_to_notifications'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
