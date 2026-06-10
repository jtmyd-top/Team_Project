from django.db import migrations


TEMPLATES = [
    ('违规成立：辱骂骚扰', '', 'uphold', '举报成立。被举报内容存在辱骂、骚扰或攻击性表达，已按社区规则处理。'),
    ('违规成立：垃圾广告', '', 'uphold', '举报成立。被举报内容存在广告、引流或重复刷屏行为，已按社区规则处理。'),
    ('违规成立：隐私风险', '', 'uphold', '举报成立。被举报内容涉及他人隐私或敏感信息，已按社区规则处理。'),
    ('驳回：证据不足', '', 'dismiss', '举报已审核。现有内容和上下文不足以认定违规，本次不进行处罚。'),
    ('驳回：未违反规则', '', 'dismiss', '举报已审核。被举报内容未达到违规处置标准，本次不进行处罚。'),
    ('重新处置：继续违规', '', 'manual', '用户在解除处置后继续出现同类违规行为，基于原工单记录进行重新处置。'),
    ('申诉通过', '', 'appeal', '申诉理由成立，相关处置已解除。'),
    ('申诉驳回', '', 'appeal', '申诉理由不足以推翻原处置，维持原处理结果。'),
]


def seed_templates(apps, schema_editor):
    ModerationTemplate = apps.get_model('knowledge_project', 'ModerationTemplate')
    for title, report_type, decision, content in TEMPLATES:
        ModerationTemplate.objects.get_or_create(
            title=title,
            defaults={
                'report_type': report_type,
                'decision': decision,
                'content': content,
                'is_active': True,
            },
        )


def unseed_templates(apps, schema_editor):
    ModerationTemplate = apps.get_model('knowledge_project', 'ModerationTemplate')
    ModerationTemplate.objects.filter(title__in=[item[0] for item in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0039_attachmentreport_evidence_snapshot_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
