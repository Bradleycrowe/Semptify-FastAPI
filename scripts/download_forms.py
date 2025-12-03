"""
Download Minnesota Court forms for offline use.
These are public domain court forms from mncourts.gov.
"""

import asyncio
import httpx
from pathlib import Path
import json

FORMS_DIR = Path("c:/Semptify/Semptify-FastAPI/semptify_dakota_eviction/app/assets/forms")
FORMS_JSON = Path("c:/Semptify/Semptify-FastAPI/semptify_dakota_eviction/app/assets/forms.json")

# Direct download URLs for Minnesota Court housing forms
# These are the actual PDF download links
FORM_URLS = {
    "HOU301_Answer.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU301.pdf",
    "HOU302_Motion_Dismiss.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU302.pdf",
    "HOU303_Counterclaim.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU303.pdf",
    "HOU304_Expungement.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU304.pdf",
    "HOU305_Continuance.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU305.pdf",
    "HOU306_Stay_Writ.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU306.pdf",
    "HOU307_IFP.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/General/IFP.pdf",
    "HOU308_Habitability.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU308.pdf",
    "HOU309_Rent_Escrow.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/Housing/HOU309.pdf",
    "HOU310_Service.pdf": "https://www.mncourts.gov/mncourtsgov/media/scao_library/forms/General/AffidavitOfService.pdf",
}

# Alternative URLs if the above don't work
ALT_FORM_URLS = {
    "HOU301_Answer.pdf": "https://mncourts.gov/GetForms.aspx?c=11&f=352",
    "HOU302_Motion_Dismiss.pdf": "https://mncourts.gov/GetForms.aspx?c=11&f=353",
    "HOU303_Counterclaim.pdf": "https://mncourts.gov/GetForms.aspx?c=11&f=354",
}


async def download_form(client: httpx.AsyncClient, filename: str, url: str) -> bool:
    """Download a single form."""
    filepath = FORMS_DIR / filename
    
    if filepath.exists():
        print(f"  ✓ {filename} (already exists)")
        return True
    
    try:
        print(f"  ⬇ Downloading {filename}...")
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        
        if response.status_code == 200:
            # Check if it's actually a PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type or response.content[:4] == b'%PDF':
                filepath.write_bytes(response.content)
                print(f"  ✅ {filename} ({len(response.content) // 1024} KB)")
                return True
            else:
                print(f"  ⚠️ {filename} - not a PDF (got {content_type})")
                return False
        else:
            print(f"  ❌ {filename} - HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ {filename} - Error: {e}")
        return False


async def main():
    """Download all forms."""
    print("📥 Downloading Minnesota Court Forms")
    print("=" * 50)
    
    # Create forms directory
    FORMS_DIR.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = 0
    
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    ) as client:
        for filename, url in FORM_URLS.items():
            if await download_form(client, filename, url):
                success += 1
            else:
                failed += 1
    
    print("=" * 50)
    print(f"✅ Downloaded: {success}")
    print(f"❌ Failed: {failed}")
    
    # List what's in the forms folder
    print("\n📁 Forms folder contents:")
    for f in FORMS_DIR.iterdir():
        size = f.stat().st_size // 1024 if f.is_file() else 0
        print(f"   {f.name} ({size} KB)")


if __name__ == "__main__":
    asyncio.run(main())
