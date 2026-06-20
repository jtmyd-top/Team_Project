"""Comment reports views."""
from .common import *  # noqa: F401, F403


def _report_payload(request):
    data = json.loads(request.body) if request.body else {}
    return {
        'reason': (data.get('reason') or 'other').strip()[:120],
        'detail': (data.get('detail') or '').strip()[:1000],
    }

@require_http_methods(["POST"])
@login_required
def note_report_api(request, note_id):
    """Create a moderation ticket for a public note/article."""
    try:
        note = get_object_or_404(Note, id=note_id, is_public=True, is_trashed=False)
        if note.author == request.user:
            return JsonResponse({'error': '不能举报自己的文章'}, status=400)

        payload = _report_payload(request)
        if payload['reason'] not in dict(NoteReport.REASON_CHOICES):
            return JsonResponse({'error': '无效的举报原因'}, status=400)
        report, _created = NoteReport.objects.get_or_create(
            note=note,
            reporter=request.user,
            pending_dedup_key='pending',
            defaults={
                'reported_user': note.author,
                'reason': payload['reason'],
                'detail': payload['detail'],
                'evidence_snapshot': note_report_snapshot(note, request),
            },
        )
        notify_user(
            request.user,
            'report_received',
            '举报已收到',
            '你的文章举报已提交，管理员会尽快处理。',
            report_type='note',
            report_id=report.id,
        )
        return JsonResponse({
            'status': 'success',
            'message': '文章举报已提交，我们会尽快处理',
            'report_id': report.id,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error("举报文章失败: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)

@require_http_methods(["POST"])
@login_required
def note_comment_report_api(request, comment_id):
    """Create a moderation ticket for a note comment or reply."""
    try:
        comment = get_object_or_404(
            NoteComment.objects.select_related('note', 'author'),
            id=comment_id,
            note__is_public=True,
        )
        if comment.author == request.user:
            return JsonResponse({'error': '不能举报自己的评论'}, status=400)

        payload = _report_payload(request)
        if payload['reason'] not in dict(CommentReport.REASON_CHOICES):
            return JsonResponse({'error': '无效的举报原因'}, status=400)
        report, _created = CommentReport.objects.get_or_create(
            comment=comment,
            reporter=request.user,
            pending_dedup_key='pending',
            defaults={
                'note': comment.note,
                'reported_user': comment.author,
                'reason': payload['reason'],
                'detail': payload['detail'],
                'evidence_snapshot': comment_report_snapshot(comment, request),
            },
        )
        notify_user(
            request.user,
            'report_received',
            '举报已收到',
            '你的评论举报已提交，管理员会尽快处理。',
            report_type='comment',
            report_id=report.id,
        )
        return JsonResponse({
            'status': 'success',
            'message': '评论举报已提交，我们会尽快处理',
            'report_id': report.id,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error("举报评论失败: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)

