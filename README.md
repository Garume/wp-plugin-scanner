# WP Plugin Scanner

This project scans WordPress plugins for upload features.

## Features
- Download plugins from WordPress.org
- Search plugins by keyword
- Detect upload-related code
- Save results to CSV or SQLite database
- Optional desktop GUI

## Installation
1. Install Python 3.10 or later.
2. Run `pip install -r requirements.txt`.

## Usage
```
python main.py [options] [slug ...]
```
Options:
- `--search <keyword>`: find slugs by keyword
- `--save` / `--nosave`: enable or disable saving plugin files
- `--db-csv` / `--db-sqlite`: choose output format (CSV is default)
- With no arguments, opens the desktop GUI (requires Tkinter)

Results are stored in CSV (`plugin_upload_audit.csv`) or SQLite (`plugin_upload_audit.db`) and source files are saved under `saved_plugins`.

Run tests with:
```
python main.py --test
```
