from django.apps import AppConfig


class PlacesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'places'
    verbose_name = 'Quản lý Địa điểm & Mẹo'

    def ready(self):
        import places.signals  # noqa
