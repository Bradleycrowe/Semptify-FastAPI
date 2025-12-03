"""
Semptify Zoom Courtroom Module
Virtual courtroom assistance for remote hearings.
Includes preparation, tech setup, etiquette, and real-time guidance.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from datetime import datetime, date, time
from enum import Enum

from app.core.security import get_current_user
from app.core.user_context import UserContext
from app.services.form_data import get_form_data_service
from app.services.eviction.pdf import generate_hearing_prep_pdf


router = APIRouter(prefix="/api/zoom-court", tags=["Zoom Courtroom"])


# =============================================================================
# Data Models
# =============================================================================

class HearingType(str, Enum):
    INITIAL = "initial_appearance"
    PRETRIAL = "pretrial_conference"
    TRIAL = "trial"
    MOTION = "motion_hearing"
    SETTLEMENT = "settlement_conference"


class TechCheckItem(BaseModel):
    """Technology checklist item."""
    item: str
    description: str
    how_to_fix: str
    critical: bool


class EtiquetteRule(BaseModel):
    """Courtroom etiquette rule."""
    rule: str
    explanation: str
    consequences: str


class HearingPrep(BaseModel):
    """Hearing preparation guide."""
    hearing_type: HearingType
    title: str
    what_to_expect: List[str]
    what_to_prepare: List[str]
    common_questions: List[Dict[str, str]]
    tips: List[str]


# =============================================================================
# Zoom Setup Guide
# =============================================================================

TECH_CHECKLIST = [
    {
        "item": "Internet Connection",
        "description": "Stable high-speed internet required",
        "how_to_fix": "Use ethernet if possible, close other apps, have mobile hotspot as backup",
        "critical": True
    },
    {
        "item": "Camera",
        "description": "Working webcam positioned at eye level",
        "how_to_fix": "Test in Zoom settings, use books to raise laptop, clean lens",
        "critical": True
    },
    {
        "item": "Microphone",
        "description": "Clear audio without echo or background noise",
        "how_to_fix": "Use headphones with mic, mute when not speaking, test in quiet room",
        "critical": True
    },
    {
        "item": "Lighting",
        "description": "Face should be well-lit, no backlighting",
        "how_to_fix": "Face a window, add desk lamp in front of you, avoid sitting with window behind",
        "critical": True
    },
    {
        "item": "Background",
        "description": "Professional, neutral background",
        "how_to_fix": "Use plain wall, tidy the area, use virtual background if needed",
        "critical": False
    },
    {
        "item": "Zoom App",
        "description": "Latest version of Zoom installed",
        "how_to_fix": "Download from zoom.us, update if prompted",
        "critical": True
    },
    {
        "item": "Meeting Link",
        "description": "Court Zoom link saved and accessible",
        "how_to_fix": "Check court notice, call clerk if missing, save link in calendar",
        "critical": True
    },
    {
        "item": "Battery/Power",
        "description": "Device fully charged or plugged in",
        "how_to_fix": "Plug in device, have charger nearby, check battery before hearing",
        "critical": True
    },
    {
        "item": "Quiet Environment",
        "description": "No background noise or interruptions",
        "how_to_fix": "Find private room, inform household, use 'Do Not Disturb'",
        "critical": True
    },
    {
        "item": "Backup Plan",
        "description": "Phone ready as backup if technology fails",
        "how_to_fix": "Have court phone number, Zoom app on phone, know how to call in",
        "critical": True
    }
]

ETIQUETTE_RULES = [
    {
        "rule": "Dress Professionally",
        "explanation": "Wear business casual or professional attire as if attending in person",
        "consequences": "Judge may view casual dress as disrespectful"
    },
    {
        "rule": "Log In Early",
        "explanation": "Join the meeting 10-15 minutes before scheduled time",
        "consequences": "Late arrival may result in default or case being passed"
    },
    {
        "rule": "Stay Muted",
        "explanation": "Keep yourself muted unless speaking to avoid background noise",
        "consequences": "Judge may mute you or warn you"
    },
    {
        "rule": "Look at Camera",
        "explanation": "When speaking, look at the camera to simulate eye contact",
        "consequences": "Appears more credible and engaged"
    },
    {
        "rule": "State Your Name",
        "explanation": "Identify yourself before speaking: 'This is [Name], Your Honor'",
        "consequences": "Court record needs clear identification"
    },
    {
        "rule": "Don't Interrupt",
        "explanation": "Wait for others to finish speaking completely",
        "consequences": "Judge may admonish you, appears unprofessional"
    },
    {
        "rule": "No Recording",
        "explanation": "Recording court proceedings is prohibited",
        "consequences": "May be held in contempt of court"
    },
    {
        "rule": "Minimize Distractions",
        "explanation": "Turn off notifications, silence phone, close other apps",
        "consequences": "Distractions appear unprofessional"
    },
    {
        "rule": "Stay Visible",
        "explanation": "Keep camera on and remain in frame throughout hearing",
        "consequences": "Judge may require camera on, case may be continued"
    },
    {
        "rule": "Have Documents Ready",
        "explanation": "Keep all exhibits and documents organized and accessible",
        "consequences": "Unable to present evidence if not prepared"
    }
]

HEARING_GUIDES = {
    HearingType.INITIAL: {
        "hearing_type": HearingType.INITIAL,
        "title": "Initial Appearance / First Hearing",
        "what_to_expect": [
            "Judge will call your case by number and name",
            "Both parties will be asked to identify themselves",
            "Judge will ask if you received the complaint",
            "You may be asked if you filed an Answer",
            "Judge may ask about settlement possibilities",
            "If no agreement, trial date will be set"
        ],
        "what_to_prepare": [
            "Know your case number",
            "Have your filed Answer ready to reference",
            "List of key issues you want addressed",
            "Calendar to check available dates",
            "Any settlement proposal you want to make"
        ],
        "common_questions": [
            {"question": "Did you receive service of the complaint?", "answer": "Yes, Your Honor, I was served on [date]"},
            {"question": "Have you filed an Answer?", "answer": "Yes, Your Honor, I filed my Answer on [date]"},
            {"question": "Are the parties willing to discuss settlement?", "answer": "I am willing to discuss resolution, Your Honor"},
            {"question": "Do you need a jury trial?", "answer": "Yes, Your Honor, I have filed a jury demand / No, Your Honor, I waive jury"}
        ],
        "tips": [
            "Be ready to state your position clearly and briefly",
            "Don't argue the full case at this stage",
            "Be open to settlement discussions",
            "Request enough time to prepare for trial"
        ]
    },
    HearingType.TRIAL: {
        "hearing_type": HearingType.TRIAL,
        "title": "Trial Hearing",
        "what_to_expect": [
            "Landlord presents case first (they have burden of proof)",
            "Landlord calls witnesses and presents evidence",
            "You can cross-examine landlord's witnesses",
            "Then you present your defense",
            "You testify and present your evidence",
            "Landlord can cross-examine you",
            "Closing arguments by both sides",
            "Judge issues ruling (may be immediate or later)"
        ],
        "what_to_prepare": [
            "All evidence organized with exhibit numbers",
            "Exhibit list for the judge",
            "Written outline of your testimony",
            "Questions prepared for cross-examination",
            "List of defenses and legal citations",
            "Witnesses confirmed and ready"
        ],
        "common_questions": [
            {"question": "How do you plead to the allegations?", "answer": "I deny the allegations, Your Honor"},
            {"question": "Is [exhibit] admitted?", "answer": "Objection, Your Honor [state reason] / No objection"},
            {"question": "Do you have any witnesses?", "answer": "Yes, Your Honor, I call [name] / No, Your Honor"},
            {"question": "Is that all your evidence?", "answer": "Yes, Your Honor, the defense rests"}
        ],
        "tips": [
            "Stay calm and stick to the facts",
            "Object to improper evidence or questions",
            "Listen carefully before responding",
            "Ask for clarification if you don't understand",
            "Don't argue with the landlord, address the judge"
        ]
    },
    HearingType.MOTION: {
        "hearing_type": HearingType.MOTION,
        "title": "Motion Hearing",
        "what_to_expect": [
            "Judge will identify the motion being heard",
            "Moving party presents argument first",
            "Opposing party responds",
            "Judge may ask questions",
            "Judge rules on the motion"
        ],
        "what_to_prepare": [
            "Know the motion and your arguments thoroughly",
            "Have copies of all relevant cases and statutes",
            "Prepare responses to likely counterarguments",
            "Have your motion papers accessible"
        ],
        "common_questions": [
            {"question": "Counsel, please summarize your motion", "answer": "Your Honor, I move to [dismiss/continue/etc] because..."},
            {"question": "What is your response?", "answer": "Your Honor, I oppose the motion because..."},
            {"question": "What authority supports your position?", "answer": "Your Honor, [statute/case] provides that..."}
        ],
        "tips": [
            "Be concise - judges appreciate brevity",
            "Focus on the legal standard",
            "Cite specific authorities",
            "Have fallback positions ready"
        ]
    }
}


# =============================================================================
# Common Problems & Solutions
# =============================================================================

COMMON_PROBLEMS = [
    {
        "problem": "Can't hear anyone",
        "solutions": [
            "Check that your speaker is not muted in Zoom",
            "Check computer volume is up",
            "Try selecting different audio output in Zoom settings",
            "Leave and rejoin the meeting",
            "Call in by phone if audio continues to fail"
        ]
    },
    {
        "problem": "Others can't hear me",
        "solutions": [
            "Check you're not muted (unmute button in Zoom)",
            "Ensure correct microphone selected in settings",
            "Unplug and replug headphones",
            "Try computer microphone instead of headphones",
            "Type in chat that you're having audio issues"
        ]
    },
    {
        "problem": "Video not working",
        "solutions": [
            "Check camera is not covered",
            "Ensure correct camera selected in settings",
            "Close other apps that might use camera",
            "Restart Zoom application",
            "Inform court via chat that camera is having issues"
        ]
    },
    {
        "problem": "Connection is choppy/freezing",
        "solutions": [
            "Turn off video to preserve bandwidth for audio",
            "Close other applications and browser tabs",
            "Move closer to WiFi router",
            "Switch to phone hotspot",
            "Call in by phone as backup"
        ]
    },
    {
        "problem": "Got disconnected",
        "solutions": [
            "Rejoin immediately using the same link",
            "Call the court clerk to notify them",
            "Have court phone number ready",
            "Use phone as backup to rejoin",
            "Document the disconnection time"
        ]
    },
    {
        "problem": "Can't share screen/documents",
        "solutions": [
            "Ask court if screen sharing is enabled",
            "Use 'Share Screen' button and select document",
            "Email documents to court before hearing as backup",
            "Hold documents up to camera if needed",
            "Describe the document verbally"
        ]
    }
]


# =============================================================================
# Pre-Hearing Checklist Generator
# =============================================================================

def generate_prehearing_checklist(hearing_type: HearingType, hearing_date: date, hearing_time: time):
    """Generate a personalized pre-hearing checklist."""
    checklist = {
        "hearing_info": {
            "type": hearing_type.value,
            "date": hearing_date.isoformat(),
            "time": hearing_time.isoformat()
        },
        "one_week_before": [
            {"task": "Confirm you have the Zoom link", "done": False},
            {"task": "Review your case file and evidence", "done": False},
            {"task": "Prepare written outline of testimony", "done": False},
            {"task": "Test Zoom on device you'll use", "done": False},
            {"task": "Identify backup device (phone)", "done": False}
        ],
        "one_day_before": [
            {"task": "Do full technology test", "done": False},
            {"task": "Organize all documents in order", "done": False},
            {"task": "Confirm witnesses (if any)", "done": False},
            {"task": "Set up your hearing space", "done": False},
            {"task": "Charge all devices", "done": False},
            {"task": "Set two alarms for tomorrow", "done": False},
            {"task": "Lay out professional clothing", "done": False}
        ],
        "morning_of": [
            {"task": "Dress professionally", "done": False},
            {"task": "Eat and use restroom before", "done": False},
            {"task": "Set up in quiet location", "done": False},
            {"task": "Turn off phone notifications", "done": False},
            {"task": "Close unnecessary computer programs", "done": False},
            {"task": "Have documents and pen ready", "done": False},
            {"task": "Have water nearby", "done": False}
        ],
        "15_minutes_before": [
            {"task": "Join the Zoom meeting", "done": False},
            {"task": "Test audio and video", "done": False},
            {"task": "Rename yourself to full legal name", "done": False},
            {"task": "Wait in waiting room if required", "done": False},
            {"task": "Stay muted until called upon", "done": False}
        ]
    }
    
    return checklist


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/tech-checklist", response_model=List[TechCheckItem])
async def get_tech_checklist(user: UserContext = Depends(get_current_user)):
    """Get the complete technology setup checklist."""
    return [TechCheckItem(**item) for item in TECH_CHECKLIST]


@router.get("/etiquette", response_model=List[EtiquetteRule])
async def get_etiquette_rules(user: UserContext = Depends(get_current_user)):
    """Get all courtroom etiquette rules for Zoom hearings."""
    return [EtiquetteRule(**rule) for rule in ETIQUETTE_RULES]


@router.get("/hearing-guide/{hearing_type}", response_model=HearingPrep)
async def get_hearing_guide(
    hearing_type: HearingType,
    user: UserContext = Depends(get_current_user)
):
    """Get preparation guide for specific hearing type."""
    if hearing_type not in HEARING_GUIDES:
        raise HTTPException(status_code=404, detail="Hearing guide not found")

    return HearingPrep(**HEARING_GUIDES[hearing_type])


@router.get("/common-problems")
async def get_common_problems(user: UserContext = Depends(get_current_user)):
    """Get list of common technical problems and solutions."""
    return {"problems": COMMON_PROBLEMS}
class ChecklistRequest(BaseModel):
    """Request for personalized checklist."""
    hearing_type: HearingType
    hearing_date: date
    hearing_time: time


@router.post("/generate-checklist")
async def generate_checklist(
    request: ChecklistRequest,
    user: UserContext = Depends(get_current_user)
):
    """Generate a personalized pre-hearing checklist."""
    return generate_prehearing_checklist(
        request.hearing_type,
        request.hearing_date,
        request.hearing_time
    )


@router.get("/quick-tips")
async def get_quick_tips(user: UserContext = Depends(get_current_user)):
    """Get quick reference tips for Zoom court."""
    return {
        "before_hearing": [
            "🔗 Save Zoom link somewhere easy to find",
            "🔋 Charge your device fully",
            "🎧 Test audio with headphones",
            "💡 Set up good lighting on your face",
            "📄 Have documents organized and numbered",
            "📱 Keep phone as backup"
        ],
        "during_hearing": [
            "🔇 Stay muted unless speaking",
            "👁️ Look at camera when talking",
            "🗣️ State your name before speaking",
            "✋ Raise hand feature to get attention",
            "⏸️ Pause before answering questions",
            "🚫 Don't interrupt"
        ],
        "if_problems": [
            "📞 Have court phone number ready",
            "💬 Use chat to alert of tech issues",
            "🔄 Rejoin immediately if disconnected",
            "📵 Turn off video if connection is poor",
            "🆘 Type 'experiencing technical difficulties' in chat"
        ]
    }


@router.get("/zoom-controls")
async def get_zoom_controls(user: UserContext = Depends(get_current_user)):
    """Get guide to Zoom controls for court."""
    return {
        "essential_controls": [
            {
                "button": "Mute/Unmute",
                "location": "Bottom left of Zoom window",
                "shortcut": "Alt+A (Windows) or Cmd+Shift+A (Mac)",
                "when_to_use": "Unmute only when it's your turn to speak"
            },
            {
                "button": "Start/Stop Video",
                "location": "Bottom left, next to Mute",
                "shortcut": "Alt+V (Windows) or Cmd+Shift+V (Mac)",
                "when_to_use": "Keep on unless court instructs otherwise"
            },
            {
                "button": "Raise Hand",
                "location": "Reactions menu at bottom",
                "shortcut": "Alt+Y (Windows)",
                "when_to_use": "To get judge's attention to speak"
            },
            {
                "button": "Chat",
                "location": "Bottom toolbar",
                "shortcut": "Alt+H (Windows)",
                "when_to_use": "Only for technical issues, not case matters"
            },
            {
                "button": "Share Screen",
                "location": "Bottom center toolbar",
                "shortcut": "Alt+S (Windows)",
                "when_to_use": "Only if court allows and you need to show documents"
            }
        ],
        "settings_to_check": [
            "Audio: Ensure correct microphone and speaker selected",
            "Video: Ensure correct camera selected",
            "General: Enable 'Always show meeting controls'",
            "Rename yourself to your full legal name"
        ]
    }


@router.get("/phrases-to-use")
async def get_court_phrases(user: UserContext = Depends(get_current_user)):
    """Get helpful phrases for court proceedings."""
    return {
        "addressing_judge": [
            {"situation": "Getting judge's attention", "phrase": "Your Honor, may I be heard?"},
            {"situation": "Responding to judge", "phrase": "Yes, Your Honor" or "No, Your Honor"},
            {"situation": "Need clarification", "phrase": "Your Honor, may I ask for clarification?"},
            {"situation": "Need a moment", "phrase": "Your Honor, may I have a moment to review that?"}
        ],
        "presenting_evidence": [
            {"situation": "Introducing exhibit", "phrase": "Your Honor, I would like to introduce Exhibit [#]"},
            {"situation": "Describing document", "phrase": "This is a [type of document] dated [date]"},
            {"situation": "Referencing testimony", "phrase": "As I testified earlier..."}
        ],
        "objections": [
            {"situation": "Hearsay", "phrase": "Objection, Your Honor, hearsay"},
            {"situation": "Relevance", "phrase": "Objection, Your Honor, not relevant"},
            {"situation": "Leading question", "phrase": "Objection, Your Honor, leading the witness"},
            {"situation": "Asked and answered", "phrase": "Objection, Your Honor, asked and answered"}
        ],
        "technical_issues": [
            {"situation": "Audio problem", "phrase": "Your Honor, I'm experiencing audio difficulties"},
            {"situation": "Video problem", "phrase": "Your Honor, my camera appears to be malfunctioning"},
            {"situation": "Need to rejoin", "phrase": "I apologize, Your Honor, I was disconnected"}
        ]
    }


# =============================================================================
# Case-Integrated Zoom Preparation
# =============================================================================

@router.get("/my-hearing-prep")
async def get_my_hearing_prep(user: UserContext = Depends(get_current_user)):
    """Get personalized hearing prep based on case data."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    summary = form_service.get_case_summary()
    answer_data = form_service.get_answer_form_data()
    
    # Determine hearing type from case stage
    hearing_type = HearingType.INITIAL
    stage = summary.get("stage", "")
    if "trial" in stage.lower():
        hearing_type = HearingType.TRIAL
    elif "motion" in stage.lower():
        hearing_type = HearingType.MOTION
    
    # Get the hearing guide
    guide = HEARING_GUIDES.get(hearing_type, HEARING_GUIDES[HearingType.INITIAL])
    
    # Build personalized prep
    return {
        "case_info": {
            "case_number": summary.get("case_number", "Not entered"),
            "hearing_date": summary.get("hearing_date", "Not scheduled"),
            "hearing_time": summary.get("hearing_time", ""),
            "days_until_hearing": summary.get("days_to_hearing"),
            "tenant_name": summary.get("tenant_name", "Not entered"),
            "landlord_name": summary.get("landlord_name", "Not entered"),
        },
        "hearing_type": hearing_type.value,
        "hearing_guide": guide,
        "your_defenses": answer_data.get("defenses", []),
        "defenses_count": summary.get("defenses_count", 0),
        "documents_count": summary.get("documents_count", 0),
        "tech_checklist": TECH_CHECKLIST,
        "etiquette_rules": ETIQUETTE_RULES[:5],  # Top 5 rules
        "quick_tips": {
            "before": [
                f"📋 Your case number is: {summary.get('case_number', 'Check your summons')}",
                "🔗 Save your Zoom link from the court notice",
                f"📄 You have {summary.get('documents_count', 0)} documents - organize them",
                "🎧 Test your audio with headphones",
                "💡 Set up good lighting"
            ],
            "during": [
                f"🗣️ Identify yourself: 'This is {summary.get('tenant_name', '[Your Name]')}, Your Honor'",
                "🔇 Stay muted when not speaking",
                "👁️ Look at camera when speaking",
                f"📋 Reference your {summary.get('defenses_count', 0)} defenses when asked"
            ]
        },
        "emergency_contacts": {
            "court_phone": "651-438-4300",
            "court_name": "Dakota County District Court"
        }
    }


