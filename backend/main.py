"""People Search API — FastAPI backend with PostgreSQL database."""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from uuid import UUID

from database import get_db, engine, Base
from models import Profile, Review
from schemas import (
    ProfileCreate, ProfileResponse, ProfileSummary,
    ReviewCreate, ReviewResponse
)

app = FastAPI(title="People Search API", version="0.2.0")

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Create tables on startup (for dev convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/search", response_model=list[ProfileSummary])
async def search_people(
    q: str = Query(default="", max_length=100),
    db: AsyncSession = Depends(get_db)
):
    """Search profiles by name, role, or location."""
    query = q.strip().lower()
    
    if not query:
        # Return all profiles
        result = await db.execute(select(Profile))
        profiles = result.scalars().all()
    else:
        # Filter by name, role, or location (case-insensitive)
        result = await db.execute(
            select(Profile).where(
                or_(
                    Profile.name.ilike(f"%{query}%"),
                    Profile.role.ilike(f"%{query}%"),
                    Profile.location.ilike(f"%{query}%")
                )
            )
        )
        profiles = result.scalars().all()
    
    return profiles


@app.post("/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new profile."""
    profile = Profile(**data.model_dump())
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@app.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get full profile with reviews."""
    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.reviews))
        .where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile


@app.post("/profiles/{profile_id}/reviews", response_model=ReviewResponse, status_code=201)
async def add_review(
    profile_id: UUID,
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a review to a profile."""
    # Check profile exists
    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    review = Review(profile_id=profile_id, **data.model_dump())
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return review


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

