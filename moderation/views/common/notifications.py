"""Moderation common notifications helpers."""
from .base import *  # noqa: F401,F403

def _notify_report_closed(report, rtype, decision):
    if decision == 'uphold':
        title = '举报已处理'
        body = '你的举报已被管理员确认成立。'
    else:
        title = '举报已驳回'
        body = '你的举报已由管理员审核，未被认定为违规。'
    notify_user(report.reporter, 'report_resolved', title, body, report_type=rtype, report_id=report.id, decision=decision)

def _notify_sanction_applied(sanction):
    notify_user(
        sanction.user,
        'sanction_applied',
        '账号权限已被限制',
        f'你的账号被执行了「{sanction.get_sanction_type_display()}」处置。',
        sanction_id=sanction.id,
        sanction_type=sanction.sanction_type,
        expires_at=sanction.expires_at.isoformat() if sanction.expires_at else None,
        source_report_type=sanction.source_report_type,
        source_report_id=sanction.source_report_id,
    )

__all__ = [
    '_notify_report_closed',
    '_notify_sanction_applied',
]
