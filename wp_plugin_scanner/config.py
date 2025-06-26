import re
from pathlib import Path

DEFAULT_WORKERS = 8
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30
BACKOFF_FACTOR = 3
CSV_PATH = Path("plugin_upload_audit.csv")
SAVE_ROOT = Path("saved_plugins")
MAX_SEARCH_RESULTS = 50

UPLOAD_PATTERN = re.compile(
    rb"(wp_handle_upload|media_handle_upload|\$_FILES\b)",
    re.I | re.S,
)

ZIP_URL_TMPL = "https://downloads.wordpress.org/plugin/{slug}.latest-stable.zip"
SEARCH_URL_TMPL = "https://wordpress.org/plugins/search/{kw}/page/{page}/"
SLUG_RE = re.compile(r"https://wordpress\.org/plugins/([a-z0-9\-]+)/")
