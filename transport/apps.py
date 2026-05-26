from django.apps import AppConfig


class TransportConfig(AppConfig):
    name = "transport"
    verbose_name = "Transport"

    def ready(self):
        # Branche les signaux (notifications email sur TrackingEvent).
        from . import signals  # noqa: F401
