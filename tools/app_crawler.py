"""
Semptify Application Crawler & Auditor
=======================================
Crawls through the application's GUI and systems to find problems.

Usage:
    python tools/app_crawler.py [--fix] [--verbose]

Features:
    - Scans all HTML files for issues
    - Checks JavaScript for common problems
    - Validates API endpoints
    - Checks static resources
    - Detects broken links and references
    - Finds unformatted dates
    - Reports missing dependencies
    - Checks Python code for issues
"""

import os
import re
import json
import asyncio
import aiohttp
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"
APP_DIR = BASE_DIR / "app"
TEMPLATES_DIR = BASE_DIR / "templates"

# Server URL for live testing
SERVER_URL = "http://localhost:8000"

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Issue:
    """Represents a detected issue."""
    severity: str  # critical, error, warning, info
    category: str  # html, js, css, api, python, config
    file: str
    line: Optional[int]
    message: str
    suggestion: Optional[str] = None
    auto_fixable: bool = False
    
    def to_dict(self):
        return {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable
        }


@dataclass
class CrawlReport:
    """Complete crawl report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    files_scanned: int = 0
    endpoints_tested: int = 0
    
    def add_issue(self, issue: Issue):
        self.issues.append(issue)
    
    def get_summary(self):
        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        for issue in self.issues:
            by_severity[issue.severity] += 1
            by_category[issue.category] += 1
        return {
            "total_issues": len(self.issues),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
            "files_scanned": self.files_scanned,
            "endpoints_tested": self.endpoints_tested
        }


# =============================================================================
# HTML SCANNER
# =============================================================================

class HTMLScanner:
    """Scans HTML files for issues."""
    
    # Patterns to detect
    UNFORMATTED_DATE_PATTERNS = [
        (r'\$\{[^}]*\.date\}(?!\s*\))', "Unformatted date display - use formatDate()"),
        (r'\$\{[^}]*_at\}(?!\s*\))', "Unformatted timestamp - use formatDateTime()"),
    ]
    
    MISSING_ALT_PATTERN = r'<img[^>]+(?!alt=)[^>]*>'
    EMPTY_HREF_PATTERN = r'href\s*=\s*["\'][\s]*["\']'
    INLINE_STYLE_PATTERN = r'style\s*=\s*["\'][^"\']{100,}["\']'
    CONSOLE_LOG_PATTERN = r'console\.(log|debug|info)\s*\('
    BROKEN_LINK_PATTERNS = [
        r'href\s*=\s*["\']([^"\']+)["\']',
        r'src\s*=\s*["\']([^"\']+)["\']',
    ]
    
    def __init__(self, report: CrawlReport):
        self.report = report
        self.all_files = set()
        self.referenced_files = set()
    
    def scan_directory(self, directory: Path):
        """Scan all HTML files in directory."""
        html_files = list(directory.glob("**/*.html"))
        
        for html_file in html_files:
            self.all_files.add(str(html_file.relative_to(BASE_DIR)))
            self.scan_file(html_file)
            self.report.files_scanned += 1
    
    def scan_file(self, filepath: Path):
        """Scan a single HTML file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            rel_path = str(filepath.relative_to(BASE_DIR))
            
            for i, line in enumerate(lines, 1):
                # Check for unformatted dates
                for pattern, message in self.UNFORMATTED_DATE_PATTERNS:
                    if re.search(pattern, line):
                        # Exclude already formatted dates and function parameters
                        if 'formatDate' not in line and 'formatDateTime' not in line and 'toLocale' not in line and 'new Date' not in line:
                            # Skip if it's a function parameter (onclick, data attribute, etc.)
                            # Examples: onclick="goToDate('${item.date}')", data-date="${item.date}"
                            is_function_param = bool(re.search(r'(onclick|data-|goTo|navigate|select|set|load)\w*\s*[=(]\s*["\']?\s*\$\{[^}]*\.date\}', line, re.IGNORECASE))
                            # Also skip if it's a filter/sort comparison
                            is_comparison = bool(re.search(r'(filter|sort|find|===|!==|>=|<=|>|<)\s*\([^)]*\.date', line, re.IGNORECASE))
                            if not is_function_param and not is_comparison:
                                self.report.add_issue(Issue(
                                    severity="warning",
                                    category="html",
                                    file=rel_path,
                                    line=i,
                                    message=message,
                                    suggestion="Wrap date in formatDate() or formatDateTime()",
                                    auto_fixable=True
                                ))
                
                # Check for console.log in production
                if re.search(self.CONSOLE_LOG_PATTERN, line):
                    # Skip if it's in a comment
                    if '//' not in line.split('console')[0]:
                        self.report.add_issue(Issue(
                            severity="info",
                            category="js",
                            file=rel_path,
                            line=i,
                            message="console.log found - consider removing for production",
                            suggestion="Remove or wrap in debug flag"
                        ))
                
                # Check for empty hrefs
                if re.search(self.EMPTY_HREF_PATTERN, line):
                    self.report.add_issue(Issue(
                        severity="warning",
                        category="html",
                        file=rel_path,
                        line=i,
                        message="Empty href attribute found",
                        suggestion="Add valid href or use button element"
                    ))
                
                # Check for very long inline styles
                if re.search(self.INLINE_STYLE_PATTERN, line):
                    self.report.add_issue(Issue(
                        severity="info",
                        category="html",
                        file=rel_path,
                        line=i,
                        message="Long inline style - consider moving to CSS",
                        suggestion="Extract to CSS class"
                    ))
                
                # Collect referenced files
                for pattern in self.BROKEN_LINK_PATTERNS:
                    for match in re.finditer(pattern, line):
                        href = match.group(1)
                        if href and not href.startswith(('http', 'https', '#', 'javascript:', 'mailto:', 'tel:', 'data:')):
                            self.referenced_files.add(href)
            
            # Check for missing formatDate function
            # Only flag if file has ${...date} patterns without ANY date formatting
            # Exclude files that appear to use form data (date inputs) rather than API dates
            if '${' in content and '.date' in content:
                has_date_formatting = any([
                    'function formatDate' in content,
                    'formatDate(' in content,
                    'toLocaleDateString(' in content,
                    'toLocaleString(' in content,
                    'toLocaleTimeString(' in content,
                    '.toDateString(' in content,
                ])
                # If file uses form date inputs, the dates are already formatted (YYYY-MM-DD)
                uses_form_dates = bool(re.search(r'type\s*=\s*["\']date["\']', content))
                # Check if file displays API timestamps (look for ISO date patterns or API fetch + date display)
                displays_api_dates = bool(re.search(r'\$\{[^}]*\.(date|created_at|updated_at)\}', content)) and '.json()' in content
                
                if not has_date_formatting and displays_api_dates and not uses_form_dates:
                    self.report.add_issue(Issue(
                        severity="warning",
                        category="js",
                        file=rel_path,
                        line=None,
                        message="File uses date displays but may be missing formatDate function",
                        suggestion="Add formatDate() helper function"
                    ))
            
            # Check for proper error handling in fetch calls
            fetch_count = content.count('fetch(')
            catch_count = content.count('.catch(') + content.count('catch {') + content.count('catch(')
            if fetch_count > catch_count + 2:  # Allow some margin
                self.report.add_issue(Issue(
                    severity="warning",
                    category="js",
                    file=rel_path,
                    line=None,
                    message=f"Found {fetch_count} fetch calls but only ~{catch_count} error handlers",
                    suggestion="Ensure all fetch calls have proper error handling"
                ))
                
        except Exception as e:
            self.report.add_issue(Issue(
                severity="error",
                category="html",
                file=str(filepath),
                line=None,
                message=f"Failed to scan file: {str(e)}"
            ))


# =============================================================================
# JAVASCRIPT SCANNER
# =============================================================================

class JavaScriptScanner:
    """Scans JavaScript files for issues."""
    
    DEPRECATED_PATTERNS = [
        (r'document\.write\s*\(', "document.write is deprecated"),
        (r'\.substr\s*\(', "substr() is deprecated, use substring() or slice()"),
        (r'escape\s*\(', "escape() is deprecated, use encodeURIComponent()"),
        (r'unescape\s*\(', "unescape() is deprecated, use decodeURIComponent()"),
    ]
    
    POTENTIAL_ISSUES = [
        (r'==\s*null(?!\s*\|\|)', "Use === for null comparison"),
        (r'!=\s*null', "Use !== for null comparison"),
        (r'var\s+\w+\s*=', "Consider using let or const instead of var"),
        (r'new\s+Array\s*\(\)', "Use [] instead of new Array()"),
        (r'new\s+Object\s*\(\)', "Use {} instead of new Object()"),
    ]
    
    def __init__(self, report: CrawlReport):
        self.report = report
    
    def scan_directory(self, directory: Path):
        """Scan all JS files in directory."""
        js_files = list(directory.glob("**/*.js"))
        
        for js_file in js_files:
            self.scan_file(js_file)
            self.report.files_scanned += 1
    
    def scan_file(self, filepath: Path):
        """Scan a single JS file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            rel_path = str(filepath.relative_to(BASE_DIR))
            
            for i, line in enumerate(lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('*'):
                    continue
                
                # Check deprecated patterns
                for pattern, message in self.DEPRECATED_PATTERNS:
                    if re.search(pattern, line):
                        self.report.add_issue(Issue(
                            severity="warning",
                            category="js",
                            file=rel_path,
                            line=i,
                            message=message
                        ))
                
                # Check potential issues
                for pattern, message in self.POTENTIAL_ISSUES:
                    if re.search(pattern, line):
                        self.report.add_issue(Issue(
                            severity="info",
                            category="js",
                            file=rel_path,
                            line=i,
                            message=message
                        ))
            
            # Check for undefined references
            self._check_undefined_references(content, rel_path)
            
        except Exception as e:
            self.report.add_issue(Issue(
                severity="error",
                category="js",
                file=str(filepath),
                line=None,
                message=f"Failed to scan file: {str(e)}"
            ))
    
    def _check_undefined_references(self, content: str, filepath: str):
        """Check for potentially undefined function calls."""
        # Find function definitions
        defined_funcs = set(re.findall(r'function\s+(\w+)\s*\(', content))
        defined_funcs.update(re.findall(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', content))
        defined_funcs.update(re.findall(r'(\w+)\s*:\s*(?:async\s*)?function', content))
        
        # Common global/built-in functions to ignore
        builtins = {
            'fetch', 'console', 'document', 'window', 'localStorage', 'sessionStorage',
            'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval', 'alert',
            'confirm', 'prompt', 'JSON', 'Array', 'Object', 'String', 'Number',
            'Boolean', 'Date', 'Math', 'RegExp', 'Error', 'Promise', 'Map', 'Set',
            'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURIComponent',
            'decodeURIComponent', 'encodeURI', 'decodeURI', 'eval', 'FormData',
            'URLSearchParams', 'URL', 'Blob', 'File', 'FileReader', 'Image',
            'WebSocket', 'XMLHttpRequest', 'navigator', 'location', 'history',
            'performance', 'requestAnimationFrame', 'cancelAnimationFrame',
            'getComputedStyle', 'matchMedia', 'MutationObserver', 'IntersectionObserver',
            'ResizeObserver', 'CustomEvent', 'Event', 'EventTarget', 'Node', 'Element',
            'HTMLElement', 'DocumentFragment', 'NodeList', 'DOMParser', 'XMLSerializer',
            'crypto', 'TextEncoder', 'TextDecoder', 'atob', 'btoa', 'Intl',
            'Proxy', 'Reflect', 'Symbol', 'WeakMap', 'WeakSet', 'ArrayBuffer',
            'DataView', 'Float32Array', 'Float64Array', 'Int8Array', 'Int16Array',
            'Int32Array', 'Uint8Array', 'Uint16Array', 'Uint32Array', 'BigInt',
            'require', 'module', 'exports', 'global', 'process', 'Buffer',
            'showToast', 'showProgress', 'updateProgress', 'hideProgress',  # Common app functions
        }
        defined_funcs.update(builtins)


# =============================================================================
# PYTHON SCANNER
# =============================================================================

class PythonScanner:
    """Scans Python files for issues."""
    
    ISSUE_PATTERNS = [
        (r'except\s*:', "Bare except clause - specify exception type"),
        (r'print\s*\((?!.*#.*debug)', "print() found - use logging instead"),
        (r'import\s+\*', "Wildcard import - import specific items"),
        (r'TODO|FIXME|HACK|XXX', "TODO/FIXME marker found"),
        (r'pass\s*$', "Empty pass statement - add implementation or comment"),
    ]
    
    SECURITY_PATTERNS = [
        (r'eval\s*\(', "eval() is dangerous - avoid if possible"),
        (r'exec\s*\(', "exec() is dangerous - avoid if possible"),
        (r'__import__\s*\(', "Dynamic import - potential security risk"),
        (r'pickle\.loads?\s*\(', "Pickle can execute arbitrary code"),
        (r'shell\s*=\s*True', "shell=True in subprocess is dangerous"),
    ]
    
    def __init__(self, report: CrawlReport):
        self.report = report
    
    def scan_directory(self, directory: Path):
        """Scan all Python files in directory."""
        py_files = list(directory.glob("**/*.py"))
        
        for py_file in py_files:
            # Skip virtual environment, cache, and the crawler itself
            if '.venv' in str(py_file) or '__pycache__' in str(py_file) or 'app_crawler.py' in str(py_file):
                continue
            self.scan_file(py_file)
            self.report.files_scanned += 1
    
    def scan_file(self, filepath: Path):
        """Scan a single Python file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            rel_path = str(filepath.relative_to(BASE_DIR))
            
            for i, line in enumerate(lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                
                # Check issue patterns
                for pattern, message in self.ISSUE_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        self.report.add_issue(Issue(
                            severity="info",
                            category="python",
                            file=rel_path,
                            line=i,
                            message=message
                        ))
                
                # Check security patterns
                for pattern, message in self.SECURITY_PATTERNS:
                    if re.search(pattern, line):
                        self.report.add_issue(Issue(
                            severity="warning",
                            category="python",
                            file=rel_path,
                            line=i,
                            message=f"Security: {message}"
                        ))
            
            # Check for missing docstrings in public functions
            self._check_docstrings(content, rel_path)
            
        except Exception as e:
            self.report.add_issue(Issue(
                severity="error",
                category="python",
                file=str(filepath),
                line=None,
                message=f"Failed to scan file: {str(e)}"
            ))
    
    def _check_docstrings(self, content: str, filepath: str):
        """Check for missing docstrings."""
        # Find function definitions without docstrings
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if re.match(r'^(?:async\s+)?def\s+[a-z_]\w*\s*\(', line):  # Public function
                # Check next non-empty line for docstring
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        if not (next_line.startswith('"""') or next_line.startswith("'''")):
                            func_name = re.search(r'def\s+(\w+)', line).group(1)
                            if not func_name.startswith('_'):  # Skip private functions
                                self.report.add_issue(Issue(
                                    severity="info",
                                    category="python",
                                    file=filepath,
                                    line=i + 1,
                                    message=f"Function '{func_name}' missing docstring"
                                ))
                        break


# =============================================================================
# API TESTER
# =============================================================================

class APITester:
    """Tests API endpoints for issues."""
    
    ENDPOINTS_TO_TEST = [
        ("GET", "/api/health", None, 200),
        ("GET", "/api/intake/documents?user_id=test", None, [200, 401]),
        ("GET", "/api/registry/documents?user_id=test", None, [200, 401]),
        ("GET", "/api/vault/documents?user_id=test", None, [200, 401]),
        ("GET", "/api/timeline/events?user_id=test", None, [200, 401]),
        ("GET", "/api/form-data/test", None, [200, 404]),
        ("GET", "/static/dashboard.html", None, 200),
        ("GET", "/static/document_intake.html", None, 200),
        ("GET", "/static/documents.html", None, 200),
        ("GET", "/static/js/shared-nav.js", None, 200),
    ]
    
    def __init__(self, report: CrawlReport, base_url: str = SERVER_URL):
        self.report = report
        self.base_url = base_url
    
    async def test_endpoints(self):
        """Test all configured endpoints."""
        async with aiohttp.ClientSession() as session:
            for method, path, body, expected_status in self.ENDPOINTS_TO_TEST:
                await self._test_endpoint(session, method, path, body, expected_status)
                self.report.endpoints_tested += 1
    
    async def _test_endpoint(self, session, method: str, path: str, body: dict, expected_status):
        """Test a single endpoint."""
        url = f"{self.base_url}{path}"
        try:
            async with session.request(method, url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if isinstance(expected_status, list):
                    if response.status not in expected_status:
                        self.report.add_issue(Issue(
                            severity="error",
                            category="api",
                            file=path,
                            line=None,
                            message=f"{method} {path} returned {response.status}, expected one of {expected_status}"
                        ))
                elif response.status != expected_status:
                    self.report.add_issue(Issue(
                        severity="error",
                        category="api",
                        file=path,
                        line=None,
                        message=f"{method} {path} returned {response.status}, expected {expected_status}"
                    ))
                
                # Check response time
                # Note: aiohttp doesn't have elapsed, would need to time it manually
                
        except aiohttp.ClientConnectorError:
            self.report.add_issue(Issue(
                severity="critical",
                category="api",
                file=path,
                line=None,
                message=f"Cannot connect to {url} - is the server running?"
            ))
        except asyncio.TimeoutError:
            self.report.add_issue(Issue(
                severity="error",
                category="api",
                file=path,
                line=None,
                message=f"{method} {path} timed out after 10 seconds"
            ))
        except Exception as e:
            self.report.add_issue(Issue(
                severity="error",
                category="api",
                file=path,
                line=None,
                message=f"Error testing {method} {path}: {str(e)}"
            ))


# =============================================================================
# RESOURCE CHECKER
# =============================================================================

class ResourceChecker:
    """Checks for missing or broken resources."""
    
    def __init__(self, report: CrawlReport):
        self.report = report
    
    def check_static_resources(self):
        """Check that all referenced static resources exist."""
        # Collect all references from HTML files
        references = set()
        
        for html_file in STATIC_DIR.glob("**/*.html"):
            try:
                content = html_file.read_text(encoding='utf-8')
                
                # Find src and href references
                for pattern in [r'src\s*=\s*["\']([^"\']+)["\']', r'href\s*=\s*["\']([^"\']+)["\']']:
                    for match in re.finditer(pattern, content):
                        ref = match.group(1)
                        # Skip dynamic references and special URLs
                        if ref and not ref.startswith(('http', 'https', '#', 'javascript:', 'mailto:', 'tel:', 'data:', '{')):
                            # Skip template variables
                            if '${' in ref or '{{' in ref:
                                continue
                            references.add((str(html_file.relative_to(BASE_DIR)), ref))
            except Exception:
                pass
        
        # Check each reference
        for source_file, ref in references:
            # Skip API routes (these are handled by backend)
            if ref.startswith('/api/') or ref.startswith('/eviction') or ref.startswith('/brain') or ref.startswith('/law'):
                continue
            # Skip route-like paths that are likely SPA routes
            if ref.startswith('/') and '.' not in ref.split('/')[-1] and ref not in ['/']:
                continue
                
            # Normalize reference
            if ref.startswith('/static/'):
                check_path = BASE_DIR / ref[1:]  # Remove leading /
            elif ref.startswith('/'):
                check_path = BASE_DIR / ref[1:]
            elif ref.startswith('./'):
                source_dir = (BASE_DIR / source_file).parent
                check_path = source_dir / ref[2:]
            elif ref.startswith('../'):
                source_dir = (BASE_DIR / source_file).parent
                check_path = (source_dir / ref).resolve()
            else:
                source_dir = (BASE_DIR / source_file).parent
                check_path = source_dir / ref
            
            # Handle query strings and fragments
            check_path = Path(str(check_path).split('?')[0].split('#')[0])
            
            if not check_path.exists():
                self.report.add_issue(Issue(
                    severity="warning",
                    category="resource",
                    file=source_file,
                    line=None,
                    message=f"Referenced resource not found: {ref}",
                    suggestion=f"Check if {check_path} exists or fix the reference"
                ))


# =============================================================================
# CONFIG CHECKER
# =============================================================================

class ConfigChecker:
    """Checks configuration files for issues."""
    
    def __init__(self, report: CrawlReport):
        self.report = report
    
    def check_all(self):
        """Run all config checks."""
        self._check_requirements()
        self._check_env()
        self._check_gitignore()
    
    def _check_requirements(self):
        """Check requirements.txt for issues."""
        req_file = BASE_DIR / "requirements.txt"
        if not req_file.exists():
            self.report.add_issue(Issue(
                severity="warning",
                category="config",
                file="requirements.txt",
                line=None,
                message="requirements.txt not found"
            ))
            return
        
        content = req_file.read_text()
        lines = content.strip().split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for unpinned versions
            if '==' not in line and '>=' not in line and '<=' not in line:
                if '@' not in line and line not in ['pip', 'setuptools', 'wheel']:
                    self.report.add_issue(Issue(
                        severity="info",
                        category="config",
                        file="requirements.txt",
                        line=i,
                        message=f"Unpinned dependency: {line}",
                        suggestion="Pin version with == for reproducible builds"
                    ))
    
    def _check_env(self):
        """Check for .env file and example."""
        env_file = BASE_DIR / ".env"
        env_example = BASE_DIR / ".env.example"
        
        if not env_file.exists() and not env_example.exists():
            self.report.add_issue(Issue(
                severity="info",
                category="config",
                file=".env",
                line=None,
                message="No .env or .env.example file found",
                suggestion="Create .env.example for documentation"
            ))
    
    def _check_gitignore(self):
        """Check .gitignore for common patterns."""
        gitignore = BASE_DIR / ".gitignore"
        if not gitignore.exists():
            self.report.add_issue(Issue(
                severity="warning",
                category="config",
                file=".gitignore",
                line=None,
                message=".gitignore not found"
            ))
            return
        
        content = gitignore.read_text()
        required_patterns = ['.env', '__pycache__', '.venv', 'venv', '*.pyc']
        
        for pattern in required_patterns:
            if pattern not in content:
                self.report.add_issue(Issue(
                    severity="info",
                    category="config",
                    file=".gitignore",
                    line=None,
                    message=f"Missing common pattern: {pattern}",
                    suggestion=f"Add {pattern} to .gitignore"
                ))


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """Generates the crawl report."""
    
    def __init__(self, report: CrawlReport):
        self.report = report
    
    def generate_console_report(self):
        """Generate console output."""
        summary = self.report.get_summary()
        
        print("\n" + "=" * 70)
        print("[REPORT] SEMPTIFY APPLICATION CRAWLER REPORT")
        print("=" * 70)
        print(f"Timestamp: {self.report.timestamp}")
        print(f"Files Scanned: {summary['files_scanned']}")
        print(f"Endpoints Tested: {summary['endpoints_tested']}")
        print(f"Total Issues: {summary['total_issues']}")
        print()
        
        # Summary by severity
        print("[SEVERITY] Issues by Severity:")
        severity_icons = {'critical': '[!!!]', 'error': '[ERR]', 'warning': '[WRN]', 'info': '[INF]'}
        for severity in ['critical', 'error', 'warning', 'info']:
            count = summary['by_severity'].get(severity, 0)
            icon = severity_icons.get(severity, '[---]')
            print(f"   {icon} {severity.upper()}: {count}")
        print()
        
        # Summary by category
        print("[CATEGORIES] Issues by Category:")
        for category, count in sorted(summary['by_category'].items()):
            print(f"   * {category}: {count}")
        print()
        
        # Detailed issues (grouped by severity)
        if self.report.issues:
            print("-" * 70)
            print("[DETAILS] DETAILED ISSUES")
            print("-" * 70)
            
            for severity in ['critical', 'error', 'warning', 'info']:
                issues = [i for i in self.report.issues if i.severity == severity]
                if issues:
                    icon = severity_icons.get(severity, '[---]')
                    print(f"\n{icon} {severity.upper()} ({len(issues)}):")
                    for issue in issues[:20]:  # Limit to first 20 per category
                        loc = f":{issue.line}" if issue.line else ""
                        print(f"   [{issue.category}] {issue.file}{loc}")
                        print(f"      -> {issue.message}")
                        if issue.suggestion:
                            print(f"      TIP: {issue.suggestion}")
                    if len(issues) > 20:
                        print(f"   ... and {len(issues) - 20} more")
        
        print("\n" + "=" * 70)
        print("[DONE] Crawl Complete")
        print("=" * 70 + "\n")
    
    def generate_json_report(self, output_path: Path):
        """Generate JSON report file."""
        data = {
            "timestamp": self.report.timestamp,
            "summary": self.report.get_summary(),
            "issues": [i.to_dict() for i in self.report.issues]
        }
        
        output_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(f"[FILE] JSON report saved to: {output_path}")
    
    def generate_html_report(self, output_path: Path):
        """Generate HTML report file."""
        summary = self.report.get_summary()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Semptify Crawler Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .severity-critical {{ border-left: 4px solid #dc3545; }}
        .severity-error {{ border-left: 4px solid #fd7e14; }}
        .severity-warning {{ border-left: 4px solid #ffc107; }}
        .severity-info {{ border-left: 4px solid #17a2b8; }}
        .issue {{ background: #f8f9fa; margin: 10px 0; padding: 15px; border-radius: 4px; }}
        .issue-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .issue-file {{ font-family: monospace; color: #666; }}
        .issue-message {{ margin: 10px 0; }}
        .issue-suggestion {{ color: #28a745; font-style: italic; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; color: white; }}
        .badge-critical {{ background: #dc3545; }}
        .badge-error {{ background: #fd7e14; }}
        .badge-warning {{ background: #ffc107; color: #333; }}
        .badge-info {{ background: #17a2b8; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Semptify Application Crawler Report</h1>
        <p>Generated: {self.report.timestamp}</p>
        
        <div class="summary">
            <div class="stat">
                <div class="stat-value">{summary['files_scanned']}</div>
                <div class="stat-label">Files Scanned</div>
            </div>
            <div class="stat">
                <div class="stat-value">{summary['endpoints_tested']}</div>
                <div class="stat-label">Endpoints Tested</div>
            </div>
            <div class="stat">
                <div class="stat-value">{summary['total_issues']}</div>
                <div class="stat-label">Total Issues</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #dc3545;">{summary['by_severity'].get('critical', 0)}</div>
                <div class="stat-label">Critical</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #fd7e14;">{summary['by_severity'].get('error', 0)}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #ffc107;">{summary['by_severity'].get('warning', 0)}</div>
                <div class="stat-label">Warnings</div>
            </div>
        </div>
        
        <h2>Issues by Category</h2>
        <table>
            <tr><th>Category</th><th>Count</th></tr>
            {''.join(f"<tr><td>{cat}</td><td>{count}</td></tr>" for cat, count in sorted(summary['by_category'].items()))}
        </table>
        
        <h2>Detailed Issues</h2>
        {''.join(self._issue_to_html(i) for i in self.report.issues)}
    </div>
</body>
</html>"""
        
        output_path.write_text(html, encoding='utf-8')
        print(f"[FILE] HTML report saved to: {output_path}")
    
    def _issue_to_html(self, issue: Issue) -> str:
        loc = f":{issue.line}" if issue.line else ""
        suggestion = f'<div class="issue-suggestion">💡 {issue.suggestion}</div>' if issue.suggestion else ''
        return f"""
        <div class="issue severity-{issue.severity}">
            <div class="issue-header">
                <span class="badge badge-{issue.severity}">{issue.severity.upper()}</span>
                <span class="issue-file">[{issue.category}] {issue.file}{loc}</span>
            </div>
            <div class="issue-message">{issue.message}</div>
            {suggestion}
        </div>"""


# =============================================================================
# MAIN
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Semptify Application Crawler & Auditor")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", type=str, help="Output JSON report to file")
    parser.add_argument("--html", type=str, help="Output HTML report to file")
    parser.add_argument("--no-api", action="store_true", help="Skip API testing")
    args = parser.parse_args()
    
    print("\n[CRAWLER] Starting Semptify Application Crawler...")
    print(f"   Base Directory: {BASE_DIR}\n")
    
    report = CrawlReport()
    
    # Run scanners
    print("[HTML] Scanning HTML files...")
    html_scanner = HTMLScanner(report)
    html_scanner.scan_directory(STATIC_DIR)
    if TEMPLATES_DIR.exists():
        html_scanner.scan_directory(TEMPLATES_DIR)
    
    print("[JS] Scanning JavaScript files...")
    js_scanner = JavaScriptScanner(report)
    js_scanner.scan_directory(STATIC_DIR)
    
    print("[PY] Scanning Python files...")
    py_scanner = PythonScanner(report)
    py_scanner.scan_directory(APP_DIR)
    py_scanner.scan_directory(BASE_DIR / "tools")
    
    print("[RESOURCES] Checking static resources...")
    resource_checker = ResourceChecker(report)
    resource_checker.check_static_resources()
    
    print("[CONFIG] Checking configuration files...")
    config_checker = ConfigChecker(report)
    config_checker.check_all()
    
    # API testing (optional)
    if not args.no_api:
        print("[API] Testing API endpoints...")
        api_tester = APITester(report)
        try:
            await api_tester.test_endpoints()
        except Exception as e:
            print(f"   [!] API testing failed: {e}")
    
    # Generate reports
    generator = ReportGenerator(report)
    generator.generate_console_report()
    
    if args.json:
        generator.generate_json_report(Path(args.json))
    
    if args.html:
        generator.generate_html_report(Path(args.html))
    
    # Default HTML report
    default_report = BASE_DIR / "tools" / "crawler_report.html"
    generator.generate_html_report(default_report)
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
