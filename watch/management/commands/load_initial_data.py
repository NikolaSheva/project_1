import hashlib
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from watch.models import Brand, City, Product


class Command(BaseCommand):
    help = "Load initial data from fixtures if not already loaded."

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        fixtures = ["auth.json", "one_watch.json"]
        hash_file = os.path.join(base_dir, ".initial_data_hash")

        def compute_hash():
            hash_md5 = hashlib.sha256() 
            # hash_md5 = hashlib.md5()
            for fixture in fixtures:
                path = os.path.join(base_dir, fixture)
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        hash_md5.update(f.read())
            return hash_md5.hexdigest()

        current_hash = compute_hash()

        if os.path.exists(hash_file):
            with open(hash_file, "r") as f:
                saved_hash = f.read().strip()
            if saved_hash == current_hash:
                self.stdout.write(
                    "✔ Initial data already loaded (hash match). Skipping."
                )
                return

        self.stdout.write("🧹 Очистка старых данных...")
        Product.objects.all().delete()
        Brand.objects.all().delete()
        City.objects.all().delete()

        self.stdout.write("🗂 Загрузка новых данных...")
        for fixture in fixtures:
            path = os.path.join(base_dir, fixture)
            if os.path.exists(path):
                self.stdout.write(f"📦 Импорт: {fixture}")
                call_command("loaddata", path)
            else:
                self.stdout.write(f"⚠️ Фикстура {fixture} не найдена. Пропуск.")

        # Сохраняем новый хеш
        with open(hash_file, "w") as f:
            f.write(current_hash)
        self.stdout.write("✅ Загрузка завершена, хеш обновлён.")
