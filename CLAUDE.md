# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WP Plugin Scanner is a security analysis tool that downloads WordPress plugins from the official repository and scans them for upload-related functionality. The tool can identify potentially dangerous file upload features in WordPress plugins.

## Core Architecture

The codebase follows a modular architecture with clear separation of concerns:

- **AuditManager** (`wp_plugin_scanner/manager.py`): Orchestrates the entire scanning process, coordinating between downloader, scanner, and reporter components
- **RequestsDownloader** (`wp_plugin_scanner/downloader.py`): Downloads plugin ZIP files from WordPress.org
- **UploadScanner** (`wp_plugin_scanner/scanner.py`): Scans extracted plugin files for upload-related patterns using regex
- **IReporter** (`wp_plugin_scanner/reporter.py`): Abstract interface for result reporting
- **CsvReporter** / **SqliteReporter**: CSV and SQLite database implementations for storing scan results
- **PluginSearcher** (`wp_plugin_scanner/searcher.py`): Searches WordPress.org for plugins by keyword

The tool supports two interfaces:
1. **CLI** (`main.py`): Command-line interface with various options
2. **Desktop GUI** (`wp_plugin_scanner/gui.py`): Tkinter-based desktop interface

## Common Commands

### Installation and Setup
```bash
pip install -r requirements.txt
```

### Running the Tool
```bash
# Launch desktop GUI (default behavior if no args provided and tkinter available)
python main.py

# Scan specific plugins
python main.py plugin-slug1 plugin-slug2

# Search and scan by keyword
python main.py --search "upload"

# Disable saving plugin files
python main.py --nosave plugin-slug

# Use SQLite database instead of CSV
python main.py --db-sqlite plugin-slug

# Use CSV format (default)
python main.py --db-csv plugin-slug

```

### Testing
```bash
# Run all tests
python main.py --test

# Run tests with unittest directly
python -m unittest tests.test_searcher -v
```


## Key Configuration

- **UPLOAD_PATTERN** (`wp_plugin_scanner/config.py`): Regex pattern used to detect upload-related code
- **SAVE_ROOT**: Directory where downloaded plugin files are saved (`saved_plugins/` by default)
- **Plugin files are saved to**: `saved_plugins/{plugin-slug}/`
- **Results are saved to**: `plugin_upload_audit.csv` (default) or `plugin_upload_audit.db` (SQLite)

## Threading and Concurrency

The tool uses ThreadPoolExecutor for concurrent plugin processing:
- Default worker count: 8 threads
- Configurable via `max_workers` parameter in AuditManager

## Data Flow

1. Plugin slugs are obtained via CLI args, keyword search, or GUI input
2. AuditManager coordinates the process using configured components
3. RequestsDownloader fetches plugin ZIP files to temporary directories
4. UploadScanner extracts and scans files for upload patterns
5. Results are reported via ExcelReporter and optionally saved to `saved_plugins/`
6. Temporary files are cleaned up automatically

## Security Context

This is a defensive security tool designed to identify potentially dangerous upload functionality in WordPress plugins. The scanner looks for patterns that could indicate file upload features which might be exploitable if not properly secured.