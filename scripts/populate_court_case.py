"""
Populate a realistic eviction case for court presentation.
Run this to set up a complete case with documents, timeline, and defenses.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.models import Base, Document, TimelineEvent, CalendarEvent
import uuid
import hashlib

DATABASE_URL = "sqlite+aiosqlite:///data/semptify.db"

# Realistic eviction case timeline
CASE_DATA = {
    "tenant_name": "Demo Tenant",
    "landlord_name": "ABC Property Management",
    "property_address": "1234 Main Street, Apt 5B, Minneapolis, MN 55401",
    "monthly_rent": 1450.00,
    "lease_start": "2023-06-01",
    "case_number": "27-CV-HC-24-5847",
}

TIMELINE_EVENTS = [
    {
        "event_type": "lease",
        "title": "Lease Signed",
        "description": f"12-month lease signed with {CASE_DATA['landlord_name']} for {CASE_DATA['property_address']}. Monthly rent: ${CASE_DATA['monthly_rent']}",
        "event_date": "2023-06-01",
        "is_evidence": True,
    },
    {
        "event_type": "maintenance",
        "title": "Maintenance Request - HVAC Not Working",
        "description": "Submitted written maintenance request for broken heating system. Temperature in unit dropping below 60°F. No response from landlord.",
        "event_date": "2024-10-15",
        "is_evidence": True,
    },
    {
        "event_type": "maintenance",
        "title": "Follow-up Maintenance Request",
        "description": "Second written request for HVAC repair. Included photos of thermostat showing 55°F. Sent via email and certified mail.",
        "event_date": "2024-10-22",
        "is_evidence": True,
    },
    {
        "event_type": "communication",
        "title": "Landlord Response - Denied Repair",
        "description": "Landlord responded claiming HVAC is 'working fine' despite documented evidence. Refused to send technician.",
        "event_date": "2024-10-25",
        "is_evidence": True,
    },
    {
        "event_type": "payment",
        "title": "November Rent Paid - With Deduction",
        "description": "Paid rent minus $200 for portable heater purchase. Sent letter explaining rent deduction under MN Stat 504B.385 (tenant remedies).",
        "event_date": "2024-11-01",
        "is_evidence": True,
    },
    {
        "event_type": "notice",
        "title": "14-Day Notice to Pay or Quit",
        "description": "Received 14-day notice claiming $200 unpaid rent. Notice did NOT include required statutory language about tenant rights.",
        "event_date": "2024-11-05",
        "is_evidence": True,
    },
    {
        "event_type": "communication",
        "title": "Response to Notice - Disputed Amount",
        "description": "Sent written response disputing notice. Explained rent deduction was lawful under habitability statute. Requested meeting to resolve.",
        "event_date": "2024-11-08",
        "is_evidence": True,
    },
    {
        "event_type": "court",
        "title": "Eviction Summons Filed",
        "description": f"Landlord filed eviction complaint. Case number: {CASE_DATA['case_number']}. Claiming non-payment of $200.",
        "event_date": "2024-11-15",
        "is_evidence": True,
    },
    {
        "event_type": "court",
        "title": "Summons Received",
        "description": "Received summons and complaint via personal service. 7-day deadline to appear and answer.",
        "event_date": "2024-11-18",
        "is_evidence": True,
    },
    {
        "event_type": "court",
        "title": "Answer Filed",
        "description": "Filed Answer with affirmative defenses: (1) Improper notice - missing required language, (2) Habitability defense - rent deduction was lawful, (3) Retaliation - eviction filed within 90 days of maintenance complaints.",
        "event_date": "2024-11-22",
        "is_evidence": True,
    },
    {
        "event_type": "court",
        "title": "Court Hearing Scheduled",
        "description": f"Initial hearing scheduled. Judge: Hon. Sarah Mitchell. Courtroom 1856, Hennepin County Government Center.",
        "event_date": "2024-12-02",
        "is_evidence": False,
    },
]

CALENDAR_EVENTS = [
    {
        "title": "🏛️ EVICTION HEARING",
        "description": f"Case: {CASE_DATA['case_number']}\nCourtroom 1856\nHennepin County Government Center\n300 S 6th St, Minneapolis\n\nBring: All evidence, timeline printout, ID",
        "event_date": "2024-12-02",
        "event_time": "09:00",
        "event_type": "court",
        "reminder_sent": False,
    },
    {
        "title": "Prepare Court Documents",
        "description": "Print timeline, organize evidence binder, prepare opening statement",
        "event_date": "2024-12-01",
        "event_time": "18:00",
        "event_type": "deadline",
        "reminder_sent": False,
    },
]

DOCUMENTS = [
    {
        "filename": "lease_agreement.pdf",
        "document_type": "lease",
        "description": "Original lease agreement signed June 2023",
        "extracted_text": f"""RESIDENTIAL LEASE AGREEMENT

PARTIES: This lease is between {CASE_DATA['landlord_name']} ("Landlord") and {CASE_DATA['tenant_name']} ("Tenant").

PROPERTY: {CASE_DATA['property_address']}

TERM: 12 months beginning June 1, 2023

RENT: ${CASE_DATA['monthly_rent']}/month, due on the 1st

LANDLORD OBLIGATIONS:
- Maintain premises in habitable condition
- Comply with housing codes
- Make necessary repairs within reasonable time

TENANT RIGHTS:
- Right to habitable premises
- Right to repair and deduct under MN law
- Protection from retaliation
""",
    },
    {
        "filename": "maintenance_request_oct15.pdf",
        "document_type": "correspondence",
        "description": "First maintenance request for broken heating",
        "extracted_text": """MAINTENANCE REQUEST

Date: October 15, 2024

To: ABC Property Management
From: Demo Tenant
Re: Urgent - Heating System Not Working

