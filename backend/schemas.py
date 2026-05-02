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
    author: Optional[str] = Field(default=None, max_length=100)
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


class LinkedInReviewCreate(BaseModel):
    """Schema for creating a saved profile and review from LinkedIn search."""
    profile: ProfileCreate
    review: ReviewCreate
    existing_profile_id: Optional[UUID] = None


class ProfileSummary(BaseModel):
    """Lightweight profile for search results."""
    id: UUID
    name: str
    company: str
    role: str
    location: str
    review_count: int
    average_rating: Optional[float] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    verification_status: str = "unverified"

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    """Full profile with reviews."""
    id: UUID
    name: str
    company: str
    role: str
    location: str
    bio: str
    avatar_url: Optional[str] = None
    is_verified: bool = False
    verification_status: str = "unverified"
    verified_at: Optional[datetime] = None
    total_review_score: int
    review_count: int
    average_rating: Optional[float] = None
    created_at: datetime
    reviews: list[ReviewResponse] = []

    model_config = {"from_attributes": True}


class VerificationStatusResponse(BaseModel):
    """Current user's leader profile verification status."""
    has_verified_profile: bool
    profile: Optional[ProfileSummary] = None


class ProfileVerificationResponse(BaseModel):
    """Response after a leader profile verification submission."""
    id: UUID
    profile_id: UUID
    profile_photo_url: str
    badge_photo_url: str
    status: str
    created_at: datetime
    profile: ProfileResponse

    model_config = {"from_attributes": True}
