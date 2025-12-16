"""
Semptify 5.0 - Crawler API Router
Provides API endpoints for ethical web crawling of public data.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.crawler import (
    get_crawler,
    MN_SOURCES,
    SourceType,
)


router = APIRouter(prefix="/api/crawler", tags=["Crawler"])


# =============================================================================
# Response Models
# =============================================================================

class CrawlRequest(BaseModel):
    """Request to crawl a URL."""
    url: str
    use_cache: bool = True


class CrawlResponse(BaseModel):
    """Response from crawl operation."""
    url: str
    success: bool
    status_code: Optional[int] = None
    title: Optional[str] = None
    text_preview: Optional[str] = None
    links_count: int = 0
    cached: bool = False
    error: Optional[str] = None


class SearchRequest(BaseModel):
    """Request to search public data."""
    query: str
    sources: Optional[list[str]] = None  # Filter to specific sources
    limit: int = 20


class SearchResultResponse(BaseModel):
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str
    source_type: str
    relevance_score: float


class SearchResponse(BaseModel):
    """Response from search operation."""
    query: str
    total_results: int
    results: list[SearchResultResponse]


class SourceInfo(BaseModel):
    """Information about a data source."""
    id: str
    name: str
    base_url: str
    type: str
    description: str


class StatuteResponse(BaseModel):
    """Response for statute lookup."""
    chapter: str
    section: Optional[str] = None
    url: str
    title: Optional[str] = None
    text: Optional[str] = None
    cached: bool = False
    error: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sources")
async def list_sources() -> list[SourceInfo]:
    """
    List all available data sources.
    
    These are public government and legal aid websites that can be searched.
    """
    return [
        SourceInfo(
            id=source_id,
            name=source["name"],
            base_url=source["base_url"],
            type=source["type"].value,
            description=source["description"],
        )
        for source_id, source in MN_SOURCES.items()
    ]


@router.get("/sources/{source_id}")
async def get_source(source_id: str) -> SourceInfo:
    """Get details about a specific source."""
    if source_id not in MN_SOURCES:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source = MN_SOURCES[source_id]
    return SourceInfo(
        id=source_id,
        name=source["name"],
        base_url=source["base_url"],
        type=source["type"].value,
        description=source["description"],
    )


@router.post("/crawl")
async def crawl_url(request: CrawlRequest) -> CrawlResponse:
    """
    Crawl a single URL.
    
    The crawler will:
    - Check robots.txt compliance
    - Rate limit requests
    - Cache results for 24 hours
    
    Only URLs from allowed domains are permitted.
    """
    crawler = get_crawler()
    
    # Validate URL is from allowed domain
    allowed_domains = [source["base_url"] for source in MN_SOURCES.values()]
    url_allowed = any(request.url.startswith(domain) or domain in request.url for domain in allowed_domains)
    
    if not url_allowed:
        raise HTTPException(
            status_code=400,
            detail="URL not from allowed public data source. Use /api/crawler/sources to see allowed sources."
        )
    
    result = await crawler.crawl(request.url, use_cache=request.use_cache)
    
    return CrawlResponse(
        url=result.url,
        success=result.success,
        status_code=result.status_code,
        title=result.title,
        text_preview=result.text[:1000] if result.text else None,
        links_count=len(result.links),
        cached=result.cached,
        error=result.error,
    )


@router.get("/search")
async def search(
    query: str = Query(..., min_length=2, description="Search query"),
    source: Optional[str] = Query(None, description="Limit to specific source ID"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
) -> SearchResponse:
    """
    Search public data sources for tenant-relevant information.
    
    Searches Minnesota government websites, legal resources, and public records.
    """
    crawler = get_crawler()
    
    if source and source not in MN_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
    
    # Search all or specific source
    if source:
        source_info = MN_SOURCES[source]
        if "{query}" in source_info.get("search_url", ""):
            search_url = source_info["search_url"].format(query=query.replace(" ", "+"))
            result = await crawler.crawl(search_url)
            
            results = []
            if result.success:
                results.append(SearchResult(
                    title=result.title or f"Search: {query}",
                    url=result.url,
                    snippet=result.text[:500] if result.text else "",
                    source=source_info["name"],
                    source_type=source_info["type"],
                    relevance_score=0.8,
                ))
        else:
            results = []
    else:
        results = await crawler.search_all(query)
    
    return SearchResponse(
        query=query,
        total_results=len(results),
        results=[
            SearchResultResponse(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:500],
                source=r.source,
                source_type=r.source_type.value if isinstance(r.source_type, SourceType) else r.source_type,
                relevance_score=r.relevance_score,
            )
            for r in results[:limit]
        ],
    )


@router.get("/search/statutes")
async def search_statutes(
    query: str = Query(..., description="Statute number or keywords"),
) -> SearchResponse:
    """
    Search Minnesota Statutes.
    
    You can search by:
    - Chapter number (e.g., "504B")
    - Section (e.g., "504B.111")
    - Keywords (e.g., "security deposit")
    """
    crawler = get_crawler()
    results = await crawler.search_mn_statutes(query)
    
    return SearchResponse(
        query=query,
        total_results=len(results),
        results=[
            SearchResultResponse(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:500],
                source=r.source,
                source_type=r.source_type.value,
                relevance_score=r.relevance_score,
            )
            for r in results
        ],
    )


@router.get("/search/business")
async def search_business(
    name: str = Query(..., min_length=2, description="Business or company name"),
) -> SearchResponse:
    """
    Search Minnesota business registry.
    
    Useful for finding:
    - Property management companies
    - Landlord LLCs
    - Business registration status
    """
    crawler = get_crawler()
    results = await crawler.search_business(name)
    
    return SearchResponse(
        query=name,
        total_results=len(results),
        results=[
            SearchResultResponse(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:500],
                source=r.source,
                source_type=r.source_type.value,
                relevance_score=r.relevance_score,
            )
            for r in results
        ],
    )


@router.get("/search/property")
async def search_property(
    address: str = Query(..., description="Property address"),
    county: str = Query("hennepin", description="County name"),
) -> SearchResponse:
    """
    Search county property records.
    
    Supported counties:
    - Hennepin (Minneapolis)
    - Ramsey (St. Paul)
    - Dakota
    """
    crawler = get_crawler()
    results = await crawler.search_property(address, county)
    
    return SearchResponse(
        query=address,
        total_results=len(results),
        results=[
            SearchResultResponse(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:500],
                source=r.source,
                source_type=r.source_type.value,
                relevance_score=r.relevance_score,
            )
            for r in results
        ],
    )


@router.get("/search/legal-aid")
async def search_legal_aid(
    query: str = Query(..., description="Legal topic or question"),
) -> SearchResponse:
    """
    Search legal aid resources.
    
    Searches:
    - LawHelp Minnesota
    - HOME Line tenant resources
    """
    crawler = get_crawler()
    results = await crawler.search_legal_resources(query)
    
    return SearchResponse(
        query=query,
        total_results=len(results),
        results=[
            SearchResultResponse(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:500],
                source=r.source,
                source_type=r.source_type.value,
                relevance_score=r.relevance_score,
            )
            for r in results
        ],
    )


@router.get("/statute/{chapter}")
async def get_statute(
    chapter: str,
    section: Optional[str] = Query(None, description="Section number"),
) -> StatuteResponse:
    """
    Get a specific Minnesota statute.
    
    Examples:
    - /api/crawler/statute/504B → Chapter 504B (Landlord-Tenant)
    - /api/crawler/statute/504B?section=111 → Security Deposit statute
    """
    crawler = get_crawler()
    result = await crawler.get_mn_statute(chapter, section)
    
    return StatuteResponse(
        chapter=result.get("chapter", chapter),
        section=result.get("section"),
        url=result.get("url", ""),
        title=result.get("title"),
        text=result.get("text"),
        cached=result.get("cached", False),
        error=result.get("error"),
    )


@router.get("/tenant-rights-statutes")
async def get_tenant_rights_statutes() -> list[StatuteResponse]:
    """
    Get all key Minnesota tenant rights statutes.
    
    This is a convenience endpoint that returns the most important
    statutes for tenant defense, including:
    - Security deposits
    - Landlord obligations
    - Eviction procedures
    - Retaliatory conduct
    - Tenant remedies
    """
    crawler = get_crawler()
    results = await crawler.get_tenant_rights_statutes()
    
    return [
        StatuteResponse(
            chapter=r.get("chapter", ""),
            section=r.get("section"),
            url=r.get("url", ""),
            title=r.get("title"),
            text=r.get("text", "")[:2000] if r.get("text") else None,  # Limit response size
            cached=r.get("cached", False),
            error=r.get("error"),
        )
        for r in results
    ]


@router.get("/ethics")
async def get_ethics_policy() -> dict:
    """
    Get the crawler's ethics policy.
    
    Explains what data is crawled and how.
    """
    return {
        "policy": "Ethical Public Data Crawler",
        "version": "1.0",
        "principles": [
            "Only crawls PUBLIC government and legal aid data",
            "Respects robots.txt on all sites",
            "Rate limits to 1 request per second per domain",
            "Caches results to minimize server load",
            "Identifies itself with User-Agent header",
            "Never scrapes personal/private data",
            "Purpose: Tenant rights research and defense",
        ],
        "allowed_sources": list(MN_SOURCES.keys()),
        "user_agent": "Semptify/5.0 (Tenant Rights Research Bot; +https://semptify.org/bot)",
        "cache_ttl_hours": 24,
        "rate_limit_seconds": 1.0,
        "contact": "For questions about this crawler, contact Semptify support",
    }


@router.delete("/cache")
async def clear_cache() -> dict:
    """
    Clear the crawler cache.
    
    Use this if you need fresh data (e.g., statute was recently updated).
    """
    import shutil
    from pathlib import Path
    
    cache_dir = Path("data/crawler_cache")
    if cache_dir.exists():
        count = len(list(cache_dir.glob("*.json")))
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "cleared", "files_removed": count}
    
    return {"status": "cache_empty", "files_removed": 0}
