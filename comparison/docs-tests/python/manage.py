import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
from django.core.management import execute_from_command_line

execute_from_command_line(sys.argv)
