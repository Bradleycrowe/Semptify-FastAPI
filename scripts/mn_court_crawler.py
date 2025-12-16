"""
Minnesota Eviction & Tenant Rights Document Crawler

Crawls publicly available court case documents focused on:
- Eviction defense documents
- Tenant counterclaims against landlords
- Habitability complaints
- Rent escrow actions
- Lease violation defenses

For training Semptify's document processor (SEED/MCRO recognition).

IMPORTANT: This only accesses PUBLIC records and forms.
"""

import asyncio
import httpx
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import hashlib

# Output directories
BASE_DIR = Path("c:/Semptify/Semptify-FastAPI/data/court_cases")
EVICTION_DIR = BASE_DIR / "eviction"
TENANT_CLAIMS_DIR = BASE_DIR / "tenant_claims"
FORMS_DIR = BASE_DIR / "forms"
METADATA_DIR = BASE_DIR / "metadata"

# Minnesota court forms - UPDATED URLS (mncourts changed their structure)
# Using GetForms.aspx with form IDs
EVICTION_FORMS = {
    # Eviction Defense Forms (Tenant responding)
    "HOU301_Answer": "https://mncourts.gov/GetForms.aspx?c=11&f=352",
    "HOU302_Motion_Dismiss": "https://mncourts.gov/GetForms.aspx?c=11&f=353",
    "HOU303_Counterclaim": "https://mncourts.gov/GetForms.aspx?c=11&f=354",
    "HOU304_Expungement": "https://mncourts.gov/GetForms.aspx?c=11&f=355",
    "HOU305_Continuance": "https://mncourts.gov/GetForms.aspx?c=11&f=356",
    "HOU306_Stay_Writ": "https://mncourts.gov/GetForms.aspx?c=11&f=357",
    
    # Sue the Landlord / Tenant Claims
    "HOU308_Habitability": "https://mncourts.gov/GetForms.aspx?c=11&f=359",
    "HOU309_Rent_Escrow": "https://mncourts.gov/GetForms.aspx?c=11&f=360",
    "HOU310_Tenant_Remedies": "https://mncourts.gov/GetForms.aspx?c=11&f=361",
    
    # General Forms needed
    "IFP_Fee_Waiver": "https://mncourts.gov/GetForms.aspx?c=19&f=466",
    "Affidavit_Service": "https://mncourts.gov/GetForms.aspx?c=19&f=443",
    "Subpoena": "https://mncourts.gov/GetForms.aspx?c=19&f=450",
}

# Tenant rights resources with sample legal documents
TENANT_RESOURCES = [
    # HOME Line (MN tenant rights org)
    "https://homelinemn.org/wp-content/uploads/Eviction-Answer-Form-Guide.pdf",
    "https://homelinemn.org/wp-content/uploads/Tenant-Remedies-Action-Guide.pdf",
    
    # Legal Aid resources
    "https://www.mylegalaid.org/documents/eviction-answer-guide",
    
    # MN AG tenant rights
    "https://www.ag.state.mn.us/consumer/handbooks/lt/default.asp",
]

# Case types for eviction/landlord-tenant
EVICTION_DOCUMENT_TYPES = [
    "eviction_complaint",      # Landlord files to evict
    "answer",                   # Tenant response
    "motion_to_dismiss",        # Tenant defense
    "counterclaim",             # Tenant sues landlord back
    "habitability_complaint",   # Tenant claims unfit conditions
    "rent_escrow",              # Tenant deposits rent with court
    "tenant_remedies",          # Tenant sues for damages
    "repair_deduct",            # Tenant made repairs, deducted from rent
    "retaliation_claim",        # Landlord retaliated against tenant
    "security_deposit",         # Landlord wrongfully kept deposit
    "lease_violation",          # Either party claims violation
    "stay_of_writ",             # Stop eviction execution
    "expungement",              # Seal eviction record
]


