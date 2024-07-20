from django.apps import AppConfig


class ReportcomoresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reportcomores'

    def ready(self):
        print("App is ready..................................")