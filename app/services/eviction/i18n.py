"""
Dakota County Eviction Defense - i18n Service
Quad-lingual support: English, Spanish, Somali, Arabic
"""

from typing import Dict, Optional, List

# ============================================================================
# Translation Strings
# ============================================================================

STRINGS: Dict[str, Dict[str, str]] = {
    # Navigation & Common
    "app_title": {
        "en": "Dakota County Eviction Defense",
        "es": "Defensa contra Desalojo del Condado de Dakota",
        "so": "Difaaca Ka Saarista Degmada Dakota",
        "ar": "دفاع الإخلاء في مقاطعة داكوتا"
    },
    "home": {
        "en": "Home",
        "es": "Inicio",
        "so": "Guriga",
        "ar": "الرئيسية"
    },
    "back": {
        "en": "Back",
        "es": "Atrás",
        "so": "Dib",
        "ar": "رجوع"
    },
    "next": {
        "en": "Next",
        "es": "Siguiente",
        "so": "Xiga",
        "ar": "التالي"
    },
    "submit": {
        "en": "Submit",
        "es": "Enviar",
        "so": "Dir",
        "ar": "إرسال"
    },
    "download": {
        "en": "Download",
        "es": "Descargar",
        "so": "Soo Degso",
        "ar": "تحميل"
    },
    "save": {
        "en": "Save",
        "es": "Guardar",
        "so": "Kaydi",
        "ar": "حفظ"
    },
    "cancel": {
        "en": "Cancel",
        "es": "Cancelar",
        "so": "Jooji",
        "ar": "إلغاء"
    },
    
    # Main Menu
    "answer_summons": {
        "en": "Answer the Summons",
        "es": "Responder a la Citación",
        "so": "Ka Jawaab Wacitaanka",
        "ar": "الرد على الاستدعاء"
    },
    "file_counterclaim": {
        "en": "File a Counterclaim",
        "es": "Presentar una Contrademanda",
        "so": "Dacwad Lid ah",
        "ar": "تقديم دعوى مضادة"
    },
    "motions": {
        "en": "Motions & Requests",
        "es": "Mociones y Solicitudes",
        "so": "Codsiyo & Dalabyo",
        "ar": "الطلبات والالتماسات"
    },
    "hearing_prep": {
        "en": "Hearing Preparation",
        "es": "Preparación para la Audiencia",
        "so": "Diyaarinta Dhageysiga",
        "ar": "التحضير لجلسة الاستماع"
    },
    "forms_library": {
        "en": "Court Forms Library",
        "es": "Biblioteca de Formularios",
        "so": "Maktabadda Foomamka",
        "ar": "مكتبة نماذج المحكمة"
    },
    "zoom_court": {
        "en": "Zoom Court Helper",
        "es": "Ayuda para Corte por Zoom",
        "so": "Caawiye Maxkamadda Zoom",
        "ar": "مساعد محكمة زووم"
    },
    
    # Answer Flow
    "step": {
        "en": "Step",
        "es": "Paso",
        "so": "Tallaabo",
        "ar": "خطوة"
    },
    "of": {
        "en": "of",
        "es": "de",
        "so": "ka mid ah",
        "ar": "من"
    },
    "your_information": {
        "en": "Your Information",
        "es": "Su Información",
        "so": "Macluumaadkaaga",
        "ar": "معلوماتك"
    },
    "tenant_name": {
        "en": "Your Full Name",
        "es": "Su Nombre Completo",
        "so": "Magacaaga Buuxa",
        "ar": "اسمك الكامل"
    },
    "landlord_name": {
        "en": "Landlord's Name",
        "es": "Nombre del Propietario",
        "so": "Magaca Mulkiilaha",
        "ar": "اسم المالك"
    },
    "case_number": {
        "en": "Case Number (if known)",
        "es": "Número de Caso (si lo sabe)",
        "so": "Lambarka Kiiska (haddii la yaqaan)",
        "ar": "رقم القضية (إن وجد)"
    },
    "property_address": {
        "en": "Property Address",
        "es": "Dirección de la Propiedad",
        "so": "Cinwaanka Guriga",
        "ar": "عنوان العقار"
    },
    "served_date": {
        "en": "Date You Were Served",
        "es": "Fecha en que Fue Notificado",
        "so": "Taariikhda Laguu Soo Diray",
        "ar": "تاريخ استلام الإخطار"
    },
    
    # Defenses
    "select_defenses": {
        "en": "Select Your Defenses",
        "es": "Seleccione Sus Defensas",
        "so": "Dooro Difaacyadaada",
        "ar": "اختر دفاعاتك"
    },
    "defense_nonpayment": {
        "en": "I paid the rent (or offered to pay)",
        "es": "Pagué el alquiler (u ofrecí pagar)",
        "so": "Waan bixiyey kirada (ama waan soo bandhigay)",
        "ar": "دفعت الإيجار (أو عرضت الدفع)"
    },
    "defense_habitability": {
        "en": "The property has serious problems (habitability)",
        "es": "La propiedad tiene problemas graves (habitabilidad)",
        "so": "Gurigu wuxuu leeyahay dhibaatooyin culus",
        "ar": "العقار به مشاكل خطيرة (صلاحية السكن)"
    },
    "defense_retaliation": {
        "en": "The eviction is retaliation for complaining",
        "es": "El desalojo es represalia por quejarme",
        "so": "Saarida waa aargoosi",
        "ar": "الإخلاء انتقامي بسبب الشكوى"
    },
    "defense_discrimination": {
        "en": "The eviction is discriminatory",
        "es": "El desalojo es discriminatorio",
        "so": "Saarida waa takoor",
        "ar": "الإخلاء تمييزي"
    },
    "defense_improper_notice": {
        "en": "I was not given proper notice",
        "es": "No recibí el aviso adecuado",
        "so": "Lama siin ogeysiis sax ah",
        "ar": "لم أتلق إشعاراً صحيحاً"
    },
    "defense_lease_violation": {
        "en": "I did not violate the lease as claimed",
        "es": "No violé el contrato como se afirma",
        "so": "Kuma xadgudin heshiiska sida la sheegay",
        "ar": "لم أنتهك عقد الإيجار كما يُدعى"
    },
    
    # Counterclaim
    "counterclaim_title": {
        "en": "File a Counterclaim",
        "es": "Presentar una Contrademanda",
        "so": "Dacwad Lid ah",
        "ar": "تقديم دعوى مضادة"
    },
    "claim_security_deposit": {
        "en": "Security deposit not returned",
        "es": "Depósito de seguridad no devuelto",
        "so": "Ceymiska aan la soo celin",
        "ar": "وديعة التأمين لم تُرد"
    },
    "claim_repairs": {
        "en": "Failed to make necessary repairs",
        "es": "No realizó las reparaciones necesarias",
        "so": "Wax ka beddelid aan la samayn",
        "ar": "فشل في إجراء الإصلاحات اللازمة"
    },
    "claim_harassment": {
        "en": "Harassment or illegal entry",
        "es": "Acoso o entrada ilegal",
        "so": "Dhibaateyn ama gelitaan sharci darro ah",
        "ar": "مضايقة أو دخول غير قانوني"
    },
    "claim_utilities": {
        "en": "Illegal utility shutoff",
        "es": "Corte ilegal de servicios",
        "so": "Adeegyo sharci darro ah oo la xiray",
        "ar": "قطع غير قانوني للمرافق"
    },
    
    # Motions
    "motion_dismiss": {
        "en": "Motion to Dismiss",
        "es": "Moción para Desestimar",
        "so": "Codsiga Joojinta",
        "ar": "طلب رفض الدعوى"
    },
    "motion_continuance": {
        "en": "Motion for Continuance",
        "es": "Moción de Aplazamiento",
        "so": "Codsiga Dib u Dhigista",
        "ar": "طلب تأجيل"
    },
    "motion_stay": {
        "en": "Motion to Stay Eviction",
        "es": "Moción para Suspender el Desalojo",
        "so": "Codsiga Joojinta Saarista",
        "ar": "طلب وقف الإخلاء"
    },
    "motion_fee_waiver": {
        "en": "Fee Waiver (IFP)",
        "es": "Exención de Tarifas",
        "so": "Ka Dhaafida Kharashka",
        "ar": "إعفاء من الرسوم"
    },
    
    # Hearing Prep
    "hearing_date": {
        "en": "Hearing Date",
        "es": "Fecha de Audiencia",
        "so": "Taariikhda Dhageysiga",
        "ar": "تاريخ الجلسة"
    },
    "hearing_time": {
        "en": "Hearing Time",
        "es": "Hora de Audiencia",
        "so": "Waqtiga Dhageysiga",
        "ar": "وقت الجلسة"
    },
    "is_zoom_hearing": {
        "en": "Is this a Zoom hearing?",
        "es": "¿Es una audiencia por Zoom?",
        "so": "Ma dhageysiga Zoom baa?",
        "ar": "هل هذه جلسة زووم؟"
    },
    "checklist_documents": {
        "en": "Bring copies of all documents",
        "es": "Traiga copias de todos los documentos",
        "so": "Keen koobiyaasha dukumeentiyada oo dhan",
        "ar": "أحضر نسخاً من جميع المستندات"
    },
    "checklist_evidence": {
        "en": "Organize your evidence",
        "es": "Organice su evidencia",
        "so": "Habee caddaymahaaga",
        "ar": "نظم أدلتك"
    },
    "checklist_witnesses": {
        "en": "Confirm witnesses can attend",
        "es": "Confirme que los testigos puedan asistir",
        "so": "Xaqiiji markhaatiyaasha inay imaanayaan",
        "ar": "تأكد من حضور الشهود"
    },
    
    # Zoom Court
    "zoom_tips_title": {
        "en": "Zoom Court Tips",
        "es": "Consejos para Corte por Zoom",
        "so": "Talooyinka Maxkamadda Zoom",
        "ar": "نصائح محكمة زووم"
    },
    "zoom_tip_1": {
        "en": "Test your audio and video before the hearing",
        "es": "Pruebe su audio y video antes de la audiencia",
        "so": "Tijaabi codkaaga iyo muuqaalkaaga dhageysiga ka hor",
        "ar": "اختبر الصوت والفيديو قبل الجلسة"
    },
    "zoom_tip_2": {
        "en": "Find a quiet place with good lighting",
        "es": "Encuentre un lugar tranquilo con buena iluminación",
        "so": "Hel meel aamusan oo iftiinka wanaagsan leh",
        "ar": "ابحث عن مكان هادئ بإضاءة جيدة"
    },
    "zoom_tip_3": {
        "en": "Dress professionally as you would for in-person court",
        "es": "Vístase profesionalmente como lo haría para corte en persona",
        "so": "Xidho si xirfadeed sida aad maxkamadda u geli lahayd",
        "ar": "ارتدِ ملابس رسمية كما في المحكمة الفعلية"
    },
    "zoom_tip_4": {
        "en": "Mute yourself when not speaking",
        "es": "Silénciese cuando no esté hablando",
        "so": "Iska aamusnow markaad aan hadlayn",
        "ar": "كتم الصوت عند عدم التحدث"
    },
    
    # Resources
    "resources_title": {
        "en": "Legal Resources",
        "es": "Recursos Legales",
        "so": "Ilaha Sharciga",
        "ar": "الموارد القانونية"
    },
    "homeline_desc": {
        "en": "Free tenant hotline and legal advice",
        "es": "Línea de ayuda gratuita para inquilinos",
        "so": "Khadka taleefanka kiraaleyda ee bilaashka ah",
        "ar": "خط مساعدة مجاني للمستأجرين"
    },
    "legal_aid_desc": {
        "en": "Free legal services for qualifying tenants",
        "es": "Servicios legales gratuitos",
        "so": "Adeegyo sharci oo bilaash ah",
        "ar": "خدمات قانونية مجانية"
    },
    
    # Deadlines & Warnings
    "deadline_warning": {
        "en": "⚠️ You typically have only 7 days to respond to an eviction summons in Minnesota",
        "es": "⚠️ Normalmente tiene solo 7 días para responder a una citación de desalojo en Minnesota",
        "so": "⚠️ Caadi ahaan waxaad haysataa 7 maalmood oo keliya si aad uga jawaabtid wacitaanka saarista Minnesota",
        "ar": "⚠️ عادة لديك 7 أيام فقط للرد على استدعاء الإخلاء في مينيسوتا"
    },
    "disclaimer": {
        "en": "This tool provides information only, not legal advice. Consider consulting with a lawyer.",
        "es": "Esta herramienta proporciona solo información, no asesoramiento legal.",
        "so": "Qalabkani wuxuu bixiyaa macluumaad kaliya, ma aha talo sharci ah.",
        "ar": "توفر هذه الأداة معلومات فقط، وليس مشورة قانونية."
    },
    
    # Success Messages
    "download_ready": {
        "en": "Your document is ready for download",
        "es": "Su documento está listo para descargar",
        "so": "Dukumentkaagu waa diyaar in la soo dejiyo",
        "ar": "مستندك جاهز للتحميل"
    },
    "form_saved": {
        "en": "Your progress has been saved",
        "es": "Su progreso ha sido guardado",
        "so": "Horumaarkaaga waa la kaydiyey",
        "ar": "تم حفظ تقدمك"
    },
}


def get_string(key: str, lang: str = "en") -> str:
    """Get a translated string by key and language."""
    if key in STRINGS:
        return STRINGS[key].get(lang, STRINGS[key].get("en", key))
    return key


def get_all_strings(lang: str = "en") -> Dict[str, str]:
    """Get all strings for a language."""
    return {key: get_string(key, lang) for key in STRINGS}


def get_supported_languages() -> List[str]:
    """Get list of supported language codes."""
    return ["en", "es", "so", "ar"]


def is_rtl(lang: str) -> bool:
    """Check if language is right-to-left."""
    return lang == "ar"
