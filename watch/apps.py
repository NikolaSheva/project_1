# watch/apps.py

import logging
import os
import sys

from django.apps import AppConfig


class WatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "watch"

    def ready(self):
        if os.environ.get("INIT_WATCH_FIXTURE") == "true" and "runserver" in sys.argv:
            from django.core.management import call_command

            try:
                call_command("loaddata", "watch.json")
                logging.info("✅ Данные загружены из watch.json")
            except Exception as e:
                logging.error(f"❌ Ошибка загрузки данных: {e}")