class MNCourtCrawler:
    """Crawler for Minnesota court documents."""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.downloaded = 0
        self.errors = 0
        self.metadata: List[Dict] = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Semptify Legal Research Bot/1.0 (Educational/Training)",
                "Accept": "text/html,application/pdf,application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        return self
        
    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
    
    def setup_directories(self):
        """Create output directories."""
        for dir_path in [OPINIONS_DIR, ORDERS_DIR, FILINGS_DIR, METADATA_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directories in {BASE_DIR}")
    
    async def crawl_mn_opinions(self, year: int = 2024) -> int:
        """Crawl Minnesota Supreme Court and Appeals Court opinions."""
        count = 0
        
        # MN Law Library archive has opinions by year
        base_urls = [
            f"https://mn.gov/law-library/archive/supct/{year}/",
            f"https://mn.gov/law-library/archive/ctapun/{year}/",
        ]
        
        for base_url in base_urls:
            court_type = "supreme" if "supct" in base_url else "appeals"
            print(f"\n📜 Crawling {court_type.title()} Court opinions for {year}...")
            
            try:
                response = await self.client.get(base_url)
                if response.status_code != 200:
                    print(f"  ⚠ Could not access {base_url} ({response.status_code})")
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all opinion links (typically .pdf or .htm)
                links = soup.find_all('a', href=True)
                opinion_links = [
                    link['href'] for link in links 
                    if link['href'].endswith(('.pdf', '.htm', '.html'))
                    and not link['href'].startswith('#')
                ]
                
                print(f"  Found {len(opinion_links)} potential documents")
                
                for href in opinion_links[:50]:  # Limit per source
                    full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href}"
                    downloaded = await self.download_document(
                        full_url, 
                        OPINIONS_DIR,
                        doc_type="opinion",
                        court=court_type,
                        year=year
                    )
                    if downloaded:
                        count += 1
                        
            except Exception as e:
                print(f"  ✗ Error crawling {base_url}: {e}")
                self.errors += 1
                
        return count
    
    async def crawl_recent_opinions(self) -> int:
        """Crawl recent opinions from mncourts.gov."""
        count = 0
        
        urls = [
            ("https://mncourts.gov/SupremeCourt/Opinions.aspx", "supreme"),
            ("https://mncourts.gov/CourtofAppeals/Opinions.aspx", "appeals"),
        ]
        
        for url, court_type in urls:
            print(f"\n📋 Checking recent {court_type} opinions...")
            
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF links in the opinions table
                pdf_links = soup.find_all('a', href=lambda h: h and '.pdf' in h.lower())
                
                print(f"  Found {len(pdf_links)} PDF links")
                
                for link in pdf_links[:25]:
                    href = link['href']
                    full_url = href if href.startswith('http') else f"https://mncourts.gov{href}"
                    
                    downloaded = await self.download_document(
                        full_url,
                        OPINIONS_DIR,
                        doc_type="opinion",
                        court=court_type,
                        year=datetime.now().year
                    )
                    if downloaded:
                        count += 1
                        
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.errors += 1
                
        return count
    
    async def crawl_sample_forms(self) -> int:
        """Download Minnesota court form samples for training."""
        count = 0
        
        # Minnesota court forms - various categories
        form_categories = {
            "housing": [
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU101.pdf",  # Complaint
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU102.pdf",  # Summons
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU301.pdf",  # Answer
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU302.pdf",  # Motion to Dismiss
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU303.pdf",  # Counterclaim
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU304.pdf",  # Expungement
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU305.pdf",  # Continuance
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU306.pdf",  # Stay of Writ
            ],
            "civil": [
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Civil/CIV301.pdf",  # Answer
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Civil/CIV302.pdf",  # Counterclaim
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Civil/CIV801.pdf",  # Motion
            ],
            "general": [
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/General/AffidavitOfService.pdf",
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/General/IFP.pdf",  # In Forma Pauperis
                "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/General/GEN103.pdf",  # Subpoena
            ],
        }
        
        print("\n📝 Downloading court form samples...")
        
        for category, urls in form_categories.items():
            print(f"\n  Category: {category}")
            for url in urls:
                downloaded = await self.download_document(
                    url,
                    FILINGS_DIR / category,
                    doc_type="form",
                    court="district",
                    category=category
                )
                if downloaded:
                    count += 1
                    
        return count
    
    async def download_document(
        self, 
        url: str, 
        output_dir: Path,
        doc_type: str = "unknown",
        **metadata
    ) -> bool:
        """Download a single document and save metadata."""
        
        # Generate filename from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = url.split('/')[-1]
        if not filename or len(filename) > 100:
            filename = f"doc_{url_hash}.pdf"
        
        # Clean filename
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        
        # Skip if already downloaded
        if filepath.exists():
            print(f"    ⏭ {filename} (exists)")
            return False
            
        try:
            response = await self.client.get(url)
            
            if response.status_code != 200:
                print(f"    ✗ {filename} ({response.status_code})")
                return False
                
            # Check content type
            content_type = response.headers.get('content-type', '')
            
            if 'pdf' in content_type.lower() or filename.endswith('.pdf'):
                # Save PDF
                filepath.write_bytes(response.content)
                print(f"    ✓ {filename} ({len(response.content)} bytes)")
                
            elif 'html' in content_type.lower():
                # Save HTML
                if not filename.endswith(('.htm', '.html')):
                    filename = filename.replace('.pdf', '.html')
                filepath = output_dir / filename
                filepath.write_text(response.text, encoding='utf-8')
                print(f"    ✓ {filename} (HTML)")
                
            else:
                # Save as-is
                filepath.write_bytes(response.content)
                print(f"    ✓ {filename}")
            
            # Save metadata
            doc_metadata = {
                "filename": filename,
                "url": url,
                "doc_type": doc_type,
                "downloaded_at": datetime.now().isoformat(),
                "size_bytes": len(response.content),
                "content_type": content_type,
                **metadata
            }
            self.metadata.append(doc_metadata)
            self.downloaded += 1
            
            return True
            
        except Exception as e:
            print(f"    ✗ {filename}: {e}")
            self.errors += 1
            return False
    
    def save_metadata(self):
        """Save crawl metadata to JSON."""
        metadata_file = METADATA_DIR / f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        crawl_info = {
            "crawl_date": datetime.now().isoformat(),
            "total_downloaded": self.downloaded,
            "total_errors": self.errors,
            "documents": self.metadata
        }
        
        metadata_file.write_text(json.dumps(crawl_info, indent=2), encoding='utf-8')
        print(f"\n📊 Metadata saved to {metadata_file}")
        
        # Also save a consolidated index
        index_file = METADATA_DIR / "document_index.json"
        if index_file.exists():
            existing = json.loads(index_file.read_text(encoding='utf-8'))
        else:
            existing = {"documents": []}
            
        existing["documents"].extend(self.metadata)
        existing["last_updated"] = datetime.now().isoformat()
        existing["total_documents"] = len(existing["documents"])
        
        index_file.write_text(json.dumps(existing, indent=2), encoding='utf-8')


async def main():
    """Run the crawler."""
    print("=" * 60)
    print("Minnesota Court Document Crawler")
    print("Training data collection for Semptify SEED/MCRO")
    print("=" * 60)
    
    async with MNCourtCrawler() as crawler:
        crawler.setup_directories()
        
        # 1. Download court form samples (highest priority for training)
        forms_count = await crawler.crawl_sample_forms()
        print(f"\n✓ Downloaded {forms_count} court forms")
        
        # 2. Crawl recent opinions
        recent_count = await crawler.crawl_recent_opinions()
        print(f"✓ Downloaded {recent_count} recent opinions")
        
        # 3. Crawl archived opinions (2024, 2023)
        for year in [2024, 2023]:
            archive_count = await crawler.crawl_mn_opinions(year)
            print(f"✓ Downloaded {archive_count} opinions from {year}")
        
        # Save metadata
        crawler.save_metadata()
        
        print("\n" + "=" * 60)
        print(f"CRAWL COMPLETE")
        print(f"  Total downloaded: {crawler.downloaded}")
        print(f"  Errors: {crawler.errors}")
        print(f"  Output: {BASE_DIR}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
