from .common import *  # noqa: F401,F403

@login_required
def moderation_view(request):
    """举报处置页面，仅超级管理员可访问。"""
    if not request.user.is_superuser:
        return redirect('home')
    return render(request, 'moderation/reports.html')


# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------
