"""
Briefcase Router - Document & Folder Organization System
A digital briefcase for organizing legal documents, evidence, and case files

ALL UPLOADS GO TO VAULT FIRST - briefcase references documents from vault.
"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import os
import io
import json
import shutil
import hashlib
import base64
import zipfile
import uuid

logger = logging.getLogger(__name__)

# Import vault upload service - ALL uploads go through here first
try:
    from app.services.vault_upload_service import get_vault_service
    HAS_VAULT_SERVICE = True
except ImportError:
    HAS_VAULT_SERVICE = False

router = APIRouter(prefix="/api/briefcase", tags=["Briefcase"])

# In-memory storage (in production, use database)
briefcase_data = {
    "folders": {
        "root": {
            "id": "root",
            "name": "My Briefcase",
            "parent_id": None,
            "created_at": datetime.now().isoformat(),
            "color": "#4ade80",
            "icon": "briefcase"
        },
        "extracted": {
            "id": "extracted",
            "name": "📄 Extracted Pages",
            "parent_id": "root",
            "created_at": datetime.now().isoformat(),
            "color": "#f59e0b",
            "icon": "file-export",
            "system": True
        },
        "highlights": {
            "id": "highlights",
            "name": "🖍️ Highlights & Notes",
            "parent_id": "root",
            "created_at": datetime.now().isoformat(),
            "color": "#ec4899",
            "icon": "highlighter",
            "system": True
        },
        "evidence": {
            "id": "evidence",
            "name": "📸 Evidence",
            "parent_id": "root",
            "created_at": datetime.now().isoformat(),
            "color": "#ef4444",
            "icon": "gavel",
            "system": True
        }
    },
    "documents": {},
    "extractions": {},  # Store extracted PDF pages
    "highlights": {},   # Store highlights and notes
    "tags": ["Important", "Evidence", "Lease", "Notice", "Court", "Correspondence", "Financial", "Photos"]
}

# Pydantic models
class FolderCreate(BaseModel):
    name: str
    parent_id: str = "root"
    color: Optional[str] = "#3b82f6"
    icon: Optional[str] = "folder"

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[str] = None

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    starred: Optional[bool] = None


@router.get("/")
async def get_briefcase():
    """Get entire briefcase structure"""
    return {
        "folders": list(briefcase_data["folders"].values()),
        "documents": list(briefcase_data["documents"].values()),
        "tags": briefcase_data["tags"],
        "stats": {
            "total_folders": len(briefcase_data["folders"]),
            "total_documents": len(briefcase_data["documents"]),
            "total_size": sum(d.get("size", 0) for d in briefcase_data["documents"].values())
        }
    }


@router.get("/folder/{folder_id}")
async def get_folder_contents(folder_id: str):
    """Get contents of a specific folder"""
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    folder = briefcase_data["folders"][folder_id]
    
    # Get subfolders
    subfolders = [f for f in briefcase_data["folders"].values() if f.get("parent_id") == folder_id]
    
    # Get documents in this folder
    documents = [d for d in briefcase_data["documents"].values() if d.get("folder_id") == folder_id]
    
    # Get breadcrumb path
    breadcrumb = get_breadcrumb(folder_id)
    
    return {
        "folder": folder,
        "subfolders": subfolders,
        "documents": documents,
        "breadcrumb": breadcrumb
    }


def get_breadcrumb(folder_id: str) -> List[Dict]:
    """Build breadcrumb path from root to folder"""
    breadcrumb = []
    current_id = folder_id
    
    while current_id:
        if current_id in briefcase_data["folders"]:
            folder = briefcase_data["folders"][current_id]
            breadcrumb.insert(0, {"id": folder["id"], "name": folder["name"]})
            current_id = folder.get("parent_id")
        else:
            break
    
    return breadcrumb


@router.post("/folder")
async def create_folder(folder: FolderCreate):
    """Create a new folder"""
    if folder.parent_id != "root" and folder.parent_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Parent folder not found")
    
    folder_id = f"folder_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(folder.name) & 0xFFFF:04x}"
    
    new_folder = {
        "id": folder_id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "color": folder.color,
        "icon": folder.icon,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    briefcase_data["folders"][folder_id] = new_folder
    
    return {"success": True, "folder": new_folder}


@router.put("/folder/{folder_id}")
async def update_folder(folder_id: str, update: FolderUpdate):
    """Update folder properties"""
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if folder_id == "root":
        raise HTTPException(status_code=400, detail="Cannot modify root folder")
    
    folder = briefcase_data["folders"][folder_id]
    
    if update.name is not None:
        folder["name"] = update.name
    if update.color is not None:
        folder["color"] = update.color
    if update.icon is not None:
        folder["icon"] = update.icon
    if update.parent_id is not None:
        # Prevent moving to own child
        if not is_valid_move(folder_id, update.parent_id):
            raise HTTPException(status_code=400, detail="Cannot move folder to its own subfolder")
        folder["parent_id"] = update.parent_id
    
    folder["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "folder": folder}


def is_valid_move(folder_id: str, new_parent_id: str) -> bool:
    """Check if moving folder to new parent is valid (not circular)"""
    if new_parent_id == folder_id:
        return False
    
    current_id = new_parent_id
    while current_id:
        if current_id == folder_id:
            return False
        if current_id in briefcase_data["folders"]:
            current_id = briefcase_data["folders"][current_id].get("parent_id")
        else:
            break
    
    return True


@router.delete("/folder/{folder_id}")
async def delete_folder(folder_id: str, recursive: bool = False):
    """Delete a folder"""
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if folder_id == "root":
        raise HTTPException(status_code=400, detail="Cannot delete root folder")
    
    # Check for contents
    subfolders = [f for f in briefcase_data["folders"].values() if f.get("parent_id") == folder_id]
    documents = [d for d in briefcase_data["documents"].values() if d.get("folder_id") == folder_id]
    
    if (subfolders or documents) and not recursive:
        raise HTTPException(
            status_code=400, 
            detail=f"Folder contains {len(subfolders)} folders and {len(documents)} documents. Use recursive=true to delete all."
        )
    
    # Recursive delete
    if recursive:
        delete_folder_recursive(folder_id)
    else:
        del briefcase_data["folders"][folder_id]
    
    return {"success": True, "message": "Folder deleted"}


def delete_folder_recursive(folder_id: str):
    """Recursively delete folder and contents"""
    # Delete subfolders
    subfolders = [f["id"] for f in briefcase_data["folders"].values() if f.get("parent_id") == folder_id]
    for subfolder_id in subfolders:
        delete_folder_recursive(subfolder_id)
    
    # Delete documents
    doc_ids = [d["id"] for d in briefcase_data["documents"].values() if d.get("folder_id") == folder_id]
    for doc_id in doc_ids:
        del briefcase_data["documents"][doc_id]
    
    # Delete folder
    if folder_id in briefcase_data["folders"]:
        del briefcase_data["folders"][folder_id]


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    folder_id: str = Form(default="root"),
    tags: str = Form(default=""),
    notes: str = Form(default=""),
    user_id: str = Form(default="default"),
    access_token: Optional[str] = Form(None, description="Storage provider access token"),
    storage_provider: str = Form("local", description="Storage provider"),
):
    """
    Upload a document to the briefcase.
    
    ALL DOCUMENTS GO TO VAULT FIRST, then referenced from briefcase.
    """
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    content = await file.read()
    
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Determine file type
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    file_type = get_file_type(ext)
    
    # STEP 1: Upload to vault first
    vault_id = None
    vault_path = None
    if HAS_VAULT_SERVICE:
        try:
            vault_service = get_vault_service()
            vault_doc = await vault_service.upload(
                user_id=user_id,
                filename=filename,
                content=content,
                mime_type=file.content_type or "application/octet-stream",
                document_type=file_type,
                tags=tag_list,
                source_module="briefcase",
                access_token=access_token,
                storage_provider=storage_provider,
            )
            vault_id = vault_doc.vault_id
            vault_path = vault_doc.storage_path
            logger.info(f"📁 Document stored in vault: {vault_id}")
        except Exception as e:
            logger.warning(f"Vault upload failed: {e}")
    
    # Generate document ID and hash
    doc_id = vault_id or f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(content) & 0xFFFFFF:06x}"
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    
    # Store document reference in briefcase (not content - that's in vault)
    document = {
        "id": doc_id,
        "vault_id": vault_id,
        "vault_path": vault_path,
        "name": filename,
        "folder_id": folder_id,
        "size": len(content),
        "type": file_type,
        "extension": ext,
        "mime_type": file.content_type,
        "hash": file_hash,
        "tags": tag_list,
        "notes": notes,
        "starred": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        # Only store content locally if vault failed
        "content": base64.b64encode(content).decode('utf-8') if not vault_id else None,
        "in_vault": bool(vault_id),
    }
    
    briefcase_data["documents"][doc_id] = document
    
    # Return without content
    doc_response = {k: v for k, v in document.items() if k != "content"}
    
    return {"success": True, "document": doc_response, "vault_id": vault_id}


def get_file_type(ext: str) -> str:
    """Determine file type category from extension"""
    types = {
        ".pdf": "pdf",
        ".doc": "word", ".docx": "word",
        ".xls": "excel", ".xlsx": "excel",
        ".ppt": "powerpoint", ".pptx": "powerpoint",
        ".txt": "text", ".md": "text", ".rtf": "text",
        ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
        ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
        ".mp4": "video", ".mov": "video", ".avi": "video",
        ".zip": "archive", ".rar": "archive", ".7z": "archive",
        ".html": "web", ".htm": "web",
        ".json": "data", ".xml": "data", ".csv": "data"
    }
    return types.get(ext, "other")


@router.get("/document/{doc_id}")
async def get_document(doc_id: str):
    """Get document metadata"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = briefcase_data["documents"][doc_id]
    # Return without content
    return {k: v for k, v in doc.items() if k != "content"}


