from django.apps import AppConfig

class KnowledgeProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_project'

    def ready(self):
        # 在这里导入您的信号模块
        import knowledge_project.signals