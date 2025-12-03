"""Add sample eviction case documents for timeline testing."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Load existing index
index_file = Path(__file__).parent.parent / "data/documents/index.json"
with open(index_file, "r") as f:
    index = json.load(f)

# Sample documents for an eviction case timeline
sample_docs = [
    {
        "filename": "Lease_Agreement_2024.pdf",
        "doc_type": "lease",
        "full_text": """RESIDENTIAL LEASE AGREEMENT
        
This Lease Agreement is entered into on December 15, 2023.
Lease Term: January 1, 2024 through December 31, 2024.
Monthly Rent: $1,450.00 due on the 1st of each month.
Security Deposit: $1,450.00 paid on December 20, 2023.
Late Fee: $50.00 if rent not received by the 5th of the month.

LANDLORD: Lexington Flats, Limited Partnership
TENANT: Dena Sazama, Bradley Crowe

Move-in inspection scheduled for December 30, 2023.
""",
    },
    {
        "filename": "Notice_Late_Rent_July2025.pdf",
        "doc_type": "notice",
        "full_text": """NOTICE OF LATE RENT
        
Date: July 8, 2025

Dear Tenant,

This notice is to inform you that your July 2025 rent payment of $1,450.00 was due on July 1, 2025 and has not been received.

A late fee of $50.00 has been applied as of July 6, 2025.

Please remit payment by July 15, 2025 to avoid further action.

Lexington Flats Management
""",
    },
    {
        "filename": "Pay_or_Quit_Notice_Aug2025.pdf",
        "doc_type": "notice",
        "full_text": """14-DAY NOTICE TO PAY RENT OR QUIT

Date Served: August 10, 2025

TO: Dena Sazama, Bradley Crowe

You are hereby notified that you are in default of your rental agreement. 
The total amount due as of August 10, 2025 is $2,950.00.

You must pay the full amount by August 24, 2025 or vacate the premises.

If payment is not received by August 24, 2025, eviction proceedings will commence.

This notice expires on August 24, 2025.
""",
    },
    {
        "filename": "Tenant_Response_Letter.pdf",
        "doc_type": "communication",
        "full_text": """August 15, 2025

To: Lexington Flats Management

RE: Response to Pay or Quit Notice dated August 10, 2025

I am writing to dispute the notice received on August 12, 2025.

I made a partial payment of $1,000.00 on August 1, 2025 which was not credited to my account.

I am attaching proof of this payment dated August 1, 2025.

I request a meeting to discuss this matter by August 20, 2025.

Sincerely,
Bradley Crowe
""",
    },
    {
        "filename": "Notice_to_Vacate_Aug29.pdf",
        "doc_type": "notice",
        "full_text": """NOTICE TO VACATE

Date: August 29, 2025

TO: Dena Sazama, Bradley Crowe

This is your formal notice that your tenancy is terminated effective October 31, 2025.

You must vacate the premises located at 123 Lexington Ave, Eagan, MN 55121 
no later than October 31, 2025 at 11:59 PM.

Failure to vacate by this date will result in eviction proceedings.

A move-out inspection is scheduled for October 30, 2025 at 10:00 AM.

Lexington Flats, Limited Partnership
""",
    },
    {
        "filename": "Summons_and_Complaint.pdf",
        "doc_type": "court_filing",
        "full_text": """STATE OF MINNESOTA
COUNTY OF DAKOTA
DISTRICT COURT - FIRST JUDICIAL DISTRICT
Case No: 19AV-CV-25-3477

SUMMONS

Filed: November 17, 2025

Plaintiff: Lexington Flats, Limited Partnership
vs.
Defendants: Dena Sazama, Bradley Crowe

YOU ARE HEREBY SUMMONED to appear before the Court for a hearing on December 15, 2025 at 9:00 AM.

Answer must be filed by December 1, 2025.

The hearing will be held at Dakota County Courthouse, 1560 Highway 55, Hastings, MN.
""",
    },
    {
        "filename": "Answer_to_Complaint.pdf",
        "doc_type": "court_filing",
        "full_text": """STATE OF MINNESOTA
COUNTY OF DAKOTA
DISTRICT COURT
Case No: 19AV-CV-25-3477

ANSWER TO COMPLAINT

Filed: November 25, 2025

Defendants Dena Sazama and Bradley Crowe hereby answer the Complaint as follows:

1. Defendants deny all allegations of non-payment.
2. Defendants made partial payments on August 1, 2025 and September 15, 2025.
3. Defendants request a jury trial scheduled after January 15, 2026.

A pre-trial conference is requested for December 10, 2025.

Submitted by: Bradley Crowe, Pro Se
Date: November 25, 2025
""",
    },
    {
        "filename": "Motion_to_Stay_Eviction.pdf",
        "doc_type": "court_filing",
        "full_text": """STATE OF MINNESOTA
COUNTY OF DAKOTA
DISTRICT COURT
Case No: 19AV-CV-25-3477

MOTION TO STAY EVICTION

Filed: December 1, 2025

Defendants move the Court to stay the eviction pending resolution of the following:

1. Disputed payment records from August 1, 2025 and September 15, 2025.
2. Alleged habitability issues reported on June 15, 2025 and July 20, 2025.

Defendants request a hearing on this motion by December 8, 2025.

This motion must be ruled on before the scheduled hearing on December 15, 2025.

Submitted by: Bradley Crowe
Date: December 1, 2025
""",
    },
]

# Add each sample document to the index
user_id = "open-mode-user"
added = 0
for doc_data in sample_docs:
    doc_id = str(uuid.uuid4())
    storage_path = f"data/documents/{user_id}/{doc_id}_{doc_data['filename']}"
    
    index[doc_id] = {
        "id": doc_id,
        "user_id": user_id,
        "filename": doc_data["filename"],
        "file_hash": f"sample_{doc_id[:8]}",
        "mime_type": "application/pdf",
        "file_size": len(doc_data["full_text"]),
        "storage_path": storage_path,
        "status": "classified",
        "doc_type": doc_data["doc_type"],
        "confidence": 0.9,
        "title": doc_data["filename"].replace(".pdf", "").replace("_", " "),
        "summary": "Sample document for timeline testing",
        "full_text": doc_data["full_text"],
        "key_dates": [],
        "key_parties": [],
        "key_amounts": [],
        "key_terms": [],
        "law_references": None,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
    added += 1
    print(f"  + {doc_data['filename']}")

# Save updated index
with open(index_file, "w") as f:
    json.dump(index, f, indent=2)

print(f"\n✅ Added {added} sample documents to index")
print(f"📊 Total documents: {len(index)}")
