"""Group polls and lightweight task tracking."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from messaging.models import GroupPoll, GroupPollOption, GroupPollVote, GroupTask, MessageGroup

from .common import _create_group_audit_log, _require_group_manager, _require_group_member


def _request_data(request):
    try:
        return json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return None


def _poll_payload(poll, viewer):
    votes_by_option = {}
    viewer_option_ids = set()
    for vote in poll.votes.all():
        votes_by_option[vote.option_id] = votes_by_option.get(vote.option_id, 0) + 1
        if vote.user_id == viewer.id:
            viewer_option_ids.add(vote.option_id)
    return {
        'id': poll.id,
        'question': poll.question,
        'allow_multiple': poll.allow_multiple,
        'is_open': poll.is_open(),
        'closes_at': poll.closes_at.isoformat() if poll.closes_at else None,
        'closed_at': poll.closed_at.isoformat() if poll.closed_at else None,
        'created_at': poll.created_at.isoformat(),
        'created_by': {'id': poll.created_by_id, 'username': poll.created_by.username},
        'total_votes': sum(votes_by_option.values()),
        'options': [
            {
                'id': option.id,
                'text': option.text,
                'votes': votes_by_option.get(option.id, 0),
                'selected': option.id in viewer_option_ids,
            }
            for option in poll.options.all()
        ],
    }


def _task_payload(task):
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'due_at': task.due_at.isoformat() if task.due_at else None,
        'created_at': task.created_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'created_by': {'id': task.created_by_id, 'username': task.created_by.username},
        'assignee': (
            {'id': task.assignee_id, 'username': task.assignee.username}
            if task.assignee_id
            else None
        ),
        'completed_by': (
            {'id': task.completed_by_id, 'username': task.completed_by.username}
            if task.completed_by_id
            else None
        ),
    }


def _parse_due_at(value):
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError('Invalid due date')
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError('Invalid due date')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@login_required
@require_http_methods(['GET', 'POST'])
def group_polls_api(request, group_id):
    group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
    membership, error = _require_group_member(group, request.user)
    if error is not None:
        return error

    if request.method == 'GET':
        polls = (
            GroupPoll.objects.filter(group=group)
            .select_related('created_by')
            .prefetch_related('options', 'votes')
            .order_by('-created_at')[:30]
        )
        return JsonResponse({'status': 'success', 'polls': [_poll_payload(poll, request.user) for poll in polls]})

    error = _require_group_manager(membership)
    if error is not None:
        return error
    data = _request_data(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    question = str(data.get('question') or '').strip()
    raw_options = data.get('options')
    if not question or len(question) > 240:
        return JsonResponse({'status': 'error', 'message': 'Question must be between 1 and 240 characters'}, status=400)
    if not isinstance(raw_options, list):
        return JsonResponse({'status': 'error', 'message': 'At least two options are required'}, status=400)
    options = []
    for value in raw_options:
        text = str(value or '').strip()
        if text and text not in options:
            options.append(text)
    if len(options) < 2 or len(options) > 10 or any(len(text) > 160 for text in options):
        return JsonResponse({'status': 'error', 'message': 'Provide 2 to 10 distinct options'}, status=400)
    try:
        closes_at = _parse_due_at(data.get('closes_at'))
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    if closes_at and closes_at <= timezone.now():
        return JsonResponse({'status': 'error', 'message': 'Closing time must be in the future'}, status=400)

    with transaction.atomic():
        poll = GroupPoll.objects.create(
            group=group,
            created_by=request.user,
            question=question,
            allow_multiple=bool(data.get('allow_multiple')),
            closes_at=closes_at,
        )
        GroupPollOption.objects.bulk_create(
            [GroupPollOption(poll=poll, text=text, position=index) for index, text in enumerate(options)]
        )
    _create_group_audit_log(group, request.user, 'poll_create', metadata={'poll_id': poll.id})
    poll = GroupPoll.objects.select_related('created_by').prefetch_related('options', 'votes').get(id=poll.id)
    return JsonResponse({'status': 'success', 'poll': _poll_payload(poll, request.user)}, status=201)


@login_required
@require_http_methods(['POST'])
def vote_group_poll_api(request, group_id, poll_id):
    group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
    membership, error = _require_group_member(group, request.user)
    if error is not None:
        return error
    data = _request_data(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    raw_option_ids = data.get('option_ids')
    if not isinstance(raw_option_ids, list):
        raw_option_ids = [data.get('option_id')]
    try:
        option_ids = {int(item) for item in raw_option_ids if item is not None}
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid option'}, status=400)

    with transaction.atomic():
        poll = (
            GroupPoll.objects.select_for_update()
            .filter(id=poll_id, group=group)
            .select_related('created_by')
            .prefetch_related('options', 'votes')
            .first()
        )
        if poll is None:
            return JsonResponse({'status': 'error', 'message': 'Poll not found'}, status=404)
        if not poll.is_open():
            return JsonResponse({'status': 'error', 'message': 'This poll is closed'}, status=400)
        valid_ids = set(poll.options.values_list('id', flat=True))
        if not option_ids or not option_ids.issubset(valid_ids):
            return JsonResponse({'status': 'error', 'message': 'Choose a valid option'}, status=400)
        if not poll.allow_multiple and len(option_ids) != 1:
            return JsonResponse({'status': 'error', 'message': 'This poll accepts one choice'}, status=400)
        GroupPollVote.objects.filter(poll=poll, user=request.user).delete()
        GroupPollVote.objects.bulk_create(
            [GroupPollVote(poll=poll, option_id=option_id, user=request.user) for option_id in option_ids]
        )

    poll = GroupPoll.objects.select_related('created_by').prefetch_related('options', 'votes').get(id=poll_id)
    return JsonResponse({'status': 'success', 'poll': _poll_payload(poll, request.user)})


@login_required
@require_http_methods(['POST'])
def close_group_poll_api(request, group_id, poll_id):
    group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
    membership, member_error = _require_group_member(group, request.user)
    if member_error is not None:
        return member_error
    error = _require_group_manager(membership)
    if error is not None:
        return error
    poll = get_object_or_404(GroupPoll, id=poll_id, group=group)
    if poll.closed_at is None:
        poll.closed_at = timezone.now()
        poll.save(update_fields=['closed_at', 'updated_at'])
        _create_group_audit_log(group, request.user, 'poll_close', metadata={'poll_id': poll.id})
    poll = GroupPoll.objects.select_related('created_by').prefetch_related('options', 'votes').get(id=poll.id)
    return JsonResponse({'status': 'success', 'poll': _poll_payload(poll, request.user)})


@login_required
@require_http_methods(['GET', 'POST'])
def group_tasks_api(request, group_id):
    group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
    membership, error = _require_group_member(group, request.user)
    if error is not None:
        return error

    if request.method == 'GET':
        tasks = (
            GroupTask.objects.filter(group=group)
            .select_related('created_by', 'assignee', 'completed_by')
            .order_by('status', 'due_at', '-created_at')[:100]
        )
        return JsonResponse({'status': 'success', 'tasks': [_task_payload(task) for task in tasks]})

    error = _require_group_manager(membership)
    if error is not None:
        return error
    data = _request_data(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    title = str(data.get('title') or '').strip()
    description = str(data.get('description') or '').strip()
    if not title or len(title) > 180 or len(description) > 1200:
        return JsonResponse({'status': 'error', 'message': 'Invalid task title or description'}, status=400)
    try:
        due_at = _parse_due_at(data.get('due_at'))
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    assignee_id = data.get('assignee_id')
    assignee = None
    if assignee_id is not None:
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Invalid assignee'}, status=400)
        assignee = User.objects.filter(id=assignee_id).first()
        if assignee is None:
            return JsonResponse({'status': 'error', 'message': 'Assignee must be an active group member'}, status=400)
        assignee_membership, assignee_error = _require_group_member(group, assignee)
        if assignee_error is not None:
            return JsonResponse({'status': 'error', 'message': 'Assignee must be an active group member'}, status=400)
        assignee = assignee_membership.user

    task = GroupTask.objects.create(
        group=group,
        created_by=request.user,
        assignee=assignee,
        title=title,
        description=description,
        due_at=due_at,
    )
    _create_group_audit_log(group, request.user, 'task_create', target_user=assignee, metadata={'task_id': task.id})
    task = GroupTask.objects.select_related('created_by', 'assignee', 'completed_by').get(id=task.id)
    return JsonResponse({'status': 'success', 'task': _task_payload(task)}, status=201)


@login_required
@require_http_methods(['POST'])
def complete_group_task_api(request, group_id, task_id):
    group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
    membership, error = _require_group_member(group, request.user)
    if error is not None:
        return error
    task = get_object_or_404(
        GroupTask.objects.select_related('created_by', 'assignee', 'completed_by'),
        id=task_id,
        group=group,
    )
    is_manager = membership.role in ('owner', 'admin')
    if task.assignee_id and task.assignee_id != request.user.id and not is_manager:
        return JsonResponse({'status': 'error', 'message': 'Only the assignee or a group manager can update this task'}, status=403)
    if task.status == GroupTask.STATUS_OPEN:
        task.status = GroupTask.STATUS_COMPLETED
        task.completed_by = request.user
        task.completed_at = timezone.now()
    else:
        task.status = GroupTask.STATUS_OPEN
        task.completed_by = None
        task.completed_at = None
    task.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_at'])
    _create_group_audit_log(
        group,
        request.user,
        'task_complete' if task.status == GroupTask.STATUS_COMPLETED else 'task_reopen',
        target_user=task.assignee,
        metadata={'task_id': task.id},
    )
    return JsonResponse({'status': 'success', 'task': _task_payload(task)})