The heating system in my unit has stopped working. The temperature inside has dropped to 55°F and continues to fall. This is a health and safety emergency.

I am requesting immediate repair as required under Minnesota Statute 504B.161 (Landlord's duty to maintain).

Please respond within 24 hours.

[Signature]
Demo Tenant
""",
    },
    {
        "filename": "14_day_notice.pdf",
        "document_type": "notice",
        "description": "Defective 14-day notice from landlord",
        "extracted_text": """NOTICE TO PAY RENT OR QUIT

TO: Demo Tenant
PROPERTY: 1234 Main Street, Apt 5B

You are hereby notified that you owe $200.00 in unpaid rent.

You must pay this amount within 14 days or vacate the premises.

Dated: November 5, 2024

ABC Property Management

---
DEFECTS IN THIS NOTICE:
1. Missing required language about tenant's right to contest
2. Missing information about legal aid resources
3. Does not specify rental period for claimed arrearage
""",
    },
    {
        "filename": "eviction_complaint.pdf",
        "document_type": "legal",
        "description": "Eviction complaint filed by landlord",
        "extracted_text": f"""STATE OF MINNESOTA
COUNTY OF HENNEPIN
DISTRICT COURT - HOUSING COURT

Case No: {CASE_DATA['case_number']}

ABC Property Management,
    Plaintiff,
vs.
Demo Tenant,
    Defendant.

COMPLAINT FOR EVICTION

Plaintiff alleges:
1. Plaintiff is owner of property at 1234 Main Street, Apt 5B
2. Defendant is tenant under written lease
3. Defendant owes $200 in unpaid rent
4. Plaintiff served 14-day notice on November 5, 2024
5. Defendant failed to pay or vacate

WHEREFORE, Plaintiff requests:
- Judgment for possession
- Past due rent of $200
- Costs and disbursements
""",
    },
    {
        "filename": "answer_and_defenses.pdf",
        "document_type": "legal",
        "description": "Answer with affirmative defenses filed by tenant",
        "extracted_text": f"""STATE OF MINNESOTA
COUNTY OF HENNEPIN  
DISTRICT COURT - HOUSING COURT

Case No: {CASE_DATA['case_number']}

DEFENDANT'S ANSWER AND AFFIRMATIVE DEFENSES

Defendant Demo Tenant answers as follows:

ANSWER:
1. Admitted
2. Admitted
3. DENIED - Rent was lawfully reduced under MN Stat 504B.385
4. Admitted notice was served; DENIED it was legally sufficient
5. DENIED

AFFIRMATIVE DEFENSES:

FIRST DEFENSE - Defective Notice
The 14-day notice failed to include required statutory language under MN Stat 504B.321.

SECOND DEFENSE - Habitability/Repair and Deduct
Landlord failed to maintain habitable premises (broken heating). Tenant lawfully exercised repair-and-deduct remedy under MN Stat 504B.385.

THIRD DEFENSE - Retaliation
This eviction was filed within 90 days of tenant's protected maintenance complaints, creating presumption of retaliation under MN Stat 504B.441.

COUNTERCLAIM:
Defendant counterclaims for:
- Return of improperly withheld rent deduction
- Damages for breach of habitability covenant
- Attorney fees if represented

Dated: November 22, 2024

[Signature]
Demo Tenant, Pro Se Defendant
""",
    },
]


async def populate_database():
    """Populate database with court-ready case data."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        user_id = "open-mode-user"
        
        # Add documents
        print("📄 Adding documents...")
        for doc_data in DOCUMENTS:
            doc_id = str(uuid.uuid4())
            content = doc_data["extracted_text"]
            doc = Document(
                id=doc_id,
                user_id=user_id,
                filename=doc_data["filename"],
                original_filename=doc_data["filename"],
                file_path=f"uploads/vault/{doc_data['filename']}",
                document_type=doc_data["document_type"],
                description=doc_data.get("description", ""),
                file_size=len(content),
                mime_type="application/pdf",
                sha256_hash=hashlib.sha256(content.encode()).hexdigest(),
            )
            session.add(doc)
        
        # Add timeline events
        print("📅 Adding timeline events...")
        for event_data in TIMELINE_EVENTS:
            event_id = str(uuid.uuid4())
            event = TimelineEvent(
                id=event_id,
                user_id=user_id,
                event_type=event_data["event_type"],
                title=event_data["title"],
                description=event_data["description"],
                event_date=datetime.strptime(event_data["event_date"], "%Y-%m-%d"),
                is_evidence=event_data["is_evidence"],
            )
            session.add(event)
        
        # Add calendar events
        print("📆 Adding calendar events...")
        for cal_data in CALENDAR_EVENTS:
            cal_id = str(uuid.uuid4())
            event_dt = datetime.strptime(f"{cal_data['event_date']} {cal_data['event_time']}", "%Y-%m-%d %H:%M")
            cal = CalendarEvent(
                id=cal_id,
                user_id=user_id,
                title=cal_data["title"],
                description=cal_data["description"],
                start_datetime=event_dt,
                event_type=cal_data["event_type"],
                is_critical=cal_data["event_type"] == "court",
            )
            session.add(cal)
        
        await session.commit()
        print("\n✅ Court case populated successfully!")
        print(f"   📄 {len(DOCUMENTS)} documents")
        print(f"   📅 {len(TIMELINE_EVENTS)} timeline events")
        print(f"   📆 {len(CALENDAR_EVENTS)} calendar events")
        print(f"\n🏛️ Case Number: {CASE_DATA['case_number']}")
        print(f"📍 Hearing: December 2, 2024 at 9:00 AM")
        print(f"🏠 Property: {CASE_DATA['property_address']}")


if __name__ == "__main__":
    asyncio.run(populate_database())
