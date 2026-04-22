from django.apps import AppConfig


class CafeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cafe'

    def ready(self):
        import cafe.signals  # noqa: F401
