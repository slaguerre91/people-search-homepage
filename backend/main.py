"""People Search API — FastAPI backend with in-memory storage."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

app = FastAPI(title="People Search API", version="0.1.0")

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., max_length=1000)


class Review(ReviewCreate):
    id: str
    created_at: datetime


class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=100)
    bio: str = Field(default="", max_length=500)


class Profile(ProfileCreate):
    id: str
    reviews: list[Review] = []
    created_at: datetime


class ProfileSummary(BaseModel):
    """Lightweight profile for search results."""
    id: str
    name: str
    role: str
    location: str


# ---------------------------------------------------------------------------
# In-memory storage (replace with database later)
# ---------------------------------------------------------------------------

PROFILES: dict[str, Profile] = {}

# Seed some sample data
def _seed_data():
    samples = [
        {"name": "Alice Monroe", "role": "Product Designer", "location": "New York, NY", "bio": "Passionate about user-centered design."},
        {"name": "Bob Chen", "role": "Software Engineer", "location": "San Francisco, CA", "bio": "Full-stack developer with 10 years experience."},
        {"name": "Carlos Ruiz", "role": "Data Scientist", "location": "Austin, TX", "bio": "ML enthusiast and Python advocate."},
        {"name": "Denise Patel", "role": "Marketing Lead", "location": "Seattle, WA", "bio": "Growth marketing specialist."},
        {"name": "Ethan Li", "role": "CTO", "location": "Boston, MA", "bio": "Building scalable systems since 2010."},
        {"name": "Fiona Gomez", "role": "UX Researcher", "location": "Denver, CO", "bio": "Qualitative research expert."},
        {"name": "Grace Park", "role": "Designer", "location": "Brooklyn, NY", "bio": "Visual design and branding."},
        {"name": "Hassan Ali", "role": "Frontend Engineer", "location": "Chicago, IL", "bio": "React and TypeScript specialist."},
    ]
    for p in samples:
        pid = str(uuid4())
        PROFILES[pid] = Profile(id=pid, created_at=datetime.utcnow(), **p)

_seed_data()

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/search", response_model=list[ProfileSummary])
def search_people(q: str = Query(default="", max_length=100)):
    """Search profiles by name, role, or location."""
    query = q.strip().lower()
    if not query:
        return [ProfileSummary(**p.model_dump()) for p in PROFILES.values()]
    
    results = []
    for p in PROFILES.values():
        if (query in p.name.lower() 
            or query in p.role.lower() 
            or query in p.location.lower()):
            results.append(ProfileSummary(**p.model_dump()))
    return results


@app.post("/profiles", response_model=Profile, status_code=201)
def create_profile(data: ProfileCreate):
    """Create a new profile."""
    pid = str(uuid4())
    profile = Profile(id=pid, created_at=datetime.utcnow(), **data.model_dump())
    PROFILES[pid] = profile
    return profile


@app.get("/profiles/{profile_id}", response_model=Profile)
def get_profile(profile_id: str):
    """Get full profile with reviews."""
    if profile_id not in PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    return PROFILES[profile_id]


@app.post("/profiles/{profile_id}/reviews", response_model=Review, status_code=201)
def add_review(profile_id: str, data: ReviewCreate):
    """Add a review to a profile."""
    if profile_id not in PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    review = Review(
        id=str(uuid4()),
        created_at=datetime.utcnow(),
        **data.model_dump()
    )
    PROFILES[profile_id].reviews.append(review)
    return review


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
