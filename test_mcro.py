#!/usr/bin/env python
"""Test MCRO document recognition."""
import sys
sys.path.insert(0, '.')
from app.services.document_recognition import DocumentRecognitionEngine

engine = DocumentRecognitionEngine()

print("=" * 60)
print("MCRO Document Recognition Test Suite")
print("=" * 60)
print()

# Test cases from your actual documents
tests = [
    ("Motion to Dismiss", """
        STATE OF MINNESOTA - COUNTY OF DAKOTA
        Court File No. 19AV-CV-25-3477
        NOTICE OF DEFENDANTS MOTION AND MOTION TO DISMISS 
        WITHOUT PREJUDICE AND EXPUNGE
        Defendants respectfully move this Court to dismiss.
    """),
    
    ("Court Order", """
        STATE OF MINNESOTA - FIRST JUDICIAL DISTRICT
        IT IS HEREBY ORDERED that the Motion is GRANTED.
        The case is hereby dismissed without prejudice.
        So ordered.
    """),
    
    ("Judgment", """
        JUDGMENT
        Judgment is entered for the Defendant.
        The complaint is hereby dismissed.
    """),
    
    ("Summons", """
        SUMMONS
        YOU ARE BEING SUED. You must respond within 20 days.
        Failure to respond may result in default judgment.
    """),
    
    ("Eviction Filing", """
        COMPLAINT FOR UNLAWFUL DETAINER
        Plaintiff seeks recovery of premises and possession.
        Tenant has failed to pay rent as agreed.
    """),
]

print("Recognition Results:")
print("-" * 60)
for name, text in tests:
    result = engine.recognize(text, f"{name.replace(' ', '_')}.pdf")
    status = "✓" if result.confidence >= 0.7 else "⚠"
    print(f"{status} {name:20} → {result.doc_type.value:15} ({result.confidence:.0%})")

print()
print("=" * 60)
print("Your MCRO Motion Document:")
print("=" * 60)

mcro_motion = """
STATE OF MINNESOTA                         FIRST JUDICIAL DISTRICT
COUNTY OF DAKOTA                           DISTRICT COURT

                                          Court File No. 19AV-CV-25-3477

Lexington Flats, Limited Partnership,
                    Plaintiff,
vs.
Dena Sazama, Bradley Crowe,
                    Defendants.

    NOTICE OF DEFENDANTS' MOTION AND MOTION TO DISMISS WITHOUT PREJUDICE AND EXPUNGE

PLEASE TAKE NOTICE that the above-named Defendants, by and through counsel, will bring on 
for hearing a Motion to Dismiss Without Prejudice and Expunge before the Honorable Dannia Edwards,
or the presiding judge of Dakota County District Court, on December 3, 2025, at 1:30 p.m.,
via Zoom, or as soon thereafter as counsel may be heard.

MOTION

Defendants respectfully move this Court for an Order dismissing this action without prejudice
and expunging the court file pursuant to Minnesota law.

SOUTHERN MINNESOTA REGIONAL LEGAL SERVICES

Dated: December 2, 2025
Heather Mendiola, Attorney for Defendants
"""

result = engine.recognize(mcro_motion, "MCRO_19AV-CV-25-3477_Notice of Motion and Motion_2025-12-02.pdf")

print()
print(f"  Document Type: {result.doc_type.value.upper()}")
print(f"  Confidence:    {result.confidence:.0%}")
print(f"  Category:      {result.category.value}")
print()
print(f"  Case Number:   {result.case_numbers[0].value if result.case_numbers else 'N/A'}")
print(f"  Dates Found:   {len(result.dates)}")
print()
print(f"  Detection: {result.reasoning_chain[0] if result.reasoning_chain else 'Standard analysis'}")
