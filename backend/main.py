
"""People Search API — FastAPI backend with PostgreSQL database."""

# Load environment variables from .env file (must be before other imports)
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from uuid import UUID

from database import get_db, engine, Base
from models import Profile, Review
from schemas import (
    ProfileCreate, ProfileResponse, ProfileSummary,
    ReviewCreate, ReviewResponse
)
from query_parser import parse_search_query, ParsedQuery
from linkedin_search import search_linkedin, LinkedInSearchResult

app = FastAPI(title="People Search API", version="0.4.0")

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Autocomplete endpoint: returns up to 8 name matches for autocomplete
@app.get("/search/autocomplete")
async def autocomplete_names(q: str = Query(default="", max_length=100), db: AsyncSession = Depends(get_db)):
    """
    Return up to 8 profiles where name starts with the given prefix (case-insensitive).
    Used for autocomplete suggestions.
    """
    if not q.strip():
        return []
    result = await db.execute(
        select(Profile)
        .where(Profile.name.ilike(f"{q}%"))
        .limit(8)
    )
    profiles = result.scalars().all()
    # Return only preview fields
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "role": p.role,
            "company": p.company,
            "location": p.location
        } for p in profiles
    ]


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
    q: str = Query(default="", max_length=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Search profiles by name and/or company.
    Uses ChatGPT to parse queries like "John Smith, Oracle" or "John Smith Oracle".
    """
    if not q.strip():
        # Return all profiles
        result = await db.execute(select(Profile).limit(50))
        profiles = result.scalars().all()
        return profiles
    
    # Parse the query using OpenAI
    parsed = await parse_search_query(q)
    
    # Build query conditions based on parsed result
    conditions = []
    
    if parsed.name:
        conditions.append(Profile.name.ilike(f"%{parsed.name}%"))
    
    if parsed.company:
        conditions.append(Profile.company.ilike(f"%{parsed.company}%"))
    
    if conditions:
        if parsed.name and parsed.company:
            # Both name AND company must match
            result = await db.execute(
                select(Profile).where(and_(*conditions))
            )
        else:
            # Just one condition
            result = await db.execute(
                select(Profile).where(conditions[0])
            )
    else:
        # Fallback: search all text fields with raw query
        raw = parsed.raw_query.lower()
        result = await db.execute(
            select(Profile).where(
                or_(
                    Profile.name.ilike(f"%{raw}%"),
                    Profile.company.ilike(f"%{raw}%"),
                    Profile.role.ilike(f"%{raw}%"),
                    Profile.location.ilike(f"%{raw}%")
                )
            )
        )
    
    profiles = result.scalars().all()
    return profiles


@app.get("/search/parse")
async def parse_query(q: str = Query(..., max_length=200)) -> ParsedQuery:
    """Debug endpoint to see how a query is parsed."""
    return await parse_search_query(q)


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


@app.get("/search/linkedin", response_model=LinkedInSearchResult)
async def linkedin_search(
    q: str = Query(..., min_length=1, max_length=200)
):
    """
    Search for LinkedIn profiles using DuckDuckGo (free, no API key).
    Returns parsed profile information.
    """
    try:
        result = await search_linkedin(q, max_results=20)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