@router.get("/generate-zoom-prep-pdf")
async def generate_zoom_prep_pdf(
    include_checklist: bool = Query(True),
    include_phrases: bool = Query(True),
    user: UserContext = Depends(get_current_user)
):
    """Generate a printable Zoom hearing preparation PDF."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    summary = form_service.get_case_summary()
    
    # Build checklist items
    checklist_items = [
        "✅ Confirm Zoom link saved",
        "✅ Test camera and microphone",
        "✅ Charge device / have charger ready",
        "✅ Set up quiet, well-lit location",
        "✅ Organize all documents with exhibit numbers",
        "✅ Have pen and paper ready",
        "✅ Have court phone number: 651-438-4300",
        "✅ Dress professionally",
        "✅ Join 15 minutes early",
        "✅ Keep phone as backup"
    ]
    
    if include_phrases:
        checklist_items.extend([
            "",
            "KEY PHRASES:",
            "• 'Your Honor, may I be heard?'",
            "• 'This is [Your Name], Your Honor'",
            "• 'Objection, Your Honor...'",
            "• 'I apologize, I was disconnected'",
        ])
    
    # Generate PDF using existing service
    pdf_bytes = generate_hearing_prep_pdf(
        tenant_name=summary.get("tenant_name", "Tenant"),
        hearing_date=summary.get("hearing_date", ""),
        hearing_time=summary.get("hearing_time", ""),
        is_zoom=True,
        checklist_items=checklist_items if include_checklist else None,
    )
    
    return Response(
        content=pdf_bytes,
        media_type="text/html",  # Falls back to HTML since WeasyPrint not installed
        headers={"Content-Disposition": f"attachment; filename=Zoom_Hearing_Prep_{datetime.now().strftime('%Y%m%d')}.html"}
    )


@router.get("/countdown")
async def get_hearing_countdown(user: UserContext = Depends(get_current_user)):
    """Get countdown to hearing with prep reminders."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    summary = form_service.get_case_summary()
    days = summary.get("days_to_hearing")
    
    if days is None:
        return {
            "has_hearing": False,
            "message": "No hearing date scheduled",
            "action": "Check your court notice for hearing date"
        }
    
    # Determine urgency and actions
    if days < 0:
        urgency = "past"
        message = f"Your hearing was {abs(days)} days ago"
        actions = ["Check court for outcome", "File any required follow-up"]
    elif days == 0:
        urgency = "today"
        message = "Your hearing is TODAY!"
        actions = [
            "Join Zoom 15 minutes early",
            "Have all documents ready",
            "Test audio/video now",
            "Dress professionally"
        ]
    elif days == 1:
        urgency = "tomorrow"
        message = "Your hearing is TOMORROW!"
        actions = [
            "Do full tech test tonight",
            "Lay out professional clothes",
            "Review your testimony outline",
            "Set multiple alarms",
            "Get good sleep"
        ]
    elif days <= 3:
        urgency = "critical"
        message = f"Your hearing is in {days} days"
        actions = [
            "Test Zoom connection",
            "Finalize document organization",
            "Practice key points",
            "Confirm you have Zoom link"
        ]
    elif days <= 7:
        urgency = "soon"
        message = f"Your hearing is in {days} days"
        actions = [
            "Review case file thoroughly",
            "Prepare written testimony outline",
            "Test all technology",
            "Organize exhibits"
        ]
    else:
        urgency = "upcoming"
        message = f"Your hearing is in {days} days"
        actions = [
            "Continue gathering evidence",
            "Review legal defenses",
            "Consider settlement options"
        ]
    
    return {
        "has_hearing": True,
        "hearing_date": summary.get("hearing_date"),
        "hearing_time": summary.get("hearing_time"),
        "days_until": days,
        "urgency": urgency,
        "message": message,
        "actions": actions,
        "case_number": summary.get("case_number", "Not entered")
    }


@router.get("/day-of-checklist")
async def get_day_of_checklist(user: UserContext = Depends(get_current_user)):
    """Get the day-of-hearing checklist."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    summary = form_service.get_case_summary()
    
    return {
        "hearing_info": {
            "case_number": summary.get("case_number", "Check summons"),
            "date": summary.get("hearing_date", "Check notice"),
            "time": summary.get("hearing_time", "Check notice"),
        },
        "morning_checklist": [
            {"item": "Shower and dress professionally", "time": "2 hours before", "done": False},
            {"item": "Eat breakfast", "time": "1.5 hours before", "done": False},
            {"item": "Review testimony outline", "time": "1 hour before", "done": False},
            {"item": "Set up hearing space", "time": "45 min before", "done": False},
            {"item": "Silence phone, close other apps", "time": "30 min before", "done": False},
            {"item": "Test Zoom audio/video", "time": "20 min before", "done": False},
            {"item": "Join Zoom meeting", "time": "15 min before", "done": False},
            {"item": "Rename yourself to legal name", "time": "10 min before", "done": False},
            {"item": "Final document check", "time": "5 min before", "done": False},
        ],
        "have_ready": [
            f"📋 Case number: {summary.get('case_number', '___________')}",
            "📄 All exhibits organized by number",
            "📝 Written outline of your testimony",
            "🖊️ Pen and paper for notes",
            "💧 Water nearby",
            "📱 Phone with Zoom app (backup)",
            "📞 Court phone: 651-438-4300",
        ],
        "remember": [
            "Stay muted unless speaking",
            "Look at camera when talking", 
            f"Introduce yourself: 'This is {summary.get('tenant_name', '[Your Name]')}, Your Honor'",
            "Say 'Your Honor' when addressing judge",
            "Don't interrupt - wait your turn",
            "Stay calm and stick to facts"
        ]
    }
