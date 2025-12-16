"""
Bradley's Case Timeline Builder - 19AV-CV-25-3477

Extracts dates from documents and builds chronological timeline
for retaliation case against Velair Property Management.
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import json

# Your documents folder
DOCS_FOLDER = Path("C:/Semptify/Semptify-FastAPI/data/intake/SUmj5gygs2ktuxr")
OUTPUT_FILE = Path("C:/Semptify/Semptify-FastAPI/data/case_outputs/timeline_19AV-CV-25-3477.json")
TIMELINE_TXT = Path("C:/Semptify/Semptify-FastAPI/data/case_outputs/timeline_19AV-CV-25-3477.txt")

# Known date patterns in MCRO filenames
# Format: MCRO_CaseNum_DocType_YYYY-MM-DD_timestamp.pdf
MCRO_DATE_PATTERN = r'(\d{4}-\d{2}-\d{2})'

def extract_date_from_filename(filename: str) -> Tuple[str, str]:
    """Extract date and document type from filename."""
    # MCRO format: MCRO_19AV-CV-25-3477_DocType_2025-11-17_timestamp.pdf
    if 'MCRO' in filename:
        parts = filename.split('_')
        if len(parts) >= 4:
            doc_type = parts[2] if len(parts) > 2 else "Unknown"
            dates = re.findall(MCRO_DATE_PATTERN, filename)
            if dates:
                return dates[0], doc_type.replace('-', ' ')
    
    # Other files - look for dates in name
    dates = re.findall(MCRO_DATE_PATTERN, filename)
    if dates:
        return dates[0], filename.split('_')[1] if '_' in filename else filename
    
    return None, filename

def categorize_document(filename: str) -> Dict:
    """Categorize document by type and relevance."""
    filename_lower = filename.lower()
    
    categories = {
        "court_filing": ["complaint", "summons", "answer", "motion", "order", "affidavit", "memorandum", "certificate"],
        "retaliation_evidence": ["retaliation", "cease", "desist", "harassment", "rationale", "non-renewal", "violation"],
        "lease_rental": ["lease", "ledger", "rent", "payment"],
        "communication": ["gmail", "email", "letter", "notice"],
        "property_info": ["rentcafe", "apartment", "flats"],
        "support": ["homeline", "legal"],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in filename_lower:
                return {"category": category, "keyword": keyword}
    
    return {"category": "other", "keyword": None}


def build_timeline():
    """Build timeline from all documents."""
    
    timeline_events = []
    documents_by_date = {}
    
    print("=" * 60)
    print("CASE TIMELINE BUILDER - 19AV-CV-25-3477")
    print("Crowe vs Velair Property Management")
    print("=" * 60)
    
    # Process all documents
    for doc_file in DOCS_FOLDER.iterdir():
        filename = doc_file.name
        date_str, doc_type = extract_date_from_filename(filename)
        category_info = categorize_document(filename)
        
        event = {
            "filename": filename,
            "document_type": doc_type,
            "date": date_str,
            "category": category_info["category"],
            "path": str(doc_file),
        }
        
        # Add significance notes for key documents
        if "retaliation" in filename.lower() or "cease" in filename.lower():
            event["significance"] = "🔴 KEY EVIDENCE - Retaliation documentation"
        elif "complaint" in doc_type.lower():
            event["significance"] = "⚖️ Landlord's complaint against you"
        elif "answer" in doc_type.lower():
            event["significance"] = "✅ Your response filed"
        elif "motion" in doc_type.lower():
            event["significance"] = "📋 Motion filed"
        elif "homeline" in filename.lower():
            event["significance"] = "📞 Tenant rights assistance contact"
        
        timeline_events.append(event)
        
        if date_str:
            if date_str not in documents_by_date:
                documents_by_date[date_str] = []
            documents_by_date[date_str].append(event)
    
    # Sort by date
    sorted_dates = sorted([d for d in documents_by_date.keys() if d], reverse=False)
    
    # Print timeline
    print("\n📅 CHRONOLOGICAL TIMELINE")
    print("-" * 60)
    
    for date_str in sorted_dates:
        print(f"\n🗓️  {date_str}")
        for doc in documents_by_date[date_str]:
            sig = doc.get("significance", "")
            print(f"   • {doc['document_type']}")
            if sig:
                print(f"     {sig}")
    
    # Documents without dates
    no_date_docs = [e for e in timeline_events if not e["date"]]
    if no_date_docs:
        print(f"\n📎 SUPPORTING DOCUMENTS (date pending extraction)")
        print("-" * 60)
        for doc in no_date_docs:
            cat = doc["category"].replace("_", " ").title()
            print(f"   [{cat}] {doc['filename'][:60]}...")
    
    # Categorized summary
    print("\n\n📊 DOCUMENTS BY CATEGORY")
    print("-" * 60)
    
    categories_count = {}
    for event in timeline_events:
        cat = event["category"]
        if cat not in categories_count:
            categories_count[cat] = []
        categories_count[cat].append(event["filename"])
    
    for cat, docs in categories_count.items():
        print(f"\n{cat.replace('_', ' ').upper()} ({len(docs)} documents):")
        for doc in docs[:5]:
            print(f"   • {doc[:55]}...")
        if len(docs) > 5:
            print(f"   ... and {len(docs) - 5} more")
    
    # Save outputs
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        "case_number": "19AV-CV-25-3477",
        "case_type": "Eviction Defense - Retaliation",
        "plaintiff": "Velair Property Management",
        "defendant": "Bradley Crowe",
        "property": "Lexington Flats, Eagan MN",
        "hearing_date": "2025-12-23",
        "generated": datetime.now().isoformat(),
        "timeline_by_date": {d: [{"type": e["document_type"], "file": e["filename"]} for e in documents_by_date[d]] for d in sorted_dates},
        "documents_by_category": categories_count,
        "total_documents": len(timeline_events),
        "key_evidence": [e for e in timeline_events if "significance" in e],
    }
    
    OUTPUT_FILE.write_text(json.dumps(output_data, indent=2))
    print(f"\n✅ Timeline JSON saved: {OUTPUT_FILE}")
    
    # Create readable timeline
    timeline_text = f"""
