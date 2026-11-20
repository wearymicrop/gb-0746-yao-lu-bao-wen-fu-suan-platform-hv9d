from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
NAME = "窑炉保温复算台"
PROJECT = "gb-0746"
RULE_VERSION = "1.0.0"
MAX_SOURCE_BYTES = 512 * 1024
MAX_ROWS = 2500
SAMPLES = {"clean": "干净样例", "dirty": "脏样例"}


def database_path():
    return Path(os.environ.get("APP_DB", ROOT / "instance" / "ledger.sqlite3"))
