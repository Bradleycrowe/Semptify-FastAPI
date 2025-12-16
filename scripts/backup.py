#!/usr/bin/env python3
"""
Semptify Database Backup Script

Creates timestamped backups of the database and uploads directory.
Supports SQLite and PostgreSQL.

Usage:
    python scripts/backup.py                    # Create backup
    python scripts/backup.py --restore latest   # Restore latest backup
    python scripts/backup.py --list             # List available backups
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
BACKUP_DIR = Path("backups")
UPLOADS_DIR = Path("uploads")
DATA_DIR = Path("data")
SQLITE_DB = Path("semptify.db")

def get_timestamp():
    """Get formatted timestamp for backup naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def backup_sqlite():
    """Backup SQLite database."""
    if not SQLITE_DB.exists():
        print(f"SQLite database not found: {SQLITE_DB}")
        return None
    
    timestamp = get_timestamp()
    backup_path = BACKUP_DIR / f"semptify_sqlite_{timestamp}.db"
    
    print(f"Backing up SQLite database to {backup_path}...")
    shutil.copy2(SQLITE_DB, backup_path)
    print(f"✓ SQLite backup created: {backup_path}")
    return backup_path

def backup_postgresql(db_url: str):
    """Backup PostgreSQL database using pg_dump."""
    timestamp = get_timestamp()
    backup_path = BACKUP_DIR / f"semptify_postgres_{timestamp}.sql"
    
    # Parse connection string
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    import re
    match = re.match(r'postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if not match:
        print(f"Invalid PostgreSQL URL format")
        return None
    
    user, password, host, port, dbname = match.groups()
    
    print(f"Backing up PostgreSQL database to {backup_path}...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    try:
        result = subprocess.run([
            'pg_dump',
            '-h', host,
            '-p', port,
            '-U', user,
            '-d', dbname,
            '-f', str(backup_path),
            '--no-owner',
            '--no-acl',
        ], env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"pg_dump error: {result.stderr}")
            return None
        
        print(f"✓ PostgreSQL backup created: {backup_path}")
        return backup_path
    except FileNotFoundError:
        print("pg_dump not found. Install PostgreSQL client tools.")
        return None

def backup_uploads():
    """Backup uploads directory."""
    if not UPLOADS_DIR.exists():
        print(f"Uploads directory not found: {UPLOADS_DIR}")
        return None
    
    timestamp = get_timestamp()
    backup_path = BACKUP_DIR / f"semptify_uploads_{timestamp}.tar.gz"
    
    print(f"Backing up uploads to {backup_path}...")
    
    # Create tar.gz archive
    shutil.make_archive(
        str(backup_path).replace('.tar.gz', ''),
        'gztar',
        root_dir='.',
        base_dir='uploads'
    )
    
    print(f"✓ Uploads backup created: {backup_path}")
    return backup_path

def list_backups():
    """List available backups."""
    ensure_backup_dir()
    
    backups = sorted(BACKUP_DIR.glob("semptify_*"), reverse=True)
    
    if not backups:
        print("No backups found.")
        return
    
    print("\nAvailable backups:")
    print("-" * 60)
    
    for backup in backups:
        size = backup.stat().st_size
        size_str = f"{size / 1024 / 1024:.2f} MB" if size > 1024*1024 else f"{size / 1024:.2f} KB"
        mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {backup.name:<45} {size_str:>10}  {mtime}")
    
    print("-" * 60)
    print(f"Total: {len(backups)} backup(s)")

def restore_sqlite(backup_path: Path):
    """Restore SQLite database from backup."""
    if not backup_path.exists():
        print(f"Backup not found: {backup_path}")
        return False
    
    # Create backup of current database before restore
    if SQLITE_DB.exists():
        pre_restore_backup = BACKUP_DIR / f"pre_restore_{get_timestamp()}.db"
        shutil.copy2(SQLITE_DB, pre_restore_backup)
        print(f"✓ Pre-restore backup created: {pre_restore_backup}")
    
    print(f"Restoring SQLite database from {backup_path}...")
    shutil.copy2(backup_path, SQLITE_DB)
    print(f"✓ Database restored from {backup_path}")
    return True

def get_latest_backup(prefix: str) -> Path | None:
    """Get the most recent backup matching prefix."""
    ensure_backup_dir()
    backups = sorted(BACKUP_DIR.glob(f"{prefix}*"), reverse=True)
    return backups[0] if backups else None

def main():
    parser = argparse.ArgumentParser(description="Semptify Database Backup Tool")
    parser.add_argument('--restore', metavar='BACKUP', help='Restore from backup (use "latest" for most recent)')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--db-url', default=os.getenv('DATABASE_URL', ''), help='Database URL')
    parser.add_argument('--uploads-only', action='store_true', help='Only backup uploads directory')
    parser.add_argument('--db-only', action='store_true', help='Only backup database')
    
    args = parser.parse_args()
    
    ensure_backup_dir()
    
    # List backups
    if args.list:
        list_backups()
        return
    
    # Restore
    if args.restore:
        if args.restore == 'latest':
            backup_path = get_latest_backup('semptify_sqlite_')
            if not backup_path:
                print("No SQLite backups found.")
                sys.exit(1)
        else:
            backup_path = Path(args.restore)
        
        if restore_sqlite(backup_path):
            print("\n✓ Restore completed successfully!")
        else:
            sys.exit(1)
        return
    
    # Create backup
    print("=" * 60)
    print("Semptify Backup")
    print("=" * 60)
    
    db_url = args.db_url or os.getenv('DATABASE_URL', '')
    
    if not args.uploads_only:
        if 'postgresql' in db_url:
            backup_postgresql(db_url)
        else:
            backup_sqlite()
    
    if not args.db_only:
        backup_uploads()
    
    print("\n✓ Backup completed!")
    print(f"  Backups stored in: {BACKUP_DIR.absolute()}")

if __name__ == "__main__":
    main()