@router.get("/document/{doc_id}/download")
async def download_document(
    doc_id: str,
    access_token: Optional[str] = None,
):
    """
    Download a document.
    
    If document is in vault, retrieves from vault storage.
    """
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = briefcase_data["documents"][doc_id]
    
    # Try to get from vault first
    content = None
    if doc.get("in_vault") and doc.get("vault_id") and HAS_VAULT_SERVICE:
        try:
            vault_service = get_vault_service()
            content = await vault_service.get_document_content(
                vault_id=doc["vault_id"],
                access_token=access_token,
            )
        except Exception as e:
            logger.warning(f"Vault download failed: {e}")
    
    # Fall back to local content
    if content is None and doc.get("content"):
        content = base64.b64decode(doc["content"])
    
    if content is None:
        raise HTTPException(status_code=404, detail="Document content not available")
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=doc.get("mime_type", "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename={doc['name']}"}
    )


@router.get("/document/{doc_id}/preview")
async def preview_document(doc_id: str):
    """Get document content for preview (base64)"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = briefcase_data["documents"][doc_id]
    
    return {
        "id": doc_id,
        "name": doc["name"],
        "type": doc["type"],
        "mime_type": doc.get("mime_type"),
        "content": f"data:{doc.get('mime_type', 'application/octet-stream')};base64,{doc['content']}"
    }


@router.put("/document/{doc_id}")
async def update_document(doc_id: str, update: DocumentUpdate):
    """Update document properties"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = briefcase_data["documents"][doc_id]
    
    if update.name is not None:
        doc["name"] = update.name
    if update.folder_id is not None:
        if update.folder_id not in briefcase_data["folders"]:
            raise HTTPException(status_code=404, detail="Target folder not found")
        doc["folder_id"] = update.folder_id
    if update.tags is not None:
        doc["tags"] = update.tags
    if update.notes is not None:
        doc["notes"] = update.notes
    if update.starred is not None:
        doc["starred"] = update.starred
    
    doc["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "document": {k: v for k, v in doc.items() if k != "content"}}


@router.delete("/document/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    del briefcase_data["documents"][doc_id]
    
    return {"success": True, "message": "Document deleted"}


@router.post("/document/{doc_id}/move")
async def move_document(doc_id: str, folder_id: str = Form(...)):
    """Move document to another folder"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Target folder not found")
    
    briefcase_data["documents"][doc_id]["folder_id"] = folder_id
    briefcase_data["documents"][doc_id]["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "message": "Document moved"}


@router.post("/document/{doc_id}/copy")
async def copy_document(doc_id: str, folder_id: str = Form(...)):
    """Copy document to another folder"""
    if doc_id not in briefcase_data["documents"]:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Target folder not found")
    
    original = briefcase_data["documents"][doc_id]
    new_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(original['name']) & 0xFFFF:04x}"
    
    copy = original.copy()
    copy["id"] = new_id
    copy["folder_id"] = folder_id
    copy["name"] = f"Copy of {original['name']}"
    copy["created_at"] = datetime.now().isoformat()
    copy["updated_at"] = datetime.now().isoformat()
    
    briefcase_data["documents"][new_id] = copy
    
    return {"success": True, "document": {k: v for k, v in copy.items() if k != "content"}}


@router.get("/search")
async def search_documents(
    q: str,
    folder_id: Optional[str] = None,
    tags: Optional[str] = None,
    file_type: Optional[str] = None,
    starred: Optional[bool] = None
):
    """Search documents"""
    results = []
    query = q.lower()
    tag_filter = [t.strip() for t in tags.split(",")] if tags else []
    
    for doc in briefcase_data["documents"].values():
        # Text search
        if query:
            name_match = query in doc["name"].lower()
            notes_match = query in doc.get("notes", "").lower()
            tag_match = any(query in t.lower() for t in doc.get("tags", []))
            if not (name_match or notes_match or tag_match):
                continue
        
        # Folder filter
        if folder_id and doc["folder_id"] != folder_id:
            continue
        
        # Tag filter
        if tag_filter:
            if not any(t in doc.get("tags", []) for t in tag_filter):
                continue
        
        # File type filter
        if file_type and doc["type"] != file_type:
            continue
        
        # Starred filter
        if starred is not None and doc.get("starred") != starred:
            continue
        
        results.append({k: v for k, v in doc.items() if k != "content"})
    
    return {"results": results, "count": len(results)}


@router.get("/starred")
async def get_starred_documents():
    """Get all starred documents"""
    starred = [
        {k: v for k, v in doc.items() if k != "content"}
        for doc in briefcase_data["documents"].values()
        if doc.get("starred")
    ]
    return {"documents": starred, "count": len(starred)}


@router.get("/recent")
async def get_recent_documents(limit: int = 10):
    """Get recently added/updated documents"""
    docs = list(briefcase_data["documents"].values())
    docs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    recent = [
        {k: v for k, v in doc.items() if k != "content"}
        for doc in docs[:limit]
    ]
    return {"documents": recent, "count": len(recent)}


@router.get("/tags")
async def get_all_tags():
    """Get all available tags"""
    # Get predefined tags plus any custom tags used
    all_tags = set(briefcase_data["tags"])
    for doc in briefcase_data["documents"].values():
        all_tags.update(doc.get("tags", []))
    
    return {"tags": sorted(list(all_tags))}


@router.post("/tags")
async def add_tag(tag: str = Form(...)):
    """Add a new tag"""
    if tag not in briefcase_data["tags"]:
        briefcase_data["tags"].append(tag)
    return {"success": True, "tags": briefcase_data["tags"]}


@router.post("/export")
async def export_folder(folder_id: str = Form(default="root")):
    """Export folder as ZIP file"""
    if folder_id not in briefcase_data["folders"]:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        export_folder_to_zip(zip_file, folder_id, "")
    
    zip_buffer.seek(0)
    folder_name = briefcase_data["folders"][folder_id]["name"]
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={folder_name}.zip"}
    )


def export_folder_to_zip(zip_file: zipfile.ZipFile, folder_id: str, path: str):
    """Recursively add folder contents to ZIP"""
    folder = briefcase_data["folders"][folder_id]
    folder_path = os.path.join(path, folder["name"]) if path else folder["name"]
    
    # Add documents
    for doc in briefcase_data["documents"].values():
        if doc["folder_id"] == folder_id:
            content = base64.b64decode(doc["content"])
            zip_file.writestr(os.path.join(folder_path, doc["name"]), content)
    
    # Add subfolders
    for subfolder in briefcase_data["folders"].values():
        if subfolder.get("parent_id") == folder_id:
            export_folder_to_zip(zip_file, subfolder["id"], folder_path)


@router.get("/stats")
async def get_briefcase_stats():
    """Get detailed briefcase statistics"""
    docs = list(briefcase_data["documents"].values())

    # Type distribution
    type_counts = {}
    for doc in docs:
        t = doc["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    # Tag distribution
    tag_counts = {}
    for doc in docs:
        for tag in doc.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Folder sizes
    folder_sizes = {}
    for doc in docs:
        fid = doc["folder_id"]
        folder_sizes[fid] = folder_sizes.get(fid, 0) + doc.get("size", 0)

    return {
        "total_folders": len(briefcase_data["folders"]),
        "total_documents": len(docs),
        "total_size": sum(d.get("size", 0) for d in docs),
        "starred_count": sum(1 for d in docs if d.get("starred")),
        "type_distribution": type_counts,
        "tag_distribution": tag_counts,
        "folder_sizes": folder_sizes,
        "extractions_count": len(briefcase_data.get("extractions", {})),
        "highlights_count": len(briefcase_data.get("highlights", {}))
    }


# ============ Extracted Pages Storage ============

@router.post("/extraction")
async def save_extraction(
    pdf_name: str = Form(...),
    pages: str = Form(...),  # JSON array of page numbers
    extracted_data: UploadFile = File(None),  # Optional: the actual extracted PDF
    notes: str = Form("")
):
    """Save extracted pages from PDF tools."""
    import json
    
    extraction_id = str(uuid.uuid4())
    page_list = json.loads(pages)
    
    extraction = {
        "id": extraction_id,
        "pdf_name": pdf_name,
        "pages": page_list,
        "page_count": len(page_list),
        "notes": notes,
        "created_at": datetime.now().isoformat(),
        "folder_id": "extracted"
    }
    
    # Save extracted PDF file if provided
    if extracted_data:
        upload_dir = Path("uploads/briefcase/extractions")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / f"{extraction_id}.pdf"
        content = await extracted_data.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        extraction["file_path"] = str(file_path)
        extraction["file_size"] = len(content)
    
    briefcase_data["extractions"][extraction_id] = extraction
    
    return {"success": True, "extraction_id": extraction_id, "extraction": extraction}


@router.get("/extractions")
async def list_extractions():
    """List all saved extractions."""
    extractions = list(briefcase_data.get("extractions", {}).values())
    extractions.sort(key=lambda x: x["created_at"], reverse=True)
    return {"extractions": extractions}


@router.get("/extraction/{extraction_id}")
async def get_extraction(extraction_id: str):
    """Get a specific extraction."""
    if extraction_id not in briefcase_data.get("extractions", {}):
        raise HTTPException(status_code=404, detail="Extraction not found")
    return briefcase_data["extractions"][extraction_id]


@router.delete("/extraction/{extraction_id}")
async def delete_extraction(extraction_id: str):
    """Delete an extraction."""
    if extraction_id not in briefcase_data.get("extractions", {}):
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    extraction = briefcase_data["extractions"][extraction_id]
    
    # Delete file if exists
    if "file_path" in extraction:
        file_path = Path(extraction["file_path"])
        if file_path.exists():
            file_path.unlink()
    
    del briefcase_data["extractions"][extraction_id]
    return {"success": True}


@router.get("/extraction/{extraction_id}/download")
async def download_extraction(extraction_id: str):
    """Download extracted PDF file."""
    if extraction_id not in briefcase_data.get("extractions", {}):
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    extraction = briefcase_data["extractions"][extraction_id]
    if "file_path" not in extraction:
        raise HTTPException(status_code=404, detail="No file associated with this extraction")
    
    file_path = Path(extraction["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"extracted_{extraction['pdf_name']}_pages.pdf"
    )


# ============ Highlights & Notes Storage ============

@router.post("/highlight")
async def save_highlight(
    pdf_name: str = Form(...),
    page_number: int = Form(...),
    color: str = Form(...),
    color_name: str = Form(""),
    text: str = Form(""),
    note: str = Form(""),
    coords: str = Form(None)  # JSON with x, y, width, height
):
    """Save a highlight/annotation from PDF tools."""
    import json
    
    highlight_id = str(uuid.uuid4())
    
    highlight = {
        "id": highlight_id,
        "pdf_name": pdf_name,
        "page_number": page_number,
        "color": color,
        "color_name": color_name,
        "text": text,
        "note": note,
        "coords": json.loads(coords) if coords else None,
        "created_at": datetime.now().isoformat(),
        "folder_id": "highlights"
    }
    
    briefcase_data["highlights"][highlight_id] = highlight
    
    return {"success": True, "highlight_id": highlight_id, "highlight": highlight}


@router.post("/highlights/batch")
async def save_highlights_batch(request: Request):
    """Save multiple highlights at once."""
    data = await request.json()
    highlights = data.get("highlights", [])
    pdf_name = data.get("pdf_name", "Unknown PDF")
    
    saved = []
    for h in highlights:
        highlight_id = str(uuid.uuid4())
        highlight = {
            "id": highlight_id,
            "pdf_name": pdf_name,
            "page_number": h.get("page", 1),
            "color": h.get("color", "#ffff00"),
            "color_name": h.get("colorName", ""),
            "text": h.get("text", ""),
            "note": h.get("note", ""),
            "coords": h.get("coords"),
            "created_at": datetime.now().isoformat(),
            "folder_id": "highlights"
        }
        briefcase_data["highlights"][highlight_id] = highlight
        saved.append(highlight)
    
    return {"success": True, "count": len(saved), "highlights": saved}


@router.get("/highlights")
async def list_highlights(pdf_name: Optional[str] = None, color: Optional[str] = None):
    """List all saved highlights, optionally filtered."""
    highlights = list(briefcase_data.get("highlights", {}).values())
    
    if pdf_name:
        highlights = [h for h in highlights if h["pdf_name"] == pdf_name]
    if color:
        highlights = [h for h in highlights if h["color"] == color]
    
    highlights.sort(key=lambda x: x["created_at"], reverse=True)
    return {"highlights": highlights}


@router.get("/highlight/{highlight_id}")
async def get_highlight(highlight_id: str):
    """Get a specific highlight."""
    if highlight_id not in briefcase_data.get("highlights", {}):
        raise HTTPException(status_code=404, detail="Highlight not found")
    return briefcase_data["highlights"][highlight_id]


@router.delete("/highlight/{highlight_id}")
async def delete_highlight(highlight_id: str):
    """Delete a highlight."""
    if highlight_id not in briefcase_data.get("highlights", {}):
        raise HTTPException(status_code=404, detail="Highlight not found")
    
    del briefcase_data["highlights"][highlight_id]
    return {"success": True}


@router.get("/highlights/by-color")
async def get_highlights_grouped_by_color():
    """Get highlights grouped by color category."""
    color_groups = {}
    
    for highlight in briefcase_data.get("highlights", {}).values():
        color = highlight.get("color_name") or highlight.get("color", "Unknown")
        if color not in color_groups:
            color_groups[color] = []
        color_groups[color].append(highlight)
    
    return {"groups": color_groups}


# ============ Document Annotation API (Footnote Indexing) ============

# In-memory annotation storage (in production, use database)
annotation_data = {
    "annotations": {},
    "global_counter": 0,
    "category_counters": {}
}


class AnnotationCreate(BaseModel):
    document_id: str
    extraction_code: str
    highlight_text: str
    page_number: int
    annotation_note: Optional[str] = None
    position_x: Optional[float] = 0.0
    position_y: Optional[float] = 0.0
    position_width: Optional[float] = 0.0
    position_height: Optional[float] = 0.0
    detection_method: Optional[str] = "MANUAL"
    confidence: Optional[float] = 1.0
    linked_event_id: Optional[str] = None


class AnnotationUpdate(BaseModel):
    annotation_note: Optional[str] = None
    linked_event_id: Optional[str] = None


@router.post("/annotation")
async def create_annotation(annotation: AnnotationCreate):
    """
    Create a new document annotation with auto-numbered footnotes.
    Returns both global footnote number and category-specific number.
    """
    annotation_id = str(uuid.uuid4())
    
    # Increment global counter
    annotation_data["global_counter"] += 1
    global_num = annotation_data["global_counter"]
    
    # Increment category counter
    code = annotation.extraction_code
    if code not in annotation_data["category_counters"]:
        annotation_data["category_counters"][code] = 0
    annotation_data["category_counters"][code] += 1
    category_num = annotation_data["category_counters"][code]
    
    new_annotation = {
        "id": annotation_id,
        "document_id": annotation.document_id,
        "footnote_number": global_num,
        "category_number": category_num,
        "extraction_code": code,
        "marker_id": f"{code}-{category_num}",
        "highlight_text": annotation.highlight_text,
        "annotation_note": annotation.annotation_note,
        "page_number": annotation.page_number,
        "position_x": annotation.position_x,
        "position_y": annotation.position_y,
        "position_width": annotation.position_width,
        "position_height": annotation.position_height,
        "detection_method": annotation.detection_method,
        "confidence": annotation.confidence,
        "linked_event_id": annotation.linked_event_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    annotation_data["annotations"][annotation_id] = new_annotation
    
    return {"success": True, "annotation": new_annotation}


@router.get("/annotations")
async def list_annotations(
    document_id: Optional[str] = None,
    extraction_code: Optional[str] = None,
    page_number: Optional[int] = None
):
    """List annotations with optional filters."""
    annotations = list(annotation_data["annotations"].values())
    
    if document_id:
        annotations = [a for a in annotations if a["document_id"] == document_id]
    if extraction_code:
        annotations = [a for a in annotations if a["extraction_code"] == extraction_code]
    if page_number is not None:
        annotations = [a for a in annotations if a["page_number"] == page_number]
    
    # Sort by footnote number
    annotations.sort(key=lambda x: x["footnote_number"])
    
    return {
        "annotations": annotations,
        "count": len(annotations),
        "global_counter": annotation_data["global_counter"],
        "category_counters": annotation_data["category_counters"]
    }


@router.get("/annotation/{annotation_id}")
async def get_annotation(annotation_id: str):
    """Get a specific annotation."""
    if annotation_id not in annotation_data["annotations"]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation_data["annotations"][annotation_id]


@router.put("/annotation/{annotation_id}")
async def update_annotation(annotation_id: str, update: AnnotationUpdate):
    """Update an annotation's note or linked event."""
    if annotation_id not in annotation_data["annotations"]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    annotation = annotation_data["annotations"][annotation_id]
    
    if update.annotation_note is not None:
        annotation["annotation_note"] = update.annotation_note
    if update.linked_event_id is not None:
        annotation["linked_event_id"] = update.linked_event_id
    
    annotation["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "annotation": annotation}


@router.delete("/annotation/{annotation_id}")
async def delete_annotation(annotation_id: str):
    """Delete an annotation."""
    if annotation_id not in annotation_data["annotations"]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    del annotation_data["annotations"][annotation_id]
    return {"success": True}


@router.post("/annotation/{annotation_id}/link-event")
async def link_annotation_to_event(
    annotation_id: str,
    event_id: str = Form(...)
):
    """Link an annotation to a timeline event."""
    if annotation_id not in annotation_data["annotations"]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    annotation = annotation_data["annotations"][annotation_id]
    annotation["linked_event_id"] = event_id
    annotation["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "annotation": annotation}


@router.get("/annotations/by-document/{document_id}")
async def get_annotations_by_document(document_id: str):
    """Get all annotations for a document, grouped by extraction code."""
    annotations = [
        a for a in annotation_data["annotations"].values()
        if a["document_id"] == document_id
    ]
    
    # Group by extraction code
    grouped = {}
    for ann in annotations:
        code = ann["extraction_code"]
        if code not in grouped:
            grouped[code] = []
        grouped[code].append(ann)
    
    # Sort within each group
    for code in grouped:
        grouped[code].sort(key=lambda x: x["category_number"])
    
    return {
        "document_id": document_id,
        "groups": grouped,
        "total_count": len(annotations)
    }


@router.post("/annotations/reset-counters")
async def reset_annotation_counters(document_id: Optional[str] = Form(None)):
    """
    Reset annotation counters. 
    If document_id is provided, only reset for that document.
    Otherwise reset all counters (use carefully).
    """
    if document_id:
        # Recalculate counters for document
        doc_annotations = [
            a for a in annotation_data["annotations"].values()
            if a["document_id"] == document_id
        ]
        # Return current state without full reset
        return {
            "success": True,
            "document_id": document_id,
            "annotation_count": len(doc_annotations)
        }
    else:
        # Full reset (admin operation)
        annotation_data["global_counter"] = 0
        annotation_data["category_counters"] = {}
        return {"success": True, "message": "All counters reset"}


# ============ Timeline Event Linking API ============

# In-memory timeline events for linking (in production, use database)
timeline_events_data = {}


class TimelineEventCreate(BaseModel):
    title: str
    event_type: str
    event_date: str  # ISO format datetime
    description: Optional[str] = None
    event_date_end: Optional[str] = None
    event_status: Optional[str] = "start"
    parent_event_id: Optional[str] = None
    source_extraction_id: Optional[str] = None
    highlight_color: Optional[str] = None
    urgency: Optional[str] = "normal"
    is_deadline: Optional[bool] = False
    is_evidence: Optional[bool] = False


class TimelineEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_status: Optional[str] = None
    event_date_end: Optional[str] = None
    urgency: Optional[str] = None
    is_deadline: Optional[bool] = None


@router.post("/timeline-event")
async def create_timeline_event(event: TimelineEventCreate):
    """Create a timeline event that can be linked to annotations."""
    event_id = str(uuid.uuid4())
    
    # Determine sequence number if part of event chain
    sequence = 0
    if event.parent_event_id:
        # Count existing children of parent
        children = [e for e in timeline_events_data.values() 
                   if e.get("parent_event_id") == event.parent_event_id]
        sequence = len(children) + 1
    
    new_event = {
        "id": event_id,
        "title": event.title,
        "event_type": event.event_type,
        "event_date": event.event_date,
        "event_date_end": event.event_date_end,
        "description": event.description,
        "event_status": event.event_status,
        "parent_event_id": event.parent_event_id,
        "sequence_number": sequence,
        "source_extraction_id": event.source_extraction_id,
        "highlight_color": event.highlight_color,
        "urgency": event.urgency,
        "is_deadline": event.is_deadline,
        "is_evidence": event.is_evidence,
        "linked_annotations": [],
        "created_at": datetime.now().isoformat()
    }
    
    timeline_events_data[event_id] = new_event
    
    return {"success": True, "event": new_event}


@router.get("/timeline-events")
async def list_timeline_events(
    event_type: Optional[str] = None,
    event_status: Optional[str] = None,
    is_deadline: Optional[bool] = None,
    parent_event_id: Optional[str] = None
):
    """List timeline events with optional filters."""
    events = list(timeline_events_data.values())
    
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]
    if event_status:
        events = [e for e in events if e.get("event_status") == event_status]
    if is_deadline is not None:
        events = [e for e in events if e.get("is_deadline") == is_deadline]
    if parent_event_id:
        events = [e for e in events if e.get("parent_event_id") == parent_event_id]
    
    # Sort by date
    events.sort(key=lambda x: x.get("event_date", ""))
    
    return {"events": events, "count": len(events)}


@router.get("/timeline-event/{event_id}")
async def get_timeline_event(event_id: str):
    """Get a timeline event with its linked annotations."""
    if event_id not in timeline_events_data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = timeline_events_data[event_id]
    
    # Get linked annotations
    linked_annotations = [
        a for a in annotation_data["annotations"].values()
        if a.get("linked_event_id") == event_id
    ]
    
    return {
        "event": event,
        "linked_annotations": linked_annotations
    }


@router.put("/timeline-event/{event_id}")
async def update_timeline_event(event_id: str, update: TimelineEventUpdate):
    """Update a timeline event."""
    if event_id not in timeline_events_data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = timeline_events_data[event_id]
    
    if update.title is not None:
        event["title"] = update.title
    if update.description is not None:
        event["description"] = update.description
    if update.event_status is not None:
        event["event_status"] = update.event_status
    if update.event_date_end is not None:
        event["event_date_end"] = update.event_date_end
    if update.urgency is not None:
        event["urgency"] = update.urgency
    if update.is_deadline is not None:
        event["is_deadline"] = update.is_deadline
    
    event["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "event": event}


@router.delete("/timeline-event/{event_id}")
async def delete_timeline_event(event_id: str):
    """Delete a timeline event and unlink associated annotations."""
    if event_id not in timeline_events_data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Unlink annotations
    for ann in annotation_data["annotations"].values():
        if ann.get("linked_event_id") == event_id:
            ann["linked_event_id"] = None
    
    del timeline_events_data[event_id]
    return {"success": True}


@router.get("/timeline-event/{event_id}/chain")
async def get_event_chain(event_id: str):
    """
    Get an event chain (linked events: start→continued→finish).
    Returns the full chain from root to all descendants.
    """
    if event_id not in timeline_events_data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = timeline_events_data[event_id]
    
    # Find root of chain
    root_id = event_id
    while timeline_events_data.get(root_id, {}).get("parent_event_id"):
        root_id = timeline_events_data[root_id]["parent_event_id"]
    
    # Build chain from root
    def get_descendants(parent_id):
        children = [
            e for e in timeline_events_data.values()
            if e.get("parent_event_id") == parent_id
        ]
        children.sort(key=lambda x: x.get("sequence_number", 0))
        
        result = []
        for child in children:
            result.append({
                "event": child,
                "children": get_descendants(child["id"])
            })
        return result
    
    root_event = timeline_events_data.get(root_id)
    
    return {
        "root": root_event,
        "chain": get_descendants(root_id),
        "total_in_chain": sum(1 for e in timeline_events_data.values() 
                             if e.get("parent_event_id") == root_id or e["id"] == root_id)
    }


@router.post("/timeline-event/from-annotation/{annotation_id}")
async def create_event_from_annotation(annotation_id: str):
    """
    Create a timeline event from an annotation's highlight.
    Auto-suggests event details based on extraction code.
    """
    if annotation_id not in annotation_data["annotations"]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    annotation = annotation_data["annotations"][annotation_id]
    
    # Map extraction codes to event types
    code_to_type = {
        "DT": "date",
        "DL": "deadline",
        "TL": "timeline",
        "EV": "event",
        "PT": "party",
        "LG": "legal",
        "WS": "witness",
        "VL": "violation"
    }
    
    event_type = code_to_type.get(annotation["extraction_code"], "note")
    is_deadline = annotation["extraction_code"] in ["DL", "DT"]
    urgency = "high" if annotation["extraction_code"] == "DL" else "normal"
    
    event_id = str(uuid.uuid4())
    
    new_event = {
        "id": event_id,
        "title": annotation["highlight_text"][:100],
        "event_type": event_type,
        "event_date": datetime.now().isoformat(),
        "description": annotation.get("annotation_note"),
        "event_status": "start",
        "source_extraction_id": annotation["marker_id"],
        "highlight_color": annotation["extraction_code"].lower(),
        "urgency": urgency,
        "is_deadline": is_deadline,
        "is_evidence": False,
        "linked_annotations": [annotation_id],
        "created_at": datetime.now().isoformat()
    }
    
    timeline_events_data[event_id] = new_event
    
    # Link annotation back to event
    annotation["linked_event_id"] = event_id
    annotation["updated_at"] = datetime.now().isoformat()
    
    return {"success": True, "event": new_event, "annotation_linked": True}


# ============ Extraction Code Reference ============

@router.get("/extraction-codes")
async def get_extraction_codes():
    """Get the complete list of extraction codes with colors and icons."""
    codes = {
        "DT": {"name": "Dates & Deadlines", "color": "#fbbf24", "icon": "📅", "category": "date"},
        "PT": {"name": "Parties & Names", "color": "#3b82f6", "icon": "👤", "category": "party"},
        "$": {"name": "Money & Amounts", "color": "#10b981", "icon": "💰", "category": "amount"},
        "AD": {"name": "Addresses & Locations", "color": "#8b5cf6", "icon": "📍", "category": "address"},
        "LG": {"name": "Legal Terms & Citations", "color": "#ef4444", "icon": "⚖️", "category": "legal"},
        "NT": {"name": "Notes & Footnotes", "color": "#f97316", "icon": "📝", "category": "note"},
        "FM": {"name": "Form Field Data", "color": "#ec4899", "icon": "📋", "category": "form"},
        "EV": {"name": "Events & Actions", "color": "#06b6d4", "icon": "📆", "category": "event"},
        "DL": {"name": "Critical Deadline", "color": "#dc2626", "icon": "🚨", "category": "deadline"},
        "WS": {"name": "Witness/Testimony", "color": "#84cc16", "icon": "👁️", "category": "witness"},
        "VL": {"name": "Violation/Issue", "color": "#f43f5e", "icon": "⚠️", "category": "violation"},
        "ED": {"name": "Evidence Markers", "color": "#14b8a6", "icon": "🔍", "category": "evidence"},
        "QT": {"name": "Quoted Text", "color": "#a855f7", "icon": "💬", "category": "quote"},
        "TL": {"name": "Timeline Key Dates", "color": "#0ea5e9", "icon": "🕐", "category": "timeline"}
    }
    return {"codes": codes}


@router.get("/event-statuses")
async def get_event_statuses():
    """Get the complete list of event statuses with descriptions."""
    statuses = {
        "start": {"description": "Event initiates a process", "examples": "Lease signing, notice served"},
        "continued": {"description": "Event continues/extends process", "examples": "Lease renewal, payment plan"},
        "finish": {"description": "Event concludes process", "examples": "Case closed, eviction complete"},
        "reported": {"description": "Issue/violation reported", "examples": "Maintenance request, complaint"},
        "invited": {"description": "Meeting/hearing scheduled", "examples": "Court date, mediation"},
        "attended": {"description": "Event was attended", "examples": "Hearing appearance"},
        "missed": {"description": "Event was missed/no-show", "examples": "Missed court date"},
        "served": {"description": "Document delivered", "examples": "Notice served"},
        "received": {"description": "Document received", "examples": "Response received"},
        "filed": {"description": "Document filed", "examples": "Court filing"},
        "responded": {"description": "Response submitted", "examples": "Answer filed"},
        "pending": {"description": "Awaiting action/decision", "examples": "Pending ruling"},
        "resolved": {"description": "Issue resolved", "examples": "Complaint resolved"},
        "escalated": {"description": "Issue escalated", "examples": "Appeal filed"},
        "used": {"description": "Evidence used in proceeding", "examples": "Document entered as exhibit"}
    }
    return {"statuses": statuses}