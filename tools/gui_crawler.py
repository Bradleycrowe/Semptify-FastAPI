#!/usr/bin/env python3
"""
Semptify GUI Crawler - Find all errors, broken links, and issues
Run: python tools/gui_crawler.py
"""

import asyncio
import aiohttp
import os
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000"
STATIC_DIR = Path("static")

@dataclass
class Issue:
    severity: str  # error, warning, info
    page: str
    issue_type: str
    description: str
    element: str = ""
    line_hint: str = ""

@dataclass 
class CrawlReport:
    pages_checked: int = 0
    links_checked: int = 0
    api_endpoints_checked: int = 0
    issues: List[Issue] = field(default_factory=list)
    broken_links: List[Dict] = field(default_factory=list)
    js_errors: List[Dict] = field(default_factory=list)
    missing_elements: List[Dict] = field(default_factory=list)
    api_errors: List[Dict] = field(default_factory=list)

class GUICrawler:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.report = CrawlReport()
        self.checked_urls: Set[str] = set()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        # Create session with cookie jar to maintain auth
        self.session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def get_all_html_pages(self) -> List[Path]:
        """Find all HTML files in static directory"""
        pages = []
        for html_file in STATIC_DIR.rglob("*.html"):
            pages.append(html_file)
        return sorted(pages)

    async def check_url(self, url: str, source_page: str = "") -> bool:
        """Check if a URL is accessible"""
        if url in self.checked_urls:
            return True
        self.checked_urls.add(url)
        
        try:
            # Handle relative URLs
            if url.startswith('/'):
                full_url = f"{self.base_url}{url}"
            elif url.startswith('http'):
                full_url = url
            else:
                return True  # Skip anchors, javascript:, etc
                
            async with self.session.get(full_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                self.report.links_checked += 1
                if resp.status >= 400:
                    self.report.broken_links.append({
                        "url": url,
                        "status": resp.status,
                        "source": source_page
                    })
                    self.report.issues.append(Issue(
                        severity="error",
                        page=source_page,
                        issue_type="broken_link",
                        description=f"Broken link: {url} (HTTP {resp.status})",
                        element=f'href="{url}"'
                    ))
                    return False
                return True
        except asyncio.TimeoutError:
            self.report.broken_links.append({
                "url": url,
                "status": "timeout",
                "source": source_page
            })
            return False
        except Exception as e:
            self.report.broken_links.append({
                "url": url,
                "status": str(e),
                "source": source_page
            })
            return False

    async def check_api_endpoint(self, endpoint: str) -> Dict:
        """Test an API endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                self.report.api_endpoints_checked += 1
                data = None
                try:
                    data = await resp.json()
                except:
                    data = await resp.text()
                    
                result = {
                    "endpoint": endpoint,
                    "status": resp.status,
                    "ok": resp.status < 400
                }
                
                if resp.status >= 400:
                    self.report.api_errors.append({
                        "endpoint": endpoint,
                        "status": resp.status,
                        "response": str(data)[:200]
                    })
                    self.report.issues.append(Issue(
                        severity="error",
                        page="API",
                        issue_type="api_error",
                        description=f"API error: {endpoint} returned {resp.status}"
                    ))
                return result
        except Exception as e:
            self.report.api_errors.append({
                "endpoint": endpoint,
                "status": "exception",
                "error": str(e)
            })
            return {"endpoint": endpoint, "status": "error", "error": str(e)}

    def analyze_html_file(self, filepath: Path) -> List[Issue]:
        """Analyze an HTML file for common issues"""
        issues = []
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(content, 'html.parser')
        page_name = str(filepath)
        
        # Check for [object Object] patterns (common JS bug)
        if '[object Object]' in content:
            issues.append(Issue(
                severity="error",
                page=page_name,
                issue_type="object_object",
                description="Found '[object Object]' text - likely a JS bug displaying object instead of value"
            ))
        
        # Check for undefined/null in visible text
        script_tags = soup.find_all('script')
        non_script_content = content
        for script in script_tags:
            if script.string:
                non_script_content = non_script_content.replace(script.string, '')
        
        # Find broken image sources
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src or src == '#':
                issues.append(Issue(
                    severity="warning",
                    page=page_name,
                    issue_type="missing_image",
                    description="Image tag with missing or empty src",
                    element=str(img)[:100]
                ))
        
        # Find onclick handlers calling undefined functions
        onclick_pattern = re.compile(r'onclick="([^"]+)"')
        for match in onclick_pattern.finditer(content):
            handler = match.group(1)
            # Check if function is defined
            func_name = handler.split('(')[0].strip()
            if func_name and not re.search(rf'function\s+{func_name}\s*\(', content):
                if not re.search(rf'{func_name}\s*[:=]\s*(async\s+)?function', content):
                    if func_name not in ['SemptifyNav', 'SemptifyHelp', 'window', 'document', 'console', 'alert', 'confirm']:
                        # Check if it's a method call
                        if '.' not in func_name:
                            issues.append(Issue(
                                severity="warning", 
                                page=page_name,
                                issue_type="possible_undefined_function",
                                description=f"onclick handler '{func_name}' may be undefined",
                                element=handler
                            ))
        
        # Find elements with IDs referenced in JS but not defined
        id_refs = re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)', content)
        defined_ids = set(tag.get('id') for tag in soup.find_all(id=True))
        for id_ref in id_refs:
            if id_ref not in defined_ids:
                # Could be dynamic, just note it
                pass
        
        # Check for fetch calls to relative URLs
        fetch_pattern = re.compile(r'fetch\([\'"]([^\'"]+)[\'"]\)')
        for match in fetch_pattern.finditer(content):
            url = match.group(1)
            if url.startswith('/api/') or url.startswith('/storage/'):
                # These are API calls - we'll check them separately
                pass
                
        # Check for console.error calls (debugging left in)
        if 'console.error(' in content:
            issues.append(Issue(
                severity="info",
                page=page_name,
                issue_type="debug_code",
                description="Contains console.error() calls"
            ))
            
        # Check for TODO/FIXME comments
        todo_pattern = re.compile(r'(TODO|FIXME|XXX|HACK)[:|\s](.+)', re.IGNORECASE)
        for match in todo_pattern.finditer(content):
            issues.append(Issue(
                severity="info",
                page=page_name,
                issue_type="todo",
                description=f"{match.group(1)}: {match.group(2)[:50]}"
            ))
            
        # Check for empty href="#" links
        for a in soup.find_all('a', href='#'):
            text = a.get_text(strip=True)
            if text and text not in ['#', '']:
                issues.append(Issue(
                    severity="info",
                    page=page_name,
                    issue_type="placeholder_link",
                    description=f"Link with href='#': {text[:30]}"
                ))
        
        return issues

    def extract_links(self, filepath: Path) -> List[str]:
        """Extract all links from an HTML file"""
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                links.append(href)
                
        for link in soup.find_all('link', href=True):
            href = link['href']
            if href:
                links.append(href)
                
        for script in soup.find_all('script', src=True):
            links.append(script['src'])
            
        return links

    def extract_api_calls(self, filepath: Path) -> List[str]:
        """Extract API endpoints from JavaScript in HTML"""
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        endpoints = set()
        
        # Find fetch() calls
        fetch_pattern = re.compile(r'fetch\([\'"]([^\'"]+)[\'"]\)')
        for match in fetch_pattern.finditer(content):
            url = match.group(1)
            if url.startswith('/'):
                endpoints.add(url.split('?')[0])  # Remove query params
                
        return list(endpoints)

    async def crawl_page(self, filepath: Path):
        """Crawl a single HTML page"""
        page_name = str(filepath)
        print(f"  📄 Checking {filepath.name}...")
        
        # Analyze HTML structure
        issues = self.analyze_html_file(filepath)
        self.report.issues.extend(issues)
        
        # Extract and check links
        links = self.extract_links(filepath)
        for link in links:
            if link.startswith('/static/') or link.startswith('/'):
                await self.check_url(link, page_name)
                
        self.report.pages_checked += 1

    async def check_common_api_endpoints(self):
        """Check common API endpoints"""
        print("\n🔌 Checking API endpoints...")
        
        endpoints = [
            "/api/documents/",
            "/api/timeline/",
            "/api/defenses/",
            "/api/motions/",
            "/api/counterclaims/",
            "/storage/status",
            "/storage/session",
            "/api/laws/categories",
            "/dashboard",
            "/health",
        ]
        
        for endpoint in endpoints:
            print(f"  🔗 {endpoint}")
            await self.check_api_endpoint(endpoint)

    async def run(self):
        """Run the full crawl"""
        print("=" * 60)
        print("Semptify GUI Crawler")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Base URL: {self.base_url}")
        print()
        
        # Get all HTML pages
        pages = self.get_all_html_pages()
        print(f"📁 Found {len(pages)} HTML pages to check\n")
        
        print("📄 Analyzing HTML files...")
        for page in pages:
            await self.crawl_page(page)
            
        # Check API endpoints
        await self.check_common_api_endpoints()
        
        # Also extract and check API calls from all pages
        print("\n🔍 Checking API calls found in pages...")
        all_api_calls = set()
        for page in pages:
            api_calls = self.extract_api_calls(page)
            all_api_calls.update(api_calls)
        
        for endpoint in all_api_calls:
            if endpoint not in [e["endpoint"] for e in self.report.api_errors]:
                await self.check_api_endpoint(endpoint)
                
        return self.report

    def print_report(self):
        """Print the crawl report"""
        r = self.report
        
        print("\n" + "=" * 60)
        print("📊 CRAWL REPORT")
        print("=" * 60)
        
        print(f"\n📈 Summary:")
        print(f"   Pages checked: {r.pages_checked}")
        print(f"   Links checked: {r.links_checked}")
        print(f"   API endpoints checked: {r.api_endpoints_checked}")
        print(f"   Total issues: {len(r.issues)}")
        
        # Group issues by severity
        errors = [i for i in r.issues if i.severity == "error"]
        warnings = [i for i in r.issues if i.severity == "warning"]
        infos = [i for i in r.issues if i.severity == "info"]
        
        print(f"\n   🔴 Errors: {len(errors)}")
        print(f"   🟡 Warnings: {len(warnings)}")
        print(f"   🔵 Info: {len(infos)}")
        
        if errors:
            print("\n" + "-" * 60)
            print("🔴 ERRORS")
            print("-" * 60)
            for issue in errors:
                print(f"\n  [{issue.issue_type}] {issue.page}")
                print(f"  → {issue.description}")
                if issue.element:
                    print(f"    Element: {issue.element[:80]}")
                    
        if warnings:
            print("\n" + "-" * 60)
            print("🟡 WARNINGS")
            print("-" * 60)
            for issue in warnings:
                print(f"\n  [{issue.issue_type}] {issue.page}")
                print(f"  → {issue.description}")
                    
        if r.broken_links:
            print("\n" + "-" * 60)
            print("🔗 BROKEN LINKS")
            print("-" * 60)
            for link in r.broken_links:
                print(f"  {link['url']} → {link['status']}")
                print(f"    Source: {link['source']}")
                
        if r.api_errors:
            print("\n" + "-" * 60)
            print("🔌 API ERRORS")
            print("-" * 60)
            for err in r.api_errors:
                print(f"  {err['endpoint']} → {err['status']}")
                if 'response' in err:
                    print(f"    Response: {err['response'][:100]}")
        
        # Save detailed report to JSON
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "pages_checked": r.pages_checked,
                "links_checked": r.links_checked,
                "api_endpoints_checked": r.api_endpoints_checked,
                "total_issues": len(r.issues),
                "errors": len(errors),
                "warnings": len(warnings),
                "info": len(infos)
            },
            "issues": [
                {
                    "severity": i.severity,
                    "page": i.page,
                    "type": i.issue_type,
                    "description": i.description,
                    "element": i.element
                }
                for i in r.issues
            ],
            "broken_links": r.broken_links,
            "api_errors": r.api_errors
        }
        
        report_path = Path("tools/crawl_report.json")
        report_path.write_text(json.dumps(report_data, indent=2))
        print(f"\n💾 Full report saved to: {report_path}")
        
        print("\n" + "=" * 60)
        if errors:
            print("❌ Crawl completed with ERRORS")
        elif warnings:
            print("⚠️ Crawl completed with warnings")
        else:
            print("✅ Crawl completed - no issues found!")
        print("=" * 60)


async def main():
    async with GUICrawler() as crawler:
        await crawler.run()
        crawler.print_report()


if __name__ == "__main__":
    asyncio.run(main())
