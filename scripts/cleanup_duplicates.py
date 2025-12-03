"""
Script to remove duplicate documents from the index.
Keeps the first (earliest) document for each unique file_hash per user.
Also cleans up orphaned files.
"""
import json
import os
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
INDEX_FILE = BASE_DIR / "data" / "documents" / "index.json"
DOCS_DIR = BASE_DIR / "data" / "documents"


def load_index():
    """Load the document index."""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_index(index):
    """Save the document index."""
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, default=str)


def cleanup_duplicates():
    """Remove duplicate documents, keeping the earliest upload for each hash."""
    index = load_index()
    
    print(f"📊 Starting with {len(index)} documents")
    
    # Group documents by (user_id, file_hash)
    hash_groups: dict[tuple[str, str], list] = {}
    for doc_id, doc in index.items():
        key = (doc.get("user_id", "unknown"), doc.get("file_hash", ""))
        if key not in hash_groups:
            hash_groups[key] = []
        hash_groups[key].append((doc_id, doc))
    
    # Find duplicates
    duplicates_to_remove = []
    kept_docs = {}
    
    for (user_id, file_hash), docs in hash_groups.items():
        if len(docs) > 1:
            # Sort by uploaded_at, keep earliest
            docs_sorted = sorted(docs, key=lambda x: x[1].get("uploaded_at", ""))
            
            # Keep the first one
            kept_id, kept_doc = docs_sorted[0]
            kept_docs[kept_id] = kept_doc
            
            # Mark others for removal
            for doc_id, doc in docs_sorted[1:]:
                duplicates_to_remove.append((doc_id, doc))
                print(f"  🗑️  Removing duplicate: {doc.get('filename')} (hash: {file_hash[:8]}...)")
        else:
            # Only one doc with this hash - keep it
            doc_id, doc = docs[0]
            kept_docs[doc_id] = doc
    
    print(f"\n📋 Summary:")
    print(f"   - Documents to keep: {len(kept_docs)}")
    print(f"   - Duplicates to remove: {len(duplicates_to_remove)}")
    
    # Remove duplicate files from disk
    files_removed = 0
    for doc_id, doc in duplicates_to_remove:
        storage_path = doc.get("storage_path")
        if storage_path:
            full_path = BASE_DIR / storage_path
            if full_path.exists():
                try:
                    os.remove(full_path)
                    files_removed += 1
                except Exception as e:
                    print(f"   ⚠️  Could not remove file {full_path}: {e}")
    
    print(f"   - Files removed from disk: {files_removed}")
    
    # Save cleaned index
    save_index(kept_docs)
    print(f"\n✅ Cleanup complete! Index now has {len(kept_docs)} unique documents")
    
    return len(duplicates_to_remove)


if __name__ == "__main__":
    cleanup_duplicates()