================================================================================
CASE TIMELINE - 19AV-CV-25-3477
Bradley Crowe vs. Velair Property Management / Lexington Flats
RETALIATION DEFENSE
================================================================================

COURT DATE: December 23, 2025
PROPERTY: Lexington Flats, Eagan MN
TENANCY: ~5 years (starting 5th year)
RENT STATUS: Always paid on time
VIOLATIONS: NONE
COMPLAINTS: NONE

================================================================================
CHRONOLOGICAL TIMELINE
================================================================================
"""
    
    for date_str in sorted_dates:
        timeline_text += f"\n{date_str}\n" + "-" * 40 + "\n"
        for doc in documents_by_date[date_str]:
            sig = doc.get("significance", "")
            timeline_text += f"  • {doc['document_type']}\n"
            if sig:
                timeline_text += f"    {sig}\n"
    
    timeline_text += """
================================================================================
RETALIATION CLAIM ELEMENTS (Minnesota Statute § 504B.285)
================================================================================

1. PROTECTED ACTIVITY: (What you did that landlord retaliated against)
   [ ] Complained about property conditions
   [ ] Reported violations to city/authorities
   [ ] Joined or organized tenant group
   [ ] Exercised legal rights under lease
   [ ] Contacted tenant rights organization (HOME Line)
   [ ] Other: _______________________

2. ADVERSE ACTION: (What landlord did in response)
   [X] Filed eviction
   [ ] Raised rent
   [ ] Reduced services
   [ ] Harassment
   [ ] Refused to renew lease
   [ ] Other: _______________________

3. TIMING: (Proximity of adverse action to protected activity)
   - Protected activity date: _______
   - Eviction filed: November 17, 2025
   - Days between: _______
   
   NOTE: Under MN law, if adverse action within 90 days of protected 
   activity, there is a PRESUMPTION of retaliation that landlord must rebut.

================================================================================
COUNTERCLAIM OPTIONS
================================================================================

Consider filing counterclaims for:
[ ] Retaliation damages (Minn. Stat. § 504B.285)
[ ] Harassment
[ ] Breach of quiet enjoyment
[ ] Attorney fees if you prevail

DEADLINE: File BEFORE or AT hearing on December 23, 2025

================================================================================
"""
    
    TIMELINE_TXT.write_text(timeline_text)
    print(f"✅ Timeline text saved: {TIMELINE_TXT}")
    
    return output_data


if __name__ == "__main__":
    build_timeline()
