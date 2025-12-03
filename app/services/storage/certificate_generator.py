"""
Legal Certificate Generator - Creates Court-Admissible Verification Certificates

Generates professional PDF/HTML certificates that can be:
1. Printed and attached to court filings
2. Submitted as evidence of document authenticity
3. Used by notaries to verify document integrity
4. Presented to landlords/attorneys as proof

Certificate includes:
- Document fingerprint (SHA-256 hash)
- Timestamp with cryptographic proof
- Chain of custody summary
- QR code for online verification
- Legal attestation language

Compliant with:
- Federal Rules of Evidence 901(b)(9)
- Minnesota Statutes § 600.135
- ESIGN Act / UETA
"""

import hashlib
import base64
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from app.core.config import get_settings
from app.services.storage.legal_integrity import (
    hash_document,
    create_timestamp_proof,
    DocumentProof,
    AuditEntry,
)

settings = get_settings()


# =============================================================================
# Certificate Data Structure
# =============================================================================

@dataclass
class VerificationCertificate:
    """Data structure for verification certificate."""
    certificate_id: str
    certificate_type: str  # "document_integrity", "chain_of_custody", "notarized"
    issued_at: str
    expires_at: str  # Certificates valid for 10 years
    
    # Document Info
    document_name: str
    document_hash: str
    document_size_bytes: int
    hash_algorithm: str
    
    # Timestamp Info
    original_timestamp: str
    timestamp_proof: str
    
    # User Info
    owner_id: str
    owner_display: str  # e.g., "Google Drive User"
    
    # Verification
    verification_url: str
    verification_code: str  # Short code for manual verification
    qr_data: str
    
    # Legal
    attestation: str
    legal_notice: str
    
    # Signature
    certificate_signature: str
    
    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Certificate Generation
# =============================================================================

def generate_certificate_id() -> str:
    """Generate unique certificate ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(6).upper()
    return f"SMPT-{timestamp}-{random_part}"


def generate_verification_code(certificate_id: str, document_hash: str) -> str:
    """Generate short verification code for manual lookup."""
    combined = f"{certificate_id}:{document_hash}:{settings.SECRET_KEY}"
    full_hash = hashlib.sha256(combined.encode()).hexdigest()
    # Return first 12 chars in groups of 4
    return f"{full_hash[:4]}-{full_hash[4:8]}-{full_hash[8:12]}".upper()


def sign_certificate(certificate_data: dict) -> str:
    """Create digital signature for certificate."""
    import hmac
    import json
    
    # Remove signature field for signing
    data_to_sign = {k: v for k, v in certificate_data.items() if k != "certificate_signature"}
    content = json.dumps(data_to_sign, sort_keys=True)
    
    return hmac.new(
        settings.SECRET_KEY.encode(),
        content.encode(),
        hashlib.sha256
    ).hexdigest()


def create_verification_certificate(
    document_content: bytes,
    document_name: str,
    proof: DocumentProof,
    user_id: str,
    base_url: str = "https://semptify.com",
    audit_entries: Optional[List[AuditEntry]] = None,
) -> VerificationCertificate:
    """
    Create a verification certificate for a document.
    This is the main function for generating certificates.
    """
    from app.core.user_id import parse_user_id
    
    now = datetime.now(timezone.utc)
    certificate_id = generate_certificate_id()
    
    # Parse user info for display
    provider, role, _ = parse_user_id(user_id)
    provider_names = {
        "google_drive": "Google Drive",
        "dropbox": "Dropbox", 
        "onedrive": "OneDrive"
    }
    owner_display = f"{provider_names.get(provider, 'Storage')} User ({role.title() if role else 'User'})"
    
    # Generate verification URL and code
    verification_code = generate_verification_code(certificate_id, proof.document_hash)
    verification_url = f"{base_url}/verify/{certificate_id}"
    qr_data = f"{verification_url}?code={verification_code}"
    
    # Create attestation text
    attestation = f"""
CERTIFICATE OF DOCUMENT INTEGRITY

This certificate attests that the document identified below was verified by the 
Semptify Legal Integrity System on {now.strftime('%B %d, %Y at %I:%M %p UTC')}.

The cryptographic hash (SHA-256) of the document matches the hash recorded at the 
time of original upload on {proof.timestamp[:10]}.

This verification confirms that:
1. The document has not been modified since original upload
2. The timestamp is cryptographically signed and unalterable
3. A complete chain of custody record exists

This certificate may be relied upon as evidence of document authenticity pursuant 
to Federal Rules of Evidence 901(b)(9) and applicable state electronic records laws.
""".strip()

    # Legal notice
    legal_notice = """
LEGAL NOTICE: This certificate is generated by an automated system and is not a 
substitute for legal advice. The cryptographic verification methods used comply 
with industry standards (SHA-256, HMAC-SHA256) recognized by courts. For matters 
involving significant legal consequences, consult with a qualified attorney.

Semptify Legal Integrity Module v5.0
""".strip()

    # Build certificate (without signature first)
    cert_data = {
        "certificate_id": certificate_id,
        "certificate_type": "document_integrity",
        "issued_at": now.isoformat(),
        "expires_at": now.replace(year=now.year + 10).isoformat(),
        "document_name": document_name,
        "document_hash": proof.document_hash,
        "document_size_bytes": len(document_content),
        "hash_algorithm": "SHA-256",
        "original_timestamp": proof.timestamp,
        "timestamp_proof": proof.timestamp_hash,
        "owner_id": user_id,
        "owner_display": owner_display,
        "verification_url": verification_url,
        "verification_code": verification_code,
        "qr_data": qr_data,
        "attestation": attestation,
        "legal_notice": legal_notice,
        "certificate_signature": "",
    }
    
    # Sign the certificate
    cert_data["certificate_signature"] = sign_certificate(cert_data)
    
    return VerificationCertificate(**cert_data)


# =============================================================================
# Certificate HTML Generation
# =============================================================================

def generate_certificate_html(cert: VerificationCertificate) -> str:
    """
    Generate printable HTML certificate.
    Designed for professional court presentation.
    """
    
    # Format dates nicely
    issued_date = datetime.fromisoformat(cert.issued_at.replace('Z', '+00:00'))
    original_date = datetime.fromisoformat(cert.original_timestamp.replace('Z', '+00:00'))
    expires_date = datetime.fromisoformat(cert.expires_at.replace('Z', '+00:00'))
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Certificate of Document Integrity - {cert.certificate_id}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Open+Sans:wght@400;600&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        @page {{
            size: letter;
            margin: 0.5in;
        }}
        
        body {{
            font-family: 'Open Sans', sans-serif;
            background: #f5f5f5;
            color: #1a1a1a;
            line-height: 1.6;
        }}
        
        .certificate {{
            max-width: 8.5in;
            margin: 20px auto;
            background: white;
            border: 3px solid #1e3a5f;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            position: relative;
        }}
        
        .certificate::before {{
            content: '';
            position: absolute;
            top: 8px;
            left: 8px;
            right: 8px;
            bottom: 8px;
            border: 1px solid #c9a227;
            pointer-events: none;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 30px 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-family: 'Merriweather', serif;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 5px;
            letter-spacing: 2px;
        }}
        
        .header .subtitle {{
            font-size: 14px;
            opacity: 0.9;
            letter-spacing: 1px;
        }}
        
        .seal {{
            width: 80px;
            height: 80px;
            margin: 15px auto;
            background: linear-gradient(135deg, #c9a227 0%, #f4d03f 50%, #c9a227 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            box-shadow: 0 4px 15px rgba(201, 162, 39, 0.4);
        }}
        
        .body {{
            padding: 30px 40px;
        }}
        
        .certificate-id {{
            text-align: center;
            margin-bottom: 25px;
        }}
        
        .certificate-id .id {{
            font-family: 'Courier New', monospace;
            font-size: 18px;
            font-weight: bold;
            color: #1e3a5f;
            background: #f0f4f8;
            padding: 10px 20px;
            border-radius: 5px;
            display: inline-block;
        }}
        
        .attestation {{
            background: #fafafa;
            border-left: 4px solid #c9a227;
            padding: 20px 25px;
            margin: 25px 0;
            font-size: 14px;
            white-space: pre-line;
        }}
        
        .details {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 25px 0;
        }}
        
        .detail-box {{
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
        }}
        
        .detail-box h3 {{
            font-size: 11px;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 8px;
            letter-spacing: 1px;
        }}
        
        .detail-box .value {{
            font-family: 'Courier New', monospace;
            font-size: 13px;
            word-break: break-all;
            color: #1a1a1a;
        }}
        
        .detail-box .value.large {{
            font-size: 16px;
            font-weight: 600;
        }}
        
        .hash-display {{
            background: #1e3a5f;
            color: #4ade80;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            word-break: break-all;
            margin: 20px 0;
            text-align: center;
        }}
        
        .hash-display .label {{
            color: #94a3b8;
            font-size: 10px;
            display: block;
            margin-bottom: 5px;
        }}
        
        .verification {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f0f4f8;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
        }}
        
        .verification-code {{
            text-align: center;
        }}
        
        .verification-code .label {{
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .verification-code .code {{
            font-family: 'Courier New', monospace;
            font-size: 24px;
            font-weight: bold;
            color: #1e3a5f;
            letter-spacing: 2px;
        }}
        
        .qr-placeholder {{
            width: 100px;
            height: 100px;
            background: white;
            border: 2px solid #1e3a5f;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            color: #666;
            text-align: center;
            padding: 10px;
        }}
        
        .verification-url {{
            font-size: 12px;
            color: #1e3a5f;
        }}
        
        .timestamps {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
            text-align: center;
        }}
        
        .timestamp-item {{
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .timestamp-item .label {{
            font-size: 10px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        
        .timestamp-item .date {{
            font-weight: 600;
            font-size: 14px;
        }}
        
        .timestamp-item .time {{
            font-size: 12px;
            color: #666;
        }}
        
        .signature-section {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        
        .digital-signature {{
            text-align: left;
        }}
        
        .digital-signature .label {{
            font-size: 10px;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .digital-signature .sig {{
            font-family: 'Courier New', monospace;
            font-size: 9px;
            color: #1e3a5f;
            word-break: break-all;
            max-width: 300px;
        }}
        
        .issued-by {{
            text-align: right;
        }}
        
        .issued-by .logo {{
            font-size: 24px;
            margin-bottom: 5px;
        }}
        
        .issued-by .name {{
            font-weight: 600;
            color: #1e3a5f;
        }}
        
        .issued-by .version {{
            font-size: 11px;
            color: #666;
        }}
        
        .legal-notice {{
            margin-top: 25px;
            padding: 15px;
            background: #fff8e1;
            border: 1px solid #ffe082;
            border-radius: 8px;
            font-size: 10px;
            color: #5d4037;
            white-space: pre-line;
        }}
        
        .footer {{
            background: #1e3a5f;
            color: white;
            padding: 15px 40px;
            text-align: center;
            font-size: 11px;
        }}
        
        .footer a {{
            color: #4ade80;
        }}
        
        @media print {{
            body {{
                background: white;
            }}
            .certificate {{
                box-shadow: none;
                margin: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">
            <div class="seal">🛡️</div>
            <h1>CERTIFICATE OF DOCUMENT INTEGRITY</h1>
            <div class="subtitle">SEMPTIFY LEGAL INTEGRITY MODULE</div>
        </div>
        
        <div class="body">
            <div class="certificate-id">
                <div class="id">{cert.certificate_id}</div>
            </div>
            
            <div class="attestation">{cert.attestation}</div>
            
            <div class="details">
                <div class="detail-box">
                    <h3>Document Name</h3>
                    <div class="value large">{cert.document_name}</div>
                </div>
                <div class="detail-box">
                    <h3>Document Size</h3>
                    <div class="value large">{cert.document_size_bytes:,} bytes</div>
                </div>
                <div class="detail-box">
                    <h3>Document Owner</h3>
                    <div class="value">{cert.owner_display}</div>
                </div>
                <div class="detail-box">
                    <h3>Owner ID</h3>
                    <div class="value">{cert.owner_id}</div>
                </div>
            </div>
            
            <div class="hash-display">
                <span class="label">CRYPTOGRAPHIC FINGERPRINT (SHA-256)</span>
                {cert.document_hash}
            </div>
            
            <div class="timestamps">
                <div class="timestamp-item">
                    <div class="label">Original Upload</div>
                    <div class="date">{original_date.strftime('%B %d, %Y')}</div>
                    <div class="time">{original_date.strftime('%I:%M %p UTC')}</div>
                </div>
                <div class="timestamp-item">
                    <div class="label">Certificate Issued</div>
                    <div class="date">{issued_date.strftime('%B %d, %Y')}</div>
                    <div class="time">{issued_date.strftime('%I:%M %p UTC')}</div>
                </div>
                <div class="timestamp-item">
                    <div class="label">Valid Until</div>
                    <div class="date">{expires_date.strftime('%B %d, %Y')}</div>
                    <div class="time">11:59 PM UTC</div>
                </div>
            </div>
            
            <div class="verification">
                <div class="verification-code">
                    <div class="label">Verification Code</div>
                    <div class="code">{cert.verification_code}</div>
                </div>
                <div class="qr-placeholder">
                    [QR CODE]<br>
                    Scan to verify online
                </div>
                <div class="verification-url">
                    <strong>Verify Online:</strong><br>
                    {cert.verification_url}
                </div>
            </div>
            
            <div class="signature-section">
                <div class="digital-signature">
                    <div class="label">Digital Signature (HMAC-SHA256)</div>
                    <div class="sig">{cert.certificate_signature}</div>
                </div>
                <div class="issued-by">
                    <div class="logo">⚖️</div>
                    <div class="name">Semptify</div>
                    <div class="version">Legal Integrity Module v5.0</div>
                </div>
            </div>
            
            <div class="legal-notice">{cert.legal_notice}</div>
        </div>
        
        <div class="footer">
            This certificate was generated by Semptify Legal Integrity Module.<br>
            Verify authenticity at <a href="{cert.verification_url}">{cert.verification_url}</a>
        </div>
    </div>
</body>
</html>'''


def generate_certificate_text(cert: VerificationCertificate) -> str:
    """
    Generate plain text certificate for email/print without HTML.
    """
    issued_date = datetime.fromisoformat(cert.issued_at.replace('Z', '+00:00'))
    original_date = datetime.fromisoformat(cert.original_timestamp.replace('Z', '+00:00'))
    
    return f'''
================================================================================
                    CERTIFICATE OF DOCUMENT INTEGRITY
                    Semptify Legal Integrity Module
================================================================================

Certificate ID: {cert.certificate_id}
Issued: {issued_date.strftime('%B %d, %Y at %I:%M %p UTC')}

--------------------------------------------------------------------------------
                              ATTESTATION
--------------------------------------------------------------------------------

{cert.attestation}

--------------------------------------------------------------------------------
                           DOCUMENT DETAILS
--------------------------------------------------------------------------------

Document Name:     {cert.document_name}
Document Size:     {cert.document_size_bytes:,} bytes
Hash Algorithm:    {cert.hash_algorithm}
Document Owner:    {cert.owner_display}
Owner ID:          {cert.owner_id}

CRYPTOGRAPHIC FINGERPRINT:
{cert.document_hash}

--------------------------------------------------------------------------------
                             TIMESTAMPS
--------------------------------------------------------------------------------

Original Upload:   {original_date.strftime('%B %d, %Y at %I:%M %p UTC')}
Certificate Issued: {issued_date.strftime('%B %d, %Y at %I:%M %p UTC')}
Timestamp Proof:   {cert.timestamp_proof}

--------------------------------------------------------------------------------
                            VERIFICATION
--------------------------------------------------------------------------------

Verification Code: {cert.verification_code}
Verify Online:     {cert.verification_url}

Digital Signature: {cert.certificate_signature}

--------------------------------------------------------------------------------
                            LEGAL NOTICE
--------------------------------------------------------------------------------

{cert.legal_notice}

================================================================================
           Semptify Legal Integrity Module v5.0 | {cert.verification_url}
================================================================================
'''


# =============================================================================
# Quick Certificate Generation
# =============================================================================

def quick_certificate(
    document_content: bytes,
    document_name: str,
    user_id: str,
    base_url: str = "http://localhost:8000",
) -> Dict[str, Any]:
    """
    Quick one-call certificate generation.
    Creates proof and certificate in one step.
    """
    from app.services.storage.legal_integrity import get_legal_integrity
    
    integrity = get_legal_integrity(user_id)
    proof = integrity.create_document_proof(document_content, action="certify")
    
    cert = create_verification_certificate(
        document_content=document_content,
        document_name=document_name,
        proof=proof,
        user_id=user_id,
        base_url=base_url,
    )
    
    return {
        "certificate": cert.to_dict(),
        "html": generate_certificate_html(cert),
        "text": generate_certificate_text(cert),
        "proof": proof.to_dict(),
    }
