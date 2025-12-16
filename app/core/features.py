"""
Feature Flags System for Semptify.

Provides runtime feature toggling without code deployments.

Usage:
    from app.core.features import features, Feature
    
    # Check if feature is enabled
    if await features.is_enabled(Feature.AI_COPILOT):
        # Use AI features
        pass
    
    # Decorator for feature-gated endpoints
    @require_feature(Feature.BETA_DASHBOARD)
    async def beta_dashboard():
        ...
    
    # User-specific feature check
    if await features.is_enabled_for_user(Feature.PREMIUM_EXPORT, user_id):
        # Premium feature
        pass
"""

import json
import logging
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Feature(str, Enum):
    """
    Feature flags enumeration.
    Add new features here as the application grows.
    """
    
    # Core Features
    AI_COPILOT = "ai_copilot"
    AI_DOCUMENT_ANALYSIS = "ai_document_analysis"
    AI_LEGAL_ADVICE = "ai_legal_advice"
    
    # Document Features
    DOCUMENT_OCR = "document_ocr"
    DOCUMENT_SIGNING = "document_signing"
    BULK_UPLOAD = "bulk_upload"
    
    # Legal Tools
    COURT_FORMS = "court_forms"
    COMPLAINT_WIZARD = "complaint_wizard"
    EVICTION_DEFENSE = "eviction_defense"
    
    # Premium Features
    PREMIUM_EXPORT = "premium_export"
    PREMIUM_TEMPLATES = "premium_templates"
    UNLIMITED_STORAGE = "unlimited_storage"
    
    # Beta Features
    BETA_DASHBOARD = "beta_dashboard"
    BETA_TIMELINE_V2 = "beta_timeline_v2"
    BETA_MESH_NETWORK = "beta_mesh_network"
    
    # Infrastructure
    REDIS_CACHE = "redis_cache"
    DISTRIBUTED_MESH = "distributed_mesh"
    WEBSOCKET_EVENTS = "websocket_events"
    
    # Security
    TWO_FACTOR_AUTH = "two_factor_auth"
    AUDIT_LOGGING = "audit_logging"
    RATE_LIMITING = "rate_limiting"
    
    # Experimental
    EXPERIMENTAL_AI_MODEL = "experimental_ai_model"
    EXPERIMENTAL_UI = "experimental_ui"


class FeatureConfig:
    """Configuration for a single feature flag."""
    
    def __init__(
        self,
        enabled: bool = False,
        rollout_percentage: int = 100,
        allowed_users: list[str] | None = None,
        denied_users: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.enabled = enabled
        self.rollout_percentage = rollout_percentage
        self.allowed_users = allowed_users or []
        self.denied_users = denied_users or []
        self.start_date = start_date
        self.end_date = end_date
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "rollout_percentage": self.rollout_percentage,
            "allowed_users": self.allowed_users,
            "denied_users": self.denied_users,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureConfig":
        return cls(
            enabled=data.get("enabled", False),
            rollout_percentage=data.get("rollout_percentage", 100),
            allowed_users=data.get("allowed_users", []),
            denied_users=data.get("denied_users", []),
            start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            metadata=data.get("metadata", {}),
        )


# Default feature configurations
DEFAULT_FEATURES: dict[Feature, FeatureConfig] = {
    # Core - enabled by default
    Feature.AI_COPILOT: FeatureConfig(enabled=True),
    Feature.AI_DOCUMENT_ANALYSIS: FeatureConfig(enabled=True),
    Feature.AI_LEGAL_ADVICE: FeatureConfig(enabled=True),
    
    # Documents - enabled
    Feature.DOCUMENT_OCR: FeatureConfig(enabled=True),
    Feature.DOCUMENT_SIGNING: FeatureConfig(enabled=False),  # Coming soon
    Feature.BULK_UPLOAD: FeatureConfig(enabled=True),
    
    # Legal Tools - enabled
    Feature.COURT_FORMS: FeatureConfig(enabled=True),
    Feature.COMPLAINT_WIZARD: FeatureConfig(enabled=True),
    Feature.EVICTION_DEFENSE: FeatureConfig(enabled=True),
    
    # Premium - disabled by default
    Feature.PREMIUM_EXPORT: FeatureConfig(enabled=False),
    Feature.PREMIUM_TEMPLATES: FeatureConfig(enabled=False),
    Feature.UNLIMITED_STORAGE: FeatureConfig(enabled=False),
    
    # Beta - gradual rollout
    Feature.BETA_DASHBOARD: FeatureConfig(enabled=True, rollout_percentage=50),
    Feature.BETA_TIMELINE_V2: FeatureConfig(enabled=True, rollout_percentage=25),
    Feature.BETA_MESH_NETWORK: FeatureConfig(enabled=True, rollout_percentage=10),
    
    # Infrastructure
    Feature.REDIS_CACHE: FeatureConfig(enabled=True),
    Feature.DISTRIBUTED_MESH: FeatureConfig(enabled=True),
    Feature.WEBSOCKET_EVENTS: FeatureConfig(enabled=True),
    
    # Security - enabled
    Feature.TWO_FACTOR_AUTH: FeatureConfig(enabled=False),  # Coming soon
    Feature.AUDIT_LOGGING: FeatureConfig(enabled=True),
    Feature.RATE_LIMITING: FeatureConfig(enabled=True),
    
    # Experimental - disabled
    Feature.EXPERIMENTAL_AI_MODEL: FeatureConfig(enabled=False),
    Feature.EXPERIMENTAL_UI: FeatureConfig(enabled=False),
}


class FeatureFlagManager:
    """
    Manages feature flags with file-based persistence.
    
    Features can be configured via:
    1. Default values (in code)
    2. Configuration file (features.json)
    3. Environment variables (FEATURE_<NAME>=true/false)
    """
    
    def __init__(self):
        self._features: dict[Feature, FeatureConfig] = {}
        self._config_file = Path("data/features.json")
        self._loaded = False
    
    def _ensure_loaded(self) -> None:
        """Load feature configuration if not already loaded."""
        if self._loaded:
            return
        
        # Start with defaults
        self._features = {k: FeatureConfig(**v.to_dict()) for k, v in DEFAULT_FEATURES.items()}
        
        # Override from config file
        self._load_from_file()
        
        # Override from environment
        self._load_from_env()
        
        self._loaded = True
        logger.info("Feature flags loaded: %d features configured", len(self._features))
    
    def _load_from_file(self) -> None:
        """Load feature configuration from JSON file."""
        if not self._config_file.exists():
            return
        
        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for feature_name, config_data in data.items():
                try:
                    feature = Feature(feature_name)
                    self._features[feature] = FeatureConfig.from_dict(config_data)
                except ValueError:
                    logger.warning("Unknown feature in config: %s", feature_name)
        except Exception as e:
            logger.error("Failed to load feature config: %s", e)
    
    def _load_from_env(self) -> None:
        """Load feature overrides from environment variables."""
        import os
        
        for feature in Feature:
            env_key = f"FEATURE_{feature.value.upper()}"
            env_value = os.environ.get(env_key)
            
            if env_value is not None:
                enabled = env_value.lower() in ("true", "1", "yes", "on")
                if feature in self._features:
                    self._features[feature].enabled = enabled
                else:
                    self._features[feature] = FeatureConfig(enabled=enabled)
                logger.debug("Feature %s set from env: %s", feature.value, enabled)
    
    def save(self) -> None:
        """Save current configuration to file."""
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            feature.value: config.to_dict()
            for feature, config in self._features.items()
        }
        
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info("Feature configuration saved to %s", self._config_file)
    
    async def is_enabled(self, feature: Feature) -> bool:
        """Check if a feature is globally enabled."""
        self._ensure_loaded()
        
        config = self._features.get(feature)
        if not config:
            return False
        
        if not config.enabled:
            return False
        
        # Check date restrictions
        now = datetime.utcnow()
        if config.start_date and now < config.start_date:
            return False
        if config.end_date and now > config.end_date:
            return False
        
        return True
    
    async def is_enabled_for_user(self, feature: Feature, user_id: str) -> bool:
        """Check if a feature is enabled for a specific user."""
        self._ensure_loaded()
        
        config = self._features.get(feature)
        if not config:
            return False
        
        # Check if user is explicitly denied
        if user_id in config.denied_users:
            return False
        
        # Check if user is explicitly allowed
        if user_id in config.allowed_users:
            return config.enabled
        
        # Check basic enabled status
        if not await self.is_enabled(feature):
            return False
        
        # Check rollout percentage (deterministic based on user_id)
        if config.rollout_percentage < 100:
            user_hash = hash(f"{feature.value}:{user_id}") % 100
            if user_hash >= config.rollout_percentage:
                return False
        
        return True
    
    def get_config(self, feature: Feature) -> FeatureConfig | None:
        """Get configuration for a feature."""
        self._ensure_loaded()
        return self._features.get(feature)
    
    def set_enabled(self, feature: Feature, enabled: bool) -> None:
        """Enable or disable a feature."""
        self._ensure_loaded()
        
        if feature in self._features:
            self._features[feature].enabled = enabled
        else:
            self._features[feature] = FeatureConfig(enabled=enabled)
        
        logger.info("Feature %s set to %s", feature.value, enabled)
    
    def set_rollout(self, feature: Feature, percentage: int) -> None:
        """Set rollout percentage for a feature."""
        self._ensure_loaded()
        
        if feature in self._features:
            self._features[feature].rollout_percentage = max(0, min(100, percentage))
        else:
            self._features[feature] = FeatureConfig(enabled=True, rollout_percentage=percentage)
    
    def add_user_to_allowlist(self, feature: Feature, user_id: str) -> None:
        """Add user to feature allowlist."""
        self._ensure_loaded()
        
        if feature in self._features:
            if user_id not in self._features[feature].allowed_users:
                self._features[feature].allowed_users.append(user_id)
    
    def remove_user_from_allowlist(self, feature: Feature, user_id: str) -> None:
        """Remove user from feature allowlist."""
        self._ensure_loaded()
        
        if feature in self._features:
            if user_id in self._features[feature].allowed_users:
                self._features[feature].allowed_users.remove(user_id)
    
    async def get_all_flags(self, user_id: str | None = None) -> dict[str, bool]:
        """Get all feature flags and their status."""
        self._ensure_loaded()
        
        result = {}
        for feature in Feature:
            if user_id:
                result[feature.value] = await self.is_enabled_for_user(feature, user_id)
            else:
                result[feature.value] = await self.is_enabled(feature)
        
        return result
    
    async def get_status(self) -> dict[str, Any]:
        """Get feature flags status summary."""
        self._ensure_loaded()
        
        enabled_count = sum(1 for f in Feature if await self.is_enabled(f))
        
        return {
            "total_features": len(Feature),
            "enabled_features": enabled_count,
            "disabled_features": len(Feature) - enabled_count,
            "config_file": str(self._config_file),
            "config_exists": self._config_file.exists(),
        }


# Global feature flag manager
features = FeatureFlagManager()


def require_feature(feature: Feature):
    """
    Decorator to require a feature flag for an endpoint.
    
    Usage:
        @router.get("/beta-feature")
        @require_feature(Feature.BETA_DASHBOARD)
        async def beta_endpoint():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not await features.is_enabled(feature):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="This feature is not currently available",
                )
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def require_feature_for_user(feature: Feature, user_id_param: str = "user_id"):
    """
    Decorator to require a feature flag for a specific user.
    
    Usage:
        @router.get("/premium-feature")
        @require_feature_for_user(Feature.PREMIUM_EXPORT, user_id_param="current_user_id")
        async def premium_endpoint(current_user_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            user_id = kwargs.get(user_id_param)
            
            if not user_id or not await features.is_enabled_for_user(feature, user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This feature is not available for your account",
                )
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator
