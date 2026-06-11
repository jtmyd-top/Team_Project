"""knowledge_project.views 包

原单文件 views.py (5865 行) 已按领域拆分为 9 个子模块:

- auth      认证 / 登录 / 注册 / 2FA / 密码重置 / 邮箱验证 / 限流
- captcha   人机验证 (Turnstile + 图形验证码)
- comment   笔记评论
- dashboard 战情室
- message   私信 / 屏蔽 / 用户公开资料
- note      笔记 CRUD / 浏览 / 搜索 / 历史 / 活动通知
- profile   个人资料 / 头像 / 邮箱 / 通知偏好 / 主题
- stats     首页社区统计
- upload    文件 / 图片上传 / 受保护媒体
- vault     保密柜

本文件统一 re-export 所有公开符号,以保持 urls.py / admin_auth.py /
folder_views.py / management 命令等外部对 `views.xxx` 的引用继续有效。
"""
from .auth import *  # noqa: F401, F403
from .captcha import *  # noqa: F401, F403
from .comment import *  # noqa: F401, F403
from .dashboard import *  # noqa: F401, F403
from .follow import *  # noqa: F401, F403
from .message import *  # noqa: F401, F403
from .note import *  # noqa: F401, F403
from .notifications import *  # noqa: F401, F403
from .profile import *  # noqa: F401, F403
from .stats import *  # noqa: F401, F403
from .upload import *  # noqa: F401, F403
from .vault import *  # noqa: F401, F403
