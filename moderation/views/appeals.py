from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def moderation_sanction_appeal_api(request, sid):
    try:
        from moderation.models import ModerationAppeal, UserSanction

        sanction = get_object_or_404(UserSanction, id=sid, user=request.user)
        if not sanction.is_effective:
            return JsonResponse({'error': '该处置已失效，不能申诉'}, status=400)
        data = json.loads(request.body) if request.body else {}
        reason = (data.get('reason') or '').strip()[:2000]
        if len(reason) < 5:
            return JsonResponse({'error': '请填写申诉理由'}, status=400)
        appeal, created = ModerationAppeal.objects.get_or_create(
            sanction=sanction,
            user=request.user,
            status='pending',
            defaults={'reason': reason},
        )
        if not created and reason != appeal.reason:
            appeal.reason = reason
            appeal.save(update_fields=['reason'])
        notify_user(
            request.user,
            'appeal_submitted',
            '申诉已提交',
            '你的处置申诉已提交，管理员会尽快处理。',
            sanction_id=sanction.id,
            appeal_id=appeal.id,
        )
        return JsonResponse({'status': 'success', 'appeal_id': appeal.id, 'created': created})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('提交申诉错误', e)


@require_http_methods(["POST"])
@login_required
def moderation_appeal_resolve_api(request, appeal_id):
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from moderation.models import ModerationAppeal, ModerationLog

        appeal = get_object_or_404(ModerationAppeal.objects.select_related('sanction', 'user'), id=appeal_id)
        if appeal.status != 'pending':
            return JsonResponse({'error': '该申诉已处理'}, status=400)
        data = json.loads(request.body) if request.body else {}
        decision = data.get('decision')
        note = (data.get('note') or '').strip()[:2000]
        if decision not in ('accepted', 'rejected'):
            return JsonResponse({'error': '无效的申诉处理结果'}, status=400)

        with transaction.atomic():
            appeal.status = decision
            appeal.handled_by = request.user
            appeal.resolution_note = note
            appeal.handled_at = timezone.now()
            appeal.save(update_fields=['status', 'handled_by', 'resolution_note', 'handled_at'])
            if decision == 'accepted' and appeal.sanction.is_active:
                appeal.sanction.is_active = False
                appeal.sanction.revoked_at = timezone.now()
                appeal.sanction.save(update_fields=['is_active', 'revoked_at'])
                if appeal.sanction.sanction_type == 'ban_login' and not appeal.user.is_active:
                    appeal.user.is_active = True
                    appeal.user.save(update_fields=['is_active'])
            ModerationLog.objects.create(
                report_type=appeal.sanction.source_report_type or 'message',
                report_id=appeal.sanction.source_report_id or 0,
                moderator=request.user,
                target_user=appeal.user,
                action=f'appeal:{decision}',
                note=note,
            )
        notify_user(
            appeal.user,
            'appeal_resolved',
            '申诉已处理',
            '你的申诉已通过，相关处置已解除。' if decision == 'accepted' else '你的申诉已被管理员驳回。',
            appeal_id=appeal.id,
            sanction_id=appeal.sanction_id,
            decision=decision,
        )
        return JsonResponse({'status': 'success', 'decision': decision})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理申诉错误', e)
