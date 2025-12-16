"""
Minnesota Eviction & Tenant Rights Document Crawler

Focused crawler for:
- Eviction defense documents  
- Tenant counterclaims against landlords
- Habitability complaints
- Security deposit disputes

For training Semptify's document processor (SEED/MCRO recognition).
"""

import asyncio
import httpx
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Optional, List, Dict
from bs4 import BeautifulSoup

# Output directories
BASE_DIR = Path("c:/Semptify/Semptify-FastAPI/data/eviction_training")
FORMS_DIR = BASE_DIR / "forms"
GUIDES_DIR = BASE_DIR / "guides"  
CASES_DIR = BASE_DIR / "cases"
METADATA_DIR = BASE_DIR / "metadata"

# ============================================================================
# EVICTION DEFENSE FORMS - These are what tenants file
# ============================================================================
EVICTION_DEFENSE_FORMS = {
    # Answer - Tenant's response to eviction
    "answer": {
        "name": "Answer to Eviction Complaint",
        "doc_type": "answer",
        "description": "Tenant's formal response denying landlord's claims",
    },
    # Motion to Dismiss - Attack the complaint
    "motion_dismiss": {
        "name": "Motion to Dismiss",
        "doc_type": "motion_to_dismiss", 
        "description": "Request court dismiss case due to defects",
    },
    # Counterclaim - Sue the landlord back
    "counterclaim": {
        "name": "Counterclaim Against Landlord",
        "doc_type": "counterclaim",
        "description": "Tenant sues landlord for damages within eviction case",
    },
    # Stay of Writ - Stop eviction execution
    "stay_writ": {
        "name": "Motion to Stay Writ of Recovery",
        "doc_type": "stay_of_writ",
        "description": "Request to delay eviction execution",
    },
    # Expungement - Seal the record
    "expungement": {
        "name": "Petition for Expungement",
        "doc_type": "expungement",
        "description": "Request to seal eviction from public record",
    },
}

# ============================================================================
# SUE THE LANDLORD FORMS - Tenant as plaintiff
# ============================================================================
TENANT_CLAIMS = {
    # Tenant Remedies Action
    "tenant_remedies": {
        "name": "Tenant Remedies Action",
        "doc_type": "tenant_remedies",
        "description": "Sue landlord for habitability violations, damages",
        "claims": ["habitability", "breach_warranty", "damages", "injunction"],
    },
    # Rent Escrow
    "rent_escrow": {
        "name": "Rent Escrow Action", 
        "doc_type": "rent_escrow",
        "description": "Deposit rent with court due to landlord violations",
    },
    # Security Deposit
    "security_deposit": {
        "name": "Security Deposit Claim",
        "doc_type": "security_deposit",
        "description": "Sue for wrongfully withheld security deposit",
        "damages": "Up to double deposit plus attorney fees",
    },
    # Retaliation
    "retaliation": {
        "name": "Retaliation Claim",
        "doc_type": "retaliation",
        "description": "Landlord retaliated for tenant exercising rights",
    },
    # Lockout/Utility Shutoff
    "illegal_lockout": {
        "name": "Illegal Lockout/Utility Shutoff Claim",
        "doc_type": "illegal_lockout", 
        "description": "Landlord illegally removed tenant without court order",
    },
}


class EvictionCrawler:
    """Crawler focused on eviction and tenant rights documents."""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.downloaded = 0
        self.errors = 0
        self.documents: List[Dict] = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/pdf",
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
        for dir_path in [FORMS_DIR, GUIDES_DIR, CASES_DIR, METADATA_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directories in {BASE_DIR}")

    async def crawl_mncourts_forms_page(self) -> int:
        """Crawl the mncourts.gov forms page for housing forms."""
        count = 0
        
        # Try the housing forms category page
        urls_to_try = [
            "https://mncourts.gov/GetForms.aspx?c=11",  # Housing category
            "https://mncourts.gov/GetForms.aspx?c=19",  # General forms
            "https://mncourts.gov/Help-Topics/Housing.aspx",
        ]
        
        for url in urls_to_try:
            print(f"\n🔍 Checking {url}...")
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    print(f"  ⚠ Status {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all links that might be forms
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link['href']
                    text = link.get_text(strip=True).lower()
                    
                    # Look for eviction/housing related links
                    if any(kw in text for kw in ['eviction', 'housing', 'tenant', 'landlord', 'answer', 'motion', 'counterclaim']):
                        print(f"  📄 Found: {link.get_text(strip=True)[:50]}...")
                        
                        # If it's a PDF link, download it
                        if '.pdf' in href.lower():
                            full_url = href if href.startswith('http') else f"https://mncourts.gov{href}"
                            if await self.download_document(full_url, FORMS_DIR, "form"):
                                count += 1
                                
                        # If it's a form download page, try to get the PDF
                        elif 'getforms' in href.lower() or 'f=' in href.lower():
                            full_url = href if href.startswith('http') else f"https://mncourts.gov{href}"
                            if await self.download_form_from_page(full_url):
                                count += 1
                                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.errors += 1
                
        return count

    async def download_form_from_page(self, url: str) -> bool:
        """Try to download a form from a GetForms.aspx page."""
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return False
                
            # Check if it redirected to a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type.lower():
                filename = url.split('=')[-1] + ".pdf"
                filepath = FORMS_DIR / filename
                filepath.write_bytes(response.content)
                print(f"    ✓ Downloaded {filename}")
                self.downloaded += 1
                return True
                
            # Otherwise parse the page for PDF link
            soup = BeautifulSoup(response.text, 'html.parser')
            pdf_links = soup.find_all('a', href=lambda h: h and '.pdf' in h.lower())
            
            for link in pdf_links[:1]:  # Just get first PDF
                pdf_url = link['href']
                if not pdf_url.startswith('http'):
                    pdf_url = f"https://mncourts.gov{pdf_url}"
                return await self.download_document(pdf_url, FORMS_DIR, "form")
                
        except Exception as e:
            print(f"    ✗ {e}")
            
        return False

    async def crawl_lawhelp_mn(self) -> int:
        """Crawl LawHelpMN for eviction guides and forms."""
        count = 0
        
        urls = [
            "https://www.lawhelpmn.org/self-help-library/fact-sheet/evictions-what-they-are",
            "https://www.lawhelpmn.org/self-help-library/booklet/tenants-rights-minnesota",
            "https://www.lawhelpmn.org/issues/housing",
        ]
        
        print("\n📚 Checking LawHelpMN resources...")
        
        for url in urls:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF links
                pdf_links = soup.find_all('a', href=lambda h: h and '.pdf' in h.lower())
                
                for link in pdf_links:
                    href = link['href']
                    full_url = href if href.startswith('http') else f"https://www.lawhelpmn.org{href}"
                    
                    text = link.get_text(strip=True)
                    if any(kw in text.lower() for kw in ['eviction', 'tenant', 'landlord', 'housing', 'answer', 'rights']):
                        if await self.download_document(full_url, GUIDES_DIR, "guide"):
                            count += 1
                            
            except Exception as e:
                print(f"  ✗ Error with {url}: {e}")
                
        return count

    async def crawl_homeline(self) -> int:
        """Crawl HOME Line tenant hotline resources."""
        count = 0
        
        urls = [
            "https://homelinemn.org/resources/",
            "https://homelinemn.org/tenant-rights/",
        ]
        
        print("\n🏠 Checking HOME Line resources...")
        
        for url in urls:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF/document links
                doc_links = soup.find_all('a', href=lambda h: h and ('.pdf' in h.lower() or 'document' in h.lower()))
                
                for link in doc_links:
                    href = link['href']
                    full_url = href if href.startswith('http') else f"https://homelinemn.org{href}"
                    
                    if await self.download_document(full_url, GUIDES_DIR, "guide"):
                        count += 1
                        
            except Exception as e:
                print(f"  ✗ Error with {url}: {e}")
                
        return count

    async def crawl_ag_handbook(self) -> int:
        """Crawl MN Attorney General Landlord-Tenant handbook."""
        count = 0
        
        print("\n⚖️ Checking MN Attorney General resources...")
        
        # AG Landlord/Tenant handbook
        ag_urls = [
            "https://www.ag.state.mn.us/consumer/handbooks/lt/lt.pdf",
            "https://www.ag.state.mn.us/consumer/handbooks/lt/default.asp",
        ]
        
        for url in ag_urls:
            try:
                response = await self.client.get(url)
                
                if 'pdf' in response.headers.get('content-type', '').lower():
                    filename = "MN_AG_Landlord_Tenant_Handbook.pdf"
                    filepath = GUIDES_DIR / filename
                    filepath.write_bytes(response.content)
                    print(f"  ✓ Downloaded {filename} ({len(response.content)} bytes)")
                    self.downloaded += 1
                    count += 1
                    
                    self.documents.append({
                        "filename": filename,
                        "url": url,
                        "doc_type": "handbook",
                        "source": "MN Attorney General",
                        "topic": "landlord_tenant_law",
                    })
                    break
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")
                
        return count

    async def download_document(self, url: str, output_dir: Path, doc_type: str) -> bool:
        """Download a document and save metadata."""
        try:
            response = await self.client.get(url)
            
            if response.status_code != 200:
                return False
                
            content_type = response.headers.get('content-type', '')
            
            # Generate filename
            filename = url.split('/')[-1].split('?')[0]
            if not filename or len(filename) < 3:
                filename = f"doc_{hash(url) % 10000}.pdf"
            
            # Clean filename
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            if not filename.endswith('.pdf') and 'pdf' in content_type.lower():
                filename += '.pdf'
                
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / filename
            
            if filepath.exists():
                print(f"  ⏭ {filename} (exists)")
                return False
                
            filepath.write_bytes(response.content)
            print(f"  ✓ {filename} ({len(response.content)} bytes)")
            
            self.downloaded += 1
            self.documents.append({
                "filename": filename,
                "url": url,
                "doc_type": doc_type,
                "size": len(response.content),
                "downloaded": datetime.now().isoformat(),
            })
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error downloading {url}: {e}")
            self.errors += 1
            return False

    async def create_sample_training_docs(self):
        """Create sample document templates for training."""
        
        print("\n📝 Creating sample training document templates...")
        
        samples_dir = BASE_DIR / "sample_templates"
        samples_dir.mkdir(parents=True, exist_ok=True)
        
        # Sample Answer document structure
        answer_template = """MINNESOTA DISTRICT COURT
{county} COUNTY                                    FIRST JUDICIAL DISTRICT

{plaintiff_name},                                  Case No.: {case_number}
                    Plaintiff,
        vs.                                        ANSWER TO COMPLAINT
                                                   FOR EVICTION
{defendant_name},
                    Defendant.

COMES NOW the Defendant, {defendant_name}, and for their Answer to Plaintiff's 
Complaint states as follows:

DENIALS

1. Defendant denies each and every allegation in Plaintiff's Complaint not 
   specifically admitted herein.

2. Defendant denies that Plaintiff is entitled to possession of the premises.

3. Defendant denies that rent is owed as alleged.

AFFIRMATIVE DEFENSES

1. IMPROPER SERVICE: The Summons and Complaint were not properly served as 
   required by Minnesota Statute § 504B.331.

2. HABITABILITY DEFENSE: Plaintiff failed to maintain the premises in 
   compliance with the implied warranty of habitability under Minnesota 
   Statute § 504B.161. Specifically:
   [List specific habitability issues]

3. RETALIATION: This eviction action is retaliatory in violation of 
   Minnesota Statute § 504B.285 because:
   [Describe protected activity and timing]

4. RENT PAYMENT: All rent due and owing has been paid.

COUNTERCLAIM

[See attached Counterclaim]

WHEREFORE, Defendant requests that this Court:
1. Dismiss Plaintiff's Complaint with prejudice;
2. Award Defendant damages on their Counterclaim;
3. Award attorney's fees and costs;
4. Grant such other relief as the Court deems just.

Dated: _______________

_______________________
{defendant_name}, Pro Se Defendant
{defendant_address}
{defendant_phone}
"""
        
        (samples_dir / "answer_template.txt").write_text(answer_template)
        
        # Sample Counterclaim
        counterclaim_template = """MINNESOTA DISTRICT COURT
{county} COUNTY                                    FIRST JUDICIAL DISTRICT

{plaintiff_name},                                  Case No.: {case_number}
                    Plaintiff,
        vs.                                        COUNTERCLAIM
                                                   
{defendant_name},
                    Defendant/Counterclaimant.

COUNTERCLAIM

Defendant/Counterclaimant {defendant_name} brings this Counterclaim against 
Plaintiff/Counterdefendant and states:

PARTIES AND JURISDICTION

1. Counterclaimant is a tenant at {property_address}.

2. Counterdefendant is the landlord of said property.

3. This Court has jurisdiction over this counterclaim pursuant to 
   Minnesota Statute § 504B.

FACTS

4. On or about {lease_date}, Counterclaimant entered into a lease agreement 
   with Counterdefendant for the premises.

5. Counterdefendant has breached the lease and violated Minnesota Statute 
   § 504B.161 by failing to:
   a. [Specific violation 1]
   b. [Specific violation 2]
   c. [Specific violation 3]

6. Counterclaimant notified Counterdefendant of these conditions on {notice_date}.

7. Counterdefendant failed to remedy the conditions within a reasonable time.

DAMAGES

8. As a result of Counterdefendant's breaches, Counterclaimant has suffered:
   a. Diminished value of tenancy: $_______
   b. Out-of-pocket expenses: $_______
   c. Emotional distress: $_______
   d. Other damages: $_______

CLAIMS FOR RELIEF

COUNT I: BREACH OF WARRANTY OF HABITABILITY
(Minnesota Statute § 504B.161)

COUNT II: BREACH OF LEASE

COUNT III: VIOLATION OF TENANT REMEDIES ACT
(Minnesota Statute § 504B.395)

WHEREFORE, Counterclaimant demands judgment against Counterdefendant for:
1. Compensatory damages in the amount of $_______;
2. Rent abatement;
3. Statutory penalties;
4. Attorney's fees and costs;
5. Injunctive relief requiring repairs;
6. Such other relief as is just and proper.

Dated: _______________

_______________________
{defendant_name}, Pro Se Counterclaimant
"""
        
        (samples_dir / "counterclaim_template.txt").write_text(counterclaim_template)
        
        # Sample Motion to Dismiss
        motion_dismiss_template = """MINNESOTA DISTRICT COURT
{county} COUNTY                                    FIRST JUDICIAL DISTRICT

{plaintiff_name},                                  Case No.: {case_number}
                    Plaintiff,
        vs.                                        MOTION TO DISMISS

{defendant_name},
                    Defendant.

MOTION TO DISMISS

Defendant {defendant_name} moves this Court for an Order dismissing 
Plaintiff's Complaint for the following reasons:

1. IMPROPER NOTICE

The eviction notice served on Defendant failed to comply with Minnesota 
Statute § 504B.321 because:
[ ] The notice period was insufficient
[ ] The notice was not properly served
[ ] The notice failed to state required information
[ ] Other: _______________

2. PROCEDURAL DEFECTS

The Complaint and/or service thereof is defective because:
[ ] Service was not made as required by Minn. Stat. § 504B.331
[ ] The Complaint fails to state a claim upon which relief can be granted
[ ] The wrong party is named as Plaintiff
[ ] The wrong party is named as Defendant
[ ] Other: _______________

3. SUBSTANTIVE DEFENSES

This eviction should be dismissed because:
[ ] All rent due has been paid
[ ] Plaintiff accepted rent after serving the notice
[ ] The eviction is retaliatory (Minn. Stat. § 504B.285)
[ ] Plaintiff failed to maintain habitability
[ ] Other: _______________

WHEREFORE, Defendant respectfully requests this Court dismiss Plaintiff's 
Complaint with prejudice.

Dated: _______________

_______________________
{defendant_name}, Pro Se Defendant
"""
        
        (samples_dir / "motion_dismiss_template.txt").write_text(motion_dismiss_template)
        
        print(f"  ✓ Created {len(list(samples_dir.glob('*.txt')))} sample templates")
        
        # Add to metadata
        for template_file in samples_dir.glob('*.txt'):
            self.documents.append({
                "filename": template_file.name,
                "doc_type": "template",
                "category": "training_sample",
                "path": str(template_file),
            })

    def save_metadata(self):
        """Save crawl metadata."""
        metadata_file = METADATA_DIR / f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        crawl_info = {
            "crawl_date": datetime.now().isoformat(),
            "focus": "eviction_defense_tenant_claims",
            "total_downloaded": self.downloaded,
            "total_errors": self.errors,
            "documents": self.documents,
            "document_types": list(EVICTION_DEFENSE_FORMS.keys()) + list(TENANT_CLAIMS.keys()),
        }
        
        metadata_file.write_text(json.dumps(crawl_info, indent=2))
        print(f"\n📊 Metadata saved to {metadata_file}")


async def main():
    """Run the eviction document crawler."""
    print("=" * 60)
    print("Minnesota Eviction & Tenant Rights Crawler")
    print("Focus: Eviction Defense + Sue the Landlord")
    print("=" * 60)
    
    async with EvictionCrawler() as crawler:
        crawler.setup_directories()
        
        # 1. Create sample training templates first
        await crawler.create_sample_training_docs()
        
        # 2. Crawl MN Courts forms
        forms_count = await crawler.crawl_mncourts_forms_page()
        print(f"\n✓ Downloaded {forms_count} court forms")
        
        # 3. Crawl MN AG handbook
        ag_count = await crawler.crawl_ag_handbook()
        print(f"✓ Downloaded {ag_count} AG resources")
        
        # 4. Crawl LawHelpMN
        lawhelp_count = await crawler.crawl_lawhelp_mn()
        print(f"✓ Downloaded {lawhelp_count} LawHelpMN resources")
        
        # 5. Crawl HOME Line
        homeline_count = await crawler.crawl_homeline()
        print(f"✓ Downloaded {homeline_count} HOME Line resources")
        
        # Save metadata
        crawler.save_metadata()
        
        print("\n" + "=" * 60)
        print("CRAWL COMPLETE")
        print(f"  Total downloaded: {crawler.downloaded}")
        print(f"  Training templates: 3")
        print(f"  Errors: {crawler.errors}")
        print(f"  Output: {BASE_DIR}")
        print("=" * 60)
        
        # Print what we have for training
        print("\n📋 TRAINING DATA COLLECTED:")
        print("-" * 40)
        for doc in crawler.documents[:20]:
            print(f"  • {doc.get('filename', 'N/A')} ({doc.get('doc_type', 'unknown')})")


if __name__ == "__main__":
    asyncio.run(main())
