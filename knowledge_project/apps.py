from django.apps import AppConfig

class KnowledgeProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_project'

    def ready(self):
        import knowledge_project.models  # 确保 models.py 被导入
        import knowledge_project.signals  # 导入信号处理器