# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WP Plugin Scanner is a comprehensive security analysis tool that systematically discovers, analyzes, and audits WordPress plugins for potentially dangerous file upload functionality. The tool has evolved from a simple CLI application to a sophisticated desktop GUI application with database management capabilities.

**Key Use Cases:**
- Security researchers analyzing WordPress plugin ecosystem
- WordPress administrators evaluating plugin security
- Developers understanding upload patterns in WordPress plugins
- Bulk security auditing of plugin repositories

## Current Architecture (Post-2024 Updates)

The application has undergone significant architectural changes and now focuses on GUI-first design with comprehensive database management:

### Core Components

**Primary Interface:**
- **AuditGUI** (`wp_plugin_scanner/gui.py`): Main tkinter-based desktop interface with three-tab layout
  - Plugin Audit Tab: Security scanning interface
  - Plugin List Tab: Discovery and collection interface  
  - Database Viewer Tab: Analysis and filtering interface

**Plugin Discovery & Management:**
- **PluginLister** (`wp_plugin_scanner/plugin_lister.py`): Category-based plugin discovery from WordPress.org
- **PluginSearcher** (`wp_plugin_scanner/searcher.py`): Keyword-based plugin search with rate limiting
- **PluginDetailFetcher** (`wp_plugin_scanner/plugin_fetcher.py`): Complete metadata retrieval

**Security Analysis:**
- **AuditManager** (`wp_plugin_scanner/manager.py`): Orchestrates scanning workflow
- **RequestsDownloader** (`wp_plugin_scanner/downloader.py`): Downloads plugin ZIP files
- **UploadScanner** (`wp_plugin_scanner/scanner.py`): Pattern-based code analysis with file-level details

**Data Persistence:**
- **PluginDetailsSqliteReporter** (`wp_plugin_scanner/reporter.py`): Comprehensive metadata storage
- **SqliteReporter/CsvReporter**: Audit result storage with file-level match details
- **Unified audit results**: Single database with detailed match information

### Key Architectural Improvements

1. **GUI-First Design**: Desktop interface as primary user interaction method
2. **Comprehensive Discovery**: Category browsing and keyword search capabilities
3. **Database Management**: SQLite-based storage with advanced filtering and search
4. **Rate Limiting**: Sophisticated API respect with exponential backoff
5. **Progress Tracking**: Real-time page-by-page status updates
6. **Multilingual Support**: Japanese and English interfaces
7. **Audit Result Integration**: File-level match details with exact line numbers

## Current Workflow

### Typical User Journey
1. **Plugin Discovery**: Use Plugin List tab to browse by category or search by keyword
2. **Detail Collection**: System automatically fetches and stores complete plugin metadata
3. **Security Audit**: Select plugins for analysis in Plugin Audit tab
4. **Result Analysis**: Use Database Viewer for filtering, sorting, and exporting findings

### Data Flow
```
Plugin Discovery → Metadata Collection → Security Scanning → Database Storage → Analysis & Export
```

## Common Commands & Operations

### Application Launch
```bash
# Primary usage - launch GUI
python main.py

# GUI with debug output
python main.py --debug
```

### Legacy CLI Interface (still supported)
```bash
# Scan specific plugins
python main.py plugin-slug1 plugin-slug2

# Search and scan by keyword
python main.py --search "upload"

# Configure output format
python main.py --db-sqlite plugin-slug

# Disable file saving
python main.py --nosave plugin-slug

# Run tests
python main.py --test
```

### Testing
```bash
# Run all tests
python -m unittest tests/ -v

# Specific test modules
python -m unittest tests.test_searcher -v
```

## File Structure & Key Configuration

### Main Application Files
- `main.py`: Entry point and CLI argument handling
- `web_gui.py`: Legacy web interface (deprecated)
- `wp_plugin_scanner/gui.py`: Primary desktop GUI application

### Core Modules
```
wp_plugin_scanner/
├── config.py              # Configuration constants and patterns
├── models.py              # Data structures (PluginDetails, UploadMatch, etc.)
├── manager.py             # AuditManager orchestration
├── downloader.py          # Plugin file downloading
├── scanner.py             # Upload pattern detection
├── searcher.py            # Plugin search functionality
├── plugin_lister.py       # Category-based plugin discovery
├── plugin_fetcher.py      # Detailed metadata retrieval
└── reporter.py            # Data persistence (SQLite/CSV)
```

### Database Files
- `plugin_details.db`: Main SQLite database with plugin metadata
- `plugin_upload_audit.db`: Audit results (if using separate audit DB)
- `plugin_upload_audit.csv`: CSV format results
- `saved_plugins/`: Downloaded plugin source code (optional)

### Key Configuration
```python
# wp_plugin_scanner/config.py
UPLOAD_PATTERN = re.compile(
    rb"(wp_handle_upload|media_handle_upload|\$_FILES\b)",
    re.I | re.S,
)
MAX_SEARCH_RESULTS = 100
DEFAULT_TIMEOUT = 30
```

## Database Schema

