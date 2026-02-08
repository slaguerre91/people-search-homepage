"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# User Schemas
# ---------------------------------------------------------------------------

from typing import Optional

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: str = Field(..., min_length=5, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    avatar_url: Optional[str] = Field(default=None, max_length=500)

class UserLogin(BaseModel):
    """Schema for user login."""
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

class UserResponse(BaseModel):
    """Schema for user info in API responses."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
# Review Schemas
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    """Schema for creating a review."""
    author: str = Field(..., min_length=1, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=1, max_length=1000)


class ReviewResponse(BaseModel):
    """Schema for review in API responses."""
    id: UUID
    author: str
    rating: int
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Profile Schemas
# ---------------------------------------------------------------------------

class ProfileCreate(BaseModel):
    """Schema for creating a profile."""
    name: str = Field(..., min_length=1, max_length=100)
    company: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=100)
    bio: str = Field(default="", max_length=500)


class ProfileSummary(BaseModel):
    """Lightweight profile for search results."""
    id: UUID
    name: str
    company: str
    role: str
    location: str

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    """Full profile with reviews."""
    id: UUID
    name: str
    company: str
    role: str
    location: str
    bio: str
    created_at: datetime
    reviews: list[ReviewResponse] = []

    model_config = {"from_attributes": True}
