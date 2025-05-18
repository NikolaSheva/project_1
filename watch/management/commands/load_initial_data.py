import hashlib
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Load initial data from fixtures if not already loaded.'

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        fixtures = ['auth.json', 'one_watch.json']
        hash_file = os.path.join(base_dir, '.initial_data_hash')

        def compute_hash():
            hash_md5 = hashlib.md5()
            for fixture in fixtures:
                path = os.path.join(base_dir, fixture)
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        hash_md5.update(f.read())
            return hash_md5.hexdigest()

        current_hash = compute_hash()

        if os.path.exists(hash_file):
            with open(hash_file, 'r') as f:
                saved_hash = f.read().strip()
            if saved_hash == current_hash:
                self.stdout.write("✔ Initial data already loaded (hash match). Skipping.")
                return

        self.stdout.write("🗂 Loading initial data...")
        for fixture in fixtures:
            path = os.path.join(base_dir, fixture)
            if os.path.exists(path):
                self.stdout.write(f"📦 Importing {fixture}...")
                call_command('loaddata', path)
            else:
                self.stdout.write(f"⚠️ Fixture {fixture} not found, skipping.")

        # Save new hash
        with open(hash_file, 'w') as f:
            f.write(current_hash)
        self.stdout.write("✅ Initial data loaded and hash updated.")

# from django.core.management.base import BaseCommand
# from django.core.management import call_command
# from django.conf import settings
# import os
#
# class Command(BaseCommand):
#     help = 'Load initial data from fixtures'
#
#     def handle(self, *args, **kwargs):
#         base_dir = settings.BASE_DIR
#
#         fixtures = ['auth.json', 'one_watch.json']
#
#         for fixture in fixtures:
#             path = os.path.join(base_dir, fixture)
#             if os.path.exists(path):
#                 self.stdout.write(f"Importing {fixture}...")
#                 call_command('loaddata', path)
#             else:
#                 self.stdout.write(f"⚠️ Fixture {fixture} not found, skipping.")
#

# from django.core.management.base import BaseCommand
# from django.core.management import call_command
# import os
#
# class Command(BaseCommand):
#     help = 'Load initial data from fixtures'
#
#     def handle(self, *args, **kwargs):
#         if os.path.exists('auth.json'):
#             self.stdout.write("Importing auth.json...")
#             call_command('loaddata', 'auth.json')
#         if os.path.exists('watch.json'):
#             self.stdout.write("Importing watch.json...")
#             call_command('loaddata', 'watch.json')