### Plugin Metadata
```sql
CREATE TABLE plugin_details (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    author TEXT,
    description TEXT,
    short_description TEXT,
    last_updated TEXT,
    active_installs TEXT,
    active_installs_raw INTEGER,
    requires_wp TEXT,
    tested_up_to TEXT,
    requires_php TEXT,
    rating REAL,
    num_ratings INTEGER,
    support_threads INTEGER,
    support_threads_resolved INTEGER,
    downloaded INTEGER,
    tags TEXT,
    donate_link TEXT,
    homepage TEXT,
    download_link TEXT,
    screenshots TEXT,  -- JSON
    banners TEXT,      -- JSON
    icons TEXT,        -- JSON
    contributors TEXT,
    requires_plugins TEXT,
    compatibility TEXT, -- JSON
    added TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Audit Results
```sql
CREATE TABLE plugin_audit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL,
    upload TEXT NOT NULL,           -- 'True', 'False', 'Error'
    timestamp TEXT NOT NULL,
    files_scanned INTEGER DEFAULT 0,
    matches_count INTEGER DEFAULT 0,
    file_path TEXT DEFAULT '',      -- Specific file that matched
    line_number INTEGER DEFAULT 0,  -- Line number of match
    line_content TEXT DEFAULT '',   -- Actual code line
    matched_pattern TEXT DEFAULT '', -- Which pattern matched
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Integration & Rate Limiting

### WordPress.org API Endpoints
- Plugin Info: `https://api.wordpress.org/plugins/info/1.0/{slug}.json`
- Plugin Search: `https://wordpress.org/plugins/search/{keyword}/page/{page}/`
- Plugin Browse: `https://wordpress.org/plugins/browse/{category}/page/{page}/`

### Rate Limiting Strategy
- **Default intervals**: 2+ seconds between requests
- **Exponential backoff**: On 429 errors, wait increases exponentially
- **User-Agent headers**: Respectful identification
- **Request limits**: Configurable per-session limits
- **Progress feedback**: Real-time status updates during long operations

## GUI Interface Details

### Three-Tab Layout

**Plugin Audit Tab:**
- Input: Plugin slugs (manual entry or copied from database)
- Configuration: Save sources, output format (SQLite/CSV)
- Output: Security scan results with file-level details

**Plugin List Tab:**
- Discovery: Category browsing or keyword search
- Configuration: Limits, intervals, categories
- Auto-save: Automatic metadata collection and storage

**Database Viewer Tab:**
- Filtering: Search by name/author, filter by audit status
- Sorting: Multiple fields (downloads, rating, last updated, audit timestamp)
- Actions: View details, export CSV, copy slugs to audit, delete entries

### Japanese Localization
All interface elements are fully localized:
- Menu items, button labels, status messages
- Progress indicators and error messages  
- Database column headers and filter options

## Security Context & Patterns

### Upload Detection Patterns
The scanner identifies these potentially risky patterns:
```regex
(wp_handle_upload|media_handle_upload|\$_FILES\b)
```

**Pattern Significance:**
- `wp_handle_upload`: WordPress core file upload handler
- `media_handle_upload`: WordPress media library upload function
- `$_FILES`: PHP superglobal for uploaded files

### File-Level Analysis
- **Exact locations**: File path and line number reporting
- **Code context**: Actual matched code lines stored
- **Pattern identification**: Which regex pattern triggered the match
- **Statistics**: Files scanned count and total matches per plugin

## Development Guidelines

### Code Style
- Follow existing patterns in the codebase
- Use type hints where possible
- Maintain Japanese/English dual language support
- Implement proper error handling with user feedback

### Threading Considerations
- GUI operations use threading to prevent interface freezing
- Progress callbacks update UI safely using `root.after()`
- Database operations are thread-safe with proper locking
- Long-running operations can be cancelled by user

### Adding New Features

**New Scan Patterns:**
```python
# wp_plugin_scanner/config.py
UPLOAD_PATTERN = re.compile(
    rb"(existing_patterns|new_pattern)",
    re.I | re.S,
)
```

**New Database Fields:**
```python
# wp_plugin_scanner/models.py
@dataclass
class PluginDetails:
    # Add new fields here
    new_field: Optional[str] = None
```

**GUI Localization:**
Add translations to both language paths in GUI components.

## Common Issues & Solutions

### Database Connection Issues
- Multiple database files may exist; check all potential locations
- Permissions issues on database files
- Use debug mode to trace database operations

### Rate Limiting (429 Errors)
- Increase intervals between requests (3+ seconds recommended)
- Use exponential backoff (automatically implemented)
- Respect WordPress.org maintenance windows

### GUI Performance
- Large datasets may slow interface; implement pagination if needed
- Use threading for all long-running operations
- Provide progress feedback and cancellation options

### Memory Usage
- Plugin source files can consume significant disk space
- Use "nosave" option to disable source file retention
- Regular cleanup of temporary download directories

## Testing Strategy

### Unit Tests
- Test individual component functionality
- Mock external API calls for reliable testing
- Validate data persistence and retrieval

### Integration Tests
- Test complete workflows from discovery to analysis
- Validate GUI components and user interactions
- Test database operations and migrations

### Manual Testing Checklist
1. Plugin discovery via categories and search
2. Metadata collection and storage
3. Security audit execution
4. Database filtering and export
5. Error handling and rate limiting
6. Japanese/English language switching

This architecture provides a robust foundation for WordPress plugin security analysis with room for future enhancements in pattern detection, analysis capabilities, and user interface improvements.