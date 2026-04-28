from pathlib import Path
import sys

API_DIR = Path(__file__).resolve().parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from apps.api.app import app
