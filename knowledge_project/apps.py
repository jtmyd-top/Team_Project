from django.apps import AppConfig


class KnowledgeProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_project'

    def ready(self):
        import knowledge_project.models  # noqa: F401
