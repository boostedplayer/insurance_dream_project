import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Frontend directory se run karo taaki Django apps sahi se dhundh sake
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "frontend"))

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(["manage.py", "runserver", "8001"])
