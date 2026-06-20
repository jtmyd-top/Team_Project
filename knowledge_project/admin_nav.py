"""Feature-oriented grouping for the Django admin index.

This is a soft app split: models keep their original app_label and database
tables, while the admin home page presents them by product domain.
"""

FEATURE_ADMIN_GROUPS = (
    {
        'app_label': 'accounts',
        'name': '账户与安全',
        'models': (
            ('auth', 'User'),
            ('accounts', 'Profile'),
            ('accounts', 'LoginDevice'),
            ('accounts', 'LoginNotification'),
            ('accounts', 'TrustedDevice'),
        ),
    },
    {
        'app_label': 'knowledge',
        'name': '知识库',
        'models': (
            ('notes', 'Tag'),
            ('notes', 'Note'),
            ('notes', 'Asset'),
        ),
    },
    {
        'app_label': 'messaging',
        'name': '消息与群聊',
        'models': (
            ('knowledge_project', 'Message'),
            ('knowledge_project', 'MessageAttachment'),
            ('knowledge_project', 'MessagePreference'),
            ('knowledge_project', 'UserBlocklist'),
            ('knowledge_project', 'ConversationSettings'),
            ('knowledge_project', 'MessageGroupPolicy'),
            ('knowledge_project', 'MessageGroup'),
            ('knowledge_project', 'MessageGroupBan'),
            ('knowledge_project', 'MessageGroupAuditLog'),
            ('knowledge_project', 'MessageGroupInviteLink'),
            ('knowledge_project', 'MessageGroupInviteUse'),
            ('knowledge_project', 'MessageGroupAnnouncementHistory'),
            ('knowledge_project', 'GroupMessage'),
        ),
    },
    {
        'app_label': 'moderation',
        'name': '审核中心',
        'models': (
            ('moderation', 'AttachmentReport'),
            ('moderation', 'NoteReport'),
            ('moderation', 'CommentReport'),
            ('moderation', 'MessageReport'),
            ('moderation', 'UserSanction'),
            ('moderation', 'ModerationLog'),
            ('moderation', 'ModerationAppeal'),
            ('moderation', 'ModerationTemplate'),
        ),
    },
    {
        'app_label': 'notifications',
        'name': '通知中心',
        'models': (
            ('notifications', 'UserNotification'),
        ),
    },
    {
        'app_label': 'ops',
        'name': '运维日志',
        'models': (
            ('admin', 'LogEntry'),
            ('accounts', 'AccessLog'),
        ),
    },
)


def _model_key(app, model_info):
    model_class = model_info.get('model')
    if model_class is not None:
        opts = model_class._meta
        return opts.app_label, opts.object_name
    return app.get('app_label'), model_info.get('object_name')


def split_admin_app_list(app_list):
    """Return the admin app list grouped by feature domain."""
    model_lookup = {}
    for app in app_list:
        for model_info in app.get('models', []):
            model_lookup[_model_key(app, model_info)] = model_info

    consumed = set()
    grouped_apps = []
    for group in FEATURE_ADMIN_GROUPS:
        group_models = []
        for key in group['models']:
            model_info = model_lookup.get(key)
            if model_info is None:
                continue
            group_models.append(model_info)
            consumed.add(key)

        if not group_models:
            continue

        grouped_apps.append({
            'name': group['name'],
            'app_label': group['app_label'],
            'app_url': '',
            'has_module_perms': True,
            'models': group_models,
        })

    for app in app_list:
        remaining_models = [
            model_info
            for model_info in app.get('models', [])
            if _model_key(app, model_info) not in consumed
        ]
        if remaining_models:
            copied_app = app.copy()
            copied_app['models'] = remaining_models
            grouped_apps.append(copied_app)

    return grouped_apps
