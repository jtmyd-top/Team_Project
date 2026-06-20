from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def moderation_templates_api(request):
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from moderation.models import ModerationTemplate

        rtype = request.GET.get('type') or ''
        decision = request.GET.get('decision') or ''
        qs = ModerationTemplate.objects.filter(is_active=True)
        if rtype:
            qs = qs.filter(Q(report_type='') | Q(report_type=rtype))
        if decision:
            qs = qs.filter(Q(decision='') | Q(decision=decision))
        return JsonResponse({
            'status': 'success',
            'templates': [
                {
                    'id': t.id,
                    'title': t.title,
                    'report_type': t.report_type,
                    'decision': t.decision,
                    'content': t.content,
                }
                for t in qs[:100]
            ],
        })
    except Exception as e:
        return _server_error_response('获取处置模板错误', e)
