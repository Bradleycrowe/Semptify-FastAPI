"""
Semptify 5.0 - Ethical Web Crawler Service
Crawls public government data for tenant defense research.

ETHICAL GUIDELINES:
- Only crawls PUBLIC government/legal data
- Respects robots.txt
- Rate limits all requests (1 req/sec default)
- Identifies itself with User-Agent
- Caches results to minimize server load
- No personal data scraping
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class CrawlerConfig:
    """Crawler configuration."""
    USER_AGENT = "Semptify/5.0 (Tenant Rights Research Bot; +https://semptify.org/bot)"
    RATE_LIMIT_SECONDS = 1.0  # Minimum seconds between requests to same domain
    REQUEST_TIMEOUT = 30.0
    MAX_RETRIES = 3
    CACHE_DIR = Path("data/crawler_cache")
    CACHE_TTL_HOURS = 24  # Cache results for 24 hours
    MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB max


class SourceType(str, Enum):
    """Types of data sources."""
    COURT_RECORDS = "court_records"
    STATUTES = "statutes"
    PROPERTY_RECORDS = "property_records"
    BUSINESS_REGISTRY = "business_registry"
    GOVERNMENT_FORMS = "government_forms"
    NEWS = "news"
    LEGAL_AID = "legal_aid"


@dataclass
class CrawlResult:
    """Result from a crawl operation."""
    url: str
    success: bool
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None
    data: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    error: Optional[str] = None
    cached: bool = False
    crawled_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str
    source_type: SourceType
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Minnesota Public Data Sources
# =============================================================================

MN_SOURCES = {
    "mn_statutes": {
        "name": "Minnesota Statutes",
        "base_url": "https://www.revisor.mn.gov",
        "search_url": "https://www.revisor.mn.gov/search/?search=statutes&keyword={query}",
        "type": SourceType.STATUTES,
        "robots_ok": True,
        "description": "Official Minnesota state laws and statutes"
    },
    "mn_courts": {
        "name": "Minnesota Judicial Branch",
        "base_url": "https://www.mncourts.gov",
        "search_url": "https://www.mncourts.gov/search/?q={query}",
        "type": SourceType.COURT_RECORDS,
        "robots_ok": True,
        "description": "Court information and resources"
    },
    "mn_ag": {
        "name": "Minnesota Attorney General",
        "base_url": "https://www.ag.state.mn.us",
        "search_url": "https://www.ag.state.mn.us/search/?q={query}",
        "type": SourceType.GOVERNMENT_FORMS,
        "robots_ok": True,
        "description": "Consumer protection and tenant rights resources"
    },
    "mn_commerce": {
        "name": "MN Department of Commerce",
        "base_url": "https://mn.gov/commerce",
        "search_url": "https://mn.gov/commerce/search/?q={query}",
        "type": SourceType.BUSINESS_REGISTRY,
        "robots_ok": True,
        "description": "Business licenses and real estate professionals"
    },
    "mn_sos": {
        "name": "MN Secretary of State - Business Search",
        "base_url": "https://mblsportal.sos.state.mn.us",
        "search_url": "https://mblsportal.sos.state.mn.us/Business/Search",
        "type": SourceType.BUSINESS_REGISTRY,
        "robots_ok": True,
        "description": "Business entity registration lookup"
    },
    "hennepin_property": {
        "name": "Hennepin County Property Records",
        "base_url": "https://www.hennepin.us",
        "search_url": "https://www.hennepin.us/residents/property/property-information",
        "type": SourceType.PROPERTY_RECORDS,
        "robots_ok": True,
        "description": "Property tax and ownership records"
    },
    "ramsey_property": {
        "name": "Ramsey County Property Records",
        "base_url": "https://www.ramseycounty.us",
        "search_url": "https://www.ramseycounty.us/residents/property-home/property-data",
        "type": SourceType.PROPERTY_RECORDS,
        "robots_ok": True,
        "description": "Property tax and ownership records"
    },
    "dakota_property": {
        "name": "Dakota County Property Records",
        "base_url": "https://www.co.dakota.mn.us",
        "search_url": "https://www.co.dakota.mn.us/homepropertyandland/propertytaxes",
        "type": SourceType.PROPERTY_RECORDS,
        "robots_ok": True,
        "description": "Property tax and ownership records"
    },
    "hud": {
        "name": "HUD Fair Housing",
        "base_url": "https://www.hud.gov",
        "search_url": "https://www.hud.gov/search?query={query}",
        "type": SourceType.GOVERNMENT_FORMS,
        "robots_ok": True,
        "description": "Federal housing rights and complaint forms"
    },
    "legal_aid_mn": {
        "name": "LawHelp Minnesota",
        "base_url": "https://www.lawhelpmn.org",
        "search_url": "https://www.lawhelpmn.org/search?keyword={query}",
        "type": SourceType.LEGAL_AID,
        "robots_ok": True,
        "description": "Free legal information and resources"
    },
    "homeline": {
        "name": "HOME Line Minnesota",
        "base_url": "https://homelinemn.org",
        "search_url": "https://homelinemn.org/?s={query}",
        "type": SourceType.LEGAL_AID,
        "robots_ok": True,
        "description": "Tenant hotline and resources"
    },
}


# =============================================================================
# Crawler Service
# =============================================================================

class CrawlerService:
    """
    Ethical web crawler for tenant defense research.
    Only crawls public government and legal aid data.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._rate_limits: dict[str, float] = {}  # domain -> last_request_time
        self._cache_dir = CrawlerConfig.CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": CrawlerConfig.USER_AGENT},
                timeout=CrawlerConfig.REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Robots.txt Compliance
    # =========================================================================

    async def _check_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            if domain not in self._robots_cache:
                robots_url = f"{domain}/robots.txt"
                client = await self._get_client()
                
                try:
                    response = await client.get(robots_url)
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    if response.status_code == 200:
                        rp.parse(response.text.splitlines())
                    self._robots_cache[domain] = rp
                except Exception:
                    # If we can't get robots.txt, assume allowed
                    rp = RobotFileParser()
                    self._robots_cache[domain] = rp
            
            rp = self._robots_cache[domain]
            return rp.can_fetch(CrawlerConfig.USER_AGENT, url)
            
        except Exception as e:
            logger.warning(f"Robots.txt check failed for {url}: {e}")
            return True  # Assume allowed if check fails

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def _rate_limit(self, url: str):
        """Apply rate limiting per domain."""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        if domain in self._rate_limits:
            elapsed = time.time() - self._rate_limits[domain]
            if elapsed < CrawlerConfig.RATE_LIMIT_SECONDS:
                wait_time = CrawlerConfig.RATE_LIMIT_SECONDS - elapsed
                await asyncio.sleep(wait_time)
        
        self._rate_limits[domain] = time.time()

    # =========================================================================
    # Caching
    # =========================================================================

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached(self, url: str) -> Optional[CrawlResult]:
        """Get cached result if valid."""
        cache_key = self._get_cache_key(url)
        cache_file = self._cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                crawled_at = datetime.fromisoformat(data.get("crawled_at", "2000-01-01"))
                
                if datetime.utcnow() - crawled_at < timedelta(hours=CrawlerConfig.CACHE_TTL_HOURS):
                    result = CrawlResult(**data)
                    result.cached = True
                    return result
            except Exception:
                pass
        
        return None

    def _save_cache(self, result: CrawlResult):
        """Save result to cache."""
        try:
            cache_key = self._get_cache_key(result.url)
            cache_file = self._cache_dir / f"{cache_key}.json"
            
            data = {
                "url": result.url,
                "success": result.success,
                "status_code": result.status_code,
                "content_type": result.content_type,
                "title": result.title,
                "text": result.text[:50000] if result.text else None,  # Limit cached text
                "data": result.data,
                "links": result.links[:100],  # Limit cached links
                "crawled_at": result.crawled_at,
            }
            
            cache_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    # =========================================================================
    # Core Crawling
    # =========================================================================

    async def crawl(self, url: str, use_cache: bool = True) -> CrawlResult:
        """
        Crawl a URL ethically.
        
        Args:
            url: URL to crawl
            use_cache: Whether to use cached results
            
        Returns:
            CrawlResult with page data
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached(url)
            if cached:
                logger.info(f"📦 Cache hit: {url}")
                return cached

        # Check robots.txt
        if not await self._check_robots(url):
            logger.warning(f"🚫 Blocked by robots.txt: {url}")
            return CrawlResult(
                url=url,
                success=False,
                error="Blocked by robots.txt"
            )

        # Rate limit
        await self._rate_limit(url)

        # Fetch page
        try:
            client = await self._get_client()
            response = await client.get(url)
            
            content_type = response.headers.get("content-type", "")
            
            result = CrawlResult(
                url=str(response.url),
                success=response.status_code == 200,
                status_code=response.status_code,
                content_type=content_type,
            )

            if response.status_code == 200:
                if "text/html" in content_type:
                    result = self._parse_html(result, response.text)
                elif "application/json" in content_type:
                    result.data = response.json()
                else:
                    result.text = response.text[:CrawlerConfig.MAX_CONTENT_SIZE]

            # Cache successful results
            if result.success:
                self._save_cache(result)

            logger.info(f"✅ Crawled: {url} ({response.status_code})")
            return result

        except httpx.TimeoutException:
            logger.error(f"⏱️ Timeout: {url}")
            return CrawlResult(url=url, success=False, error="Request timeout")
        except Exception as e:
            logger.error(f"❌ Crawl failed: {url} - {e}")
            return CrawlResult(url=url, success=False, error=str(e))

    def _parse_html(self, result: CrawlResult, html: str) -> CrawlResult:
        """Parse HTML content and extract useful data."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Get title
        title_tag = soup.find("title")
        result.title = title_tag.get_text(strip=True) if title_tag else None
        
        # Get main text content
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        result.text = soup.get_text(separator="\n", strip=True)
        result.html = html
        
        # Extract links
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                links.append(href)
            elif href.startswith("/"):
                # Convert relative to absolute
                parsed = urlparse(result.url)
                links.append(f"{parsed.scheme}://{parsed.netloc}{href}")
        result.links = list(set(links))[:100]  # Dedupe and limit
        
        # Extract structured data
        result.data = self._extract_structured_data(soup)
        
        return result

    def _extract_structured_data(self, soup: BeautifulSoup) -> dict:
        """Extract structured data from HTML."""
        data = {}
        
        # Get meta description
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            data["description"] = meta_desc.get("content", "")
        
        # Get headings
        headings = []
        for level in range(1, 4):
            for h in soup.find_all(f"h{level}"):
                headings.append({
                    "level": level,
                    "text": h.get_text(strip=True)
                })
        if headings:
            data["headings"] = headings[:20]
        
        # Get tables (often contain important legal data)
        tables = []
        for table in soup.find_all("table")[:5]:
            rows = []
            for tr in table.find_all("tr")[:50]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        if tables:
            data["tables"] = tables
        
        # Get PDF links (often forms and documents)
        pdf_links = []
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                pdf_links.append({
                    "text": a.get_text(strip=True),
                    "url": a["href"]
                })
        if pdf_links:
            data["pdf_links"] = pdf_links[:20]
        
        return data

    # =========================================================================
    # Search Methods
    # =========================================================================

    async def search_mn_statutes(self, query: str) -> list[SearchResult]:
        """Search Minnesota Statutes."""
        source = MN_SOURCES["mn_statutes"]
        url = f"https://www.revisor.mn.gov/statutes/cite/{query.replace(' ', '')}"
        
        result = await self.crawl(url)
        results = []
        
        if result.success and result.text:
            # Extract statute sections
            results.append(SearchResult(
                title=result.title or f"MN Statute {query}",
                url=result.url,
                snippet=result.text[:500] if result.text else "",
                source=source["name"],
                source_type=source["type"],
                relevance_score=1.0,
            ))
        
        return results

    async def search_business(self, business_name: str) -> list[SearchResult]:
        """Search Minnesota business registry."""
        results = []
        
        # Search MN SOS
        source = MN_SOURCES["mn_sos"]
        search_url = f"{source['search_url']}?BusinessName={business_name.replace(' ', '+')}"
        
        result = await self.crawl(search_url)
        
        if result.success:
            results.append(SearchResult(
                title=f"Business Search: {business_name}",
                url=result.url,
                snippet=result.text[:500] if result.text else "Search results",
                source=source["name"],
                source_type=source["type"],
                relevance_score=0.9,
                metadata=result.data,
            ))
        
        return results

    async def search_property(self, address: str, county: str = "hennepin") -> list[SearchResult]:
        """Search county property records."""
        county_lower = county.lower()
        source_key = f"{county_lower}_property"
        
        if source_key not in MN_SOURCES:
            source_key = "hennepin_property"  # Default
        
        source = MN_SOURCES[source_key]
        result = await self.crawl(source["search_url"])
        
        results = []
        if result.success:
            results.append(SearchResult(
                title=f"Property Records: {address}",
                url=result.url,
                snippet=f"Property information for {county} County",
                source=source["name"],
                source_type=source["type"],
                relevance_score=0.8,
            ))
        
        return results

    async def search_legal_resources(self, query: str) -> list[SearchResult]:
        """Search legal aid resources."""
        results = []
        
        # Search LawHelp MN
        for source_key in ["legal_aid_mn", "homeline"]:
            source = MN_SOURCES[source_key]
            search_url = source["search_url"].format(query=query.replace(" ", "+"))
            
            result = await self.crawl(search_url)
            
            if result.success:
                results.append(SearchResult(
                    title=result.title or f"Legal Resources: {query}",
                    url=result.url,
                    snippet=result.text[:500] if result.text else "",
                    source=source["name"],
                    source_type=source["type"],
                    relevance_score=0.85,
                ))
        
        return results

    async def search_all(self, query: str) -> list[SearchResult]:
        """Search all configured sources."""
        all_results = []
        
        # Search in parallel with rate limiting per domain
        tasks = []
        
        for source_key, source in MN_SOURCES.items():
            if "search_url" in source and "{query}" in source.get("search_url", ""):
                search_url = source["search_url"].format(query=query.replace(" ", "+"))
                tasks.append(self._search_source(search_url, source))
        
        # Execute with limited concurrency
        for task in tasks:
            result = await task
            if result:
                all_results.extend(result)
        
        # Sort by relevance
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return all_results

    async def _search_source(self, url: str, source: dict) -> list[SearchResult]:
        """Search a single source."""
        result = await self.crawl(url)
        
        if not result.success:
            return []
        
        return [SearchResult(
            title=result.title or source["name"],
            url=result.url,
            snippet=result.text[:500] if result.text else source["description"],
            source=source["name"],
            source_type=source["type"],
            relevance_score=0.7,
            metadata=result.data,
        )]

    # =========================================================================
    # Specialized Extractors
    # =========================================================================

    async def get_mn_statute(self, chapter: str, section: Optional[str] = None) -> dict:
        """Get a specific Minnesota statute."""
        if section:
            url = f"https://www.revisor.mn.gov/statutes/cite/{chapter}.{section}"
        else:
            url = f"https://www.revisor.mn.gov/statutes/cite/{chapter}"
        
        result = await self.crawl(url)
        
        if not result.success:
            return {"error": result.error, "url": url}
        
        return {
            "chapter": chapter,
            "section": section,
            "url": result.url,
            "title": result.title,
            "text": result.text,
            "cached": result.cached,
        }

    async def get_tenant_rights_statutes(self) -> list[dict]:
        """Get key Minnesota tenant rights statutes."""
        key_statutes = [
            ("504B", None, "Landlord Tenant Law"),
            ("504B", "001", "Definitions"),
            ("504B", "111", "Security Deposit"),
            ("504B", "115", "Return of Security Deposit"),
            ("504B", "161", "Covenants of Landlord"),
            ("504B", "171", "Tenant Remedies"),
            ("504B", "178", "Retaliatory Conduct"),
            ("504B", "181", "Attorney Fees"),
            ("504B", "195", "Residential Tenant Bill of Rights"),
            ("504B", "206", "Notice Requirements"),
            ("504B", "285", "Writ of Recovery"),
            ("504B", "321", "Eviction Actions"),
            ("504B", "345", "Expungement"),
            ("504B", "375", "Emergency Tenant Remedies"),
            ("504B", "381", "Bed Bug Infestation"),
            ("504B", "395", "Tenant Screening Reports"),
        ]
        
        results = []
        for chapter, section, description in key_statutes:
            statute = await self.get_mn_statute(chapter, section)
            statute["description"] = description
            results.append(statute)
            
            # Be extra polite to revisor.mn.gov
            await asyncio.sleep(0.5)
        
        return results


# =============================================================================
# Global Instance
# =============================================================================

_crawler: Optional[CrawlerService] = None


def get_crawler() -> CrawlerService:
    """Get or create crawler service instance."""
    global _crawler
    if _crawler is None:
        _crawler = CrawlerService()
    return _crawler


async def shutdown_crawler():
    """Shutdown crawler service."""
    global _crawler
    if _crawler:
        await _crawler.close()
        _crawler = None
