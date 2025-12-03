"""
Semptify 5.0 - User Service
Handles user persistence, lookup, and provider management.

Solves the "returning user" problem:
1. Where to look for token? → Check user's primary_provider
2. What role to load? → Check user's default_role
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, LinkedProvider
from app.core.database import get_db_session


# =============================================================================
# User CRUD Operations
# =============================================================================

async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by their internal ID."""
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def get_user_by_provider(provider: str, storage_user_id: str) -> Optional[User]:
    """Get user by storage provider identity."""
    from app.core.security import derive_user_id
    user_id = derive_user_id(provider, storage_user_id)
    return await get_user_by_id(user_id)


async def create_user(
    user_id: str,
    provider: str,
    storage_user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    default_role: str = "tenant",
) -> User:
    """Create a new user from storage provider auth."""
    async with get_db_session() as session:
        user = User(
            id=user_id,
            primary_provider=provider,
            storage_user_id=storage_user_id,
            email=email,
            display_name=display_name,
            default_role=default_role,
            created_at=datetime.now(timezone.utc),
            last_login=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def get_or_create_user(
    user_id: str,
    provider: str,
    storage_user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    default_role: str = "tenant",
) -> tuple[User, bool]:
    """
    Get existing user or create new one.
    Returns: (user, created: bool)
    """
    user = await get_user_by_id(user_id)
    if user:
        # Update last login
        async with get_db_session() as session:
            user.last_login = datetime.now(timezone.utc)
            if email and not user.email:
                user.email = email
            if display_name and not user.display_name:
                user.display_name = display_name
            session.add(user)
            await session.commit()
        return user, False
    
    user = await create_user(
        user_id=user_id,
        provider=provider,
        storage_user_id=storage_user_id,
        email=email,
        display_name=display_name,
        default_role=default_role,
    )
    return user, True


async def update_user_role(user_id: str, role: str) -> Optional[User]:
    """Update user's default role preference."""
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.default_role = role
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(user)
        return user


async def update_user_profile(
    user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> Optional[User]:
    """Update user profile info."""
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            if email is not None:
                user.email = email
            if display_name is not None:
                user.display_name = display_name
            if avatar_url is not None:
                user.avatar_url = avatar_url
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(user)
        return user


# =============================================================================
# Linked Providers
# =============================================================================

async def link_provider(
    user_id: str,
    provider: str,
    storage_user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> LinkedProvider:
    """Link an additional storage provider to user's account."""
    async with get_db_session() as session:
        linked = LinkedProvider(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider=provider,
            storage_user_id=storage_user_id,
            email=email,
            display_name=display_name,
            linked_at=datetime.now(timezone.utc),
        )
        session.add(linked)
        await session.commit()
        await session.refresh(linked)
        return linked


async def get_linked_providers(user_id: str) -> list[LinkedProvider]:
    """Get all linked providers for a user."""
    async with get_db_session() as session:
        result = await session.execute(
            select(LinkedProvider)
            .where(LinkedProvider.user_id == user_id)
            .where(LinkedProvider.is_active == True)
        )
        return list(result.scalars().all())


async def unlink_provider(user_id: str, provider: str) -> bool:
    """Unlink a provider from user's account."""
    async with get_db_session() as session:
        result = await session.execute(
            select(LinkedProvider)
            .where(LinkedProvider.user_id == user_id)
            .where(LinkedProvider.provider == provider)
        )
        linked = result.scalar_one_or_none()
        if linked:
            linked.is_active = False
            await session.commit()
            return True
        return False


# =============================================================================
# User Lookup for Returning Users
# =============================================================================

async def get_user_auth_info(user_id: str) -> Optional[dict]:
    """
    Get the info needed to re-authenticate a returning user.
    
    Returns:
        {
            "user_id": "abc123",
            "primary_provider": "google_drive",
            "default_role": "tenant",
            "email": "user@example.com",
            "linked_providers": ["google_drive", "dropbox"]
        }
    """
    user = await get_user_by_id(user_id)
    if not user:
        return None
    
    linked = await get_linked_providers(user_id)
    
    return {
        "user_id": user.id,
        "primary_provider": user.primary_provider,
        "default_role": user.default_role,
        "email": user.email,
        "display_name": user.display_name,
        "linked_providers": [user.primary_provider] + [l.provider for l in linked],
    }
