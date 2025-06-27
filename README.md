# WordPress Plugin Security Scanner

A comprehensive security analysis tool that systematically discovers, analyzes, and audits WordPress plugins for potentially dangerous file upload functionality. This tool provides both automated plugin discovery and deep security scanning capabilities through an intuitive desktop interface.

## 🎯 Purpose & Value

WordPress plugins can contain file upload functionality that, if improperly secured, may pose security risks. This tool helps security researchers, WordPress administrators, and developers:

- **Discover plugins** systematically from WordPress.org repository
- **Analyze upload patterns** using regex-based code scanning
- **Track audit results** with comprehensive database management
- **Filter and sort** findings for efficient security review
- **Export results** for reporting and further analysis

## ✨ Core Features

### Plugin Discovery & Management
- **Category-based browsing**: Fetch plugins by popularity, newest, updated, favorites
- **Keyword search**: Find plugins using WordPress.org search API
- **Bulk operations**: Process hundreds of plugins efficiently
- **Rate limiting**: Respectful API usage with exponential backoff
- **Progress tracking**: Real-time status with page-by-page updates

### Security Analysis
- **Upload pattern detection**: Scans for `wp_handle_upload`, `media_handle_upload`, `$_FILES`
- **File-level analysis**: Reports exact file paths and line numbers
- **Match highlighting**: Shows actual code snippets that triggered detection
- **Comprehensive reporting**: Files scanned count and match statistics

### Data Management
- **Dual storage**: SQLite database and CSV export options
- **Plugin metadata**: Complete plugin information (author, version, downloads, ratings)
- **Audit history**: Track when plugins were analyzed
- **Advanced filtering**: Filter by audit status, sort by various criteria
- **Database viewer**: Browse all collected data with search and filters

### User Interface
- **Japanese/English support**: Fully localized interface
- **Three-tab layout**: Organized workflow from discovery to analysis
- **Real-time feedback**: Progress bars and status updates
- **Export functions**: CSV export of filtered results
- **Error handling**: Graceful failure with detailed error messages

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or later
- tkinter (usually included with Python)
- Internet connection for WordPress.org API access

### Installation
```bash
# Clone the repository
git clone https://github.com/your-repo/wp-plugin-scanner.git
cd wp-plugin-scanner

# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py
```

### First Use Workflow
1. **Launch GUI** → Start with the desktop interface
2. **Browse Plugins** → Go to "Plugin List" tab, select category, click "Start Fetch"
3. **Auto-save Details** → System automatically saves plugin metadata
4. **Run Security Audit** → Go to "Plugin Audit" tab, select plugins, run analysis
5. **Review Results** → Use "Database Viewer" tab to filter and examine findings

## 📋 Detailed Usage Guide

### Step 1: Plugin Discovery

#### Method A: Category-based Discovery
```
Plugin List Tab → Select Category (Popular/Newest/Updated/Favorites) → Set Options → Start Fetch
```

**Configuration Options:**
- **Category**: Choose from popular, newest, recently updated, or favorites
- **Limit**: Set maximum number of plugins (or uncheck for comprehensive scan)
- **Interval**: API request interval (minimum 1 second, recommended 2+ seconds)

**Best Practices:**
- Start with "Popular" category for high-value targets
- Use limits (50-100) for initial exploration
- Increase interval if you encounter rate limiting

#### Method B: Keyword Search
```
Plugin List Tab → Enter Search Term → Start Fetch
```

**Search Strategy:**
- Use specific terms: "upload", "media", "file", "attachment"
- Security-related: "security", "backup", "migration"
- Functionality: "gallery", "form", "ecommerce"

### Step 2: Automatic Plugin Detail Collection

When plugins are discovered, the system automatically:
1. **Fetches complete metadata** from WordPress.org API
2. **Stores in database** for persistent access
3. **Offers bulk detail fetching** for comprehensive data collection

**Retrieved Information:**
- Plugin name, version, author, description
- Download counts, active installations, ratings
- Last updated date, WordPress compatibility
- Tags, contributors, screenshots, banners

### Step 3: Security Audit Execution

#### Selecting Plugins for Audit
```
Plugin Audit Tab → Enter Plugin Slugs → Configure Options → Run Audit
```

**Input Methods:**
- **Manual entry**: Type plugin slugs (comma or space separated)
- **Copy from database**: Use "Copy Slug to Audit" button in Database Viewer
- **Bulk selection**: Select multiple plugins in Database Viewer

**Audit Configuration:**
- **Save Sources**: Keep downloaded plugin files for manual review
- **Output Format**: Choose SQLite (recommended) or CSV
- **Concurrency**: Tool automatically manages parallel processing

#### Understanding Audit Results

**Audit Status Meanings:**
- **✓ True**: Upload functionality detected
- **✗ False**: No upload patterns found
- **- Not Audited**: Plugin not yet analyzed
- **Error**: Audit failed (network, extraction, or parsing issues)

### Step 4: Results Analysis & Filtering

#### Database Viewer Features
```
Database Viewer Tab → Apply Filters → Review Results → Export if Needed
```

**Filtering Options:**
- **Search**: Plugin name, author, or description
- **Audit Status**: All, True findings, False findings, Not audited
- **Sorting**: Name, download count, rating, last updated, audit timestamp
- **Sort Order**: Ascending or descending

**Practical Filter Examples:**
1. **High-risk findings**: Audit Status = "True", Sort by "Downloads" descending
2. **Popular unaudited**: Audit Status = "Not Audited", Sort by "Downloads" descending  
3. **Recent updates**: Sort by "Last Updated" descending
4. **Highest rated**: Sort by "Rating" descending

#### Detailed Analysis
- **Double-click** any plugin for complete metadata
- **View Audit Results** button shows file-by-file scan details
- **Export** filtered results to CSV for external analysis

## 🔧 Advanced Features

### Command Line Interface
While GUI is recommended, CLI remains available:

```bash
# Scan specific plugins
python main.py plugin-slug1 plugin-slug2

# Search and scan by keyword  
python main.py --search "upload"

# Configure output format
python main.py --db-sqlite plugin-slug

# Disable file saving
python main.py --nosave plugin-slug
```

### API Rate Limiting & Best Practices

The tool implements sophisticated rate limiting:
- **Exponential backoff** on 429 errors
- **User-Agent headers** for respectful identification
- **Configurable intervals** between requests
- **Automatic retry logic** with progressive delays

**Recommended Settings:**
- **Interval**: 2+ seconds for sustained operations
- **Limit**: 100-500 plugins per session
- **Peak hours**: Avoid during WordPress.org maintenance windows

### Database Management

**Files Created:**
- `plugin_details.db`: Main SQLite database with all plugin information
- `plugin_upload_audit.db`: Audit results (if using separate audit DB)
- `plugin_upload_audit.csv`: CSV format results
- `saved_plugins/`: Downloaded plugin source code (if enabled)

**Maintenance:**
- Use "Delete Selected" to remove outdated entries
- Export before major updates
- Regular backups recommended for large datasets

## 🛠️ Troubleshooting

### Common Issues

#### "429 Too Many Requests" Errors
**Symptoms**: Rate limiting messages, failed downloads
**Solutions**: 
- Increase interval to 3+ seconds
- Reduce concurrent operations
- Use "Stop" button and retry later

#### "No plugins found" in Database Viewer
**Symptoms**: Empty database viewer despite successful scans
**Solutions**:
- Check if plugins were saved with "Auto-fetch Details" enabled
- Verify database file permissions
- Use "Refresh" button to reload data

#### GUI freezing during operations
**Symptoms**: Unresponsive interface during scans
**Solutions**:
- Use "Stop" button to cancel operations
- Reduce batch sizes
- Close other applications to free memory

#### Missing audit results after scanning
**Symptoms**: Audit completed but no results visible
**Solutions**:
- Check output format settings (SQLite vs CSV)
- Verify audit database file location
- Use "Filter Apply" to refresh database view

### Debug Information

Enable debug output by running:
```bash
python main.py --debug
```

Debug information includes:
- Database connection status
- Audit result loading details
- API response codes
- File processing status

## 🏗️ Technical Architecture

### Core Components
- **AuditManager**: Orchestrates scanning workflow
- **PluginLister**: Discovers plugins by category
- **PluginSearcher**: Searches plugins by keyword  
- **PluginDetailFetcher**: Retrieves complete plugin metadata
- **UploadScanner**: Analyzes code for upload patterns
- **Reporters**: Handle SQLite/CSV data persistence

### Data Flow
1. **Discovery** → Plugin slugs collected via listing or search
2. **Detail Fetch** → Complete metadata retrieved and stored
3. **Security Scan** → Source code analyzed for upload patterns
4. **Result Storage** → Findings saved to database with file-level details
5. **Analysis** → Database viewer provides filtering and export capabilities

### Security Patterns
The scanner detects these upload-related patterns:
```regex
(wp_handle_upload|media_handle_upload|\$_FILES\b)
```

**Pattern Explanation:**
- `wp_handle_upload`: WordPress core upload handler
- `media_handle_upload`: WordPress media upload function
- `$_FILES`: PHP file upload superglobal

## 📊 Output Formats

### SQLite Database Schema
```sql
-- Plugin metadata
CREATE TABLE plugin_details (
    slug TEXT PRIMARY KEY,
    name TEXT, version TEXT, author TEXT,
    description TEXT, last_updated TEXT,
    active_installs TEXT, rating REAL,
    downloaded INTEGER, tags TEXT,
    -- ... additional metadata fields
);

-- Audit results with file-level details
CREATE TABLE plugin_audit_results (
    id INTEGER PRIMARY KEY,
    slug TEXT, upload TEXT, timestamp TEXT,
    files_scanned INTEGER, matches_count INTEGER,
    file_path TEXT, line_number INTEGER,
    line_content TEXT, matched_pattern TEXT
);
```

### CSV Export Format
```csv
Slug,Name,Version,Author,Active Installs,Rating,Last Updated,Audit Result,Matches
plugin-slug,Plugin Name,1.0.0,Author Name,1000+,4.5,2024-01-01,✓ True,3
```

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m unittest tests/ -v

# Code formatting
python -m black wp_plugin_scanner/
```

### Adding New Scan Patterns
Edit `wp_plugin_scanner/config.py`:
```python
UPLOAD_PATTERN = re.compile(
    rb"(wp_handle_upload|media_handle_upload|\$_FILES\b|your_new_pattern)",
    re.I | re.S,
)
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is intended for legitimate security research and WordPress administration. Users are responsible for:
- Respecting WordPress.org API terms of service
- Using reasonable request rates to avoid service disruption
- Properly securing any downloaded plugin code
- Following responsible disclosure for any vulnerabilities discovered

The tool performs static analysis only and does not execute plugin code or test actual vulnerabilities.