from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Import scheduler so it starts when Django starts
        try:
            from api.utills import scheduler
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Scheduler failed to start: {e}")
