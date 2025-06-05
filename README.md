# WP Plugin Scanner

This project scans WordPress plugins for upload features.

## Features
- Download plugins from WordPress.org
- Search plugins by keyword
- Detect upload-related code
- Save results to `plugin_upload_audit.xlsx`
- Optional GUI and web interface

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
- `--web`: launch the web GUI
- With no arguments, opens the desktop GUI (requires Tkinter)

Results are stored in Excel and source files are saved under `saved_plugins`.

Run tests with:
```
python main.py --test
```
