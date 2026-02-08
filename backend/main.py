
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
from models import Profile, Review, User
from schemas import (
    ProfileCreate, ProfileResponse, ProfileSummary,
    ReviewCreate, ReviewResponse,
    UserCreate, UserLogin, UserResponse
)
from query_parser import parse_search_query, ParsedQuery
from linkedin_search import search_linkedin, LinkedInSearchResult
import jwt

from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import status
import os
from datetime import timedelta, datetime

# Initialize FastAPI app immediately after imports
app = FastAPI(title="People Search API", version="0.4.0")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ----------------------
# JWT Auth Helpers
# ----------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

# ----------------------
# Auth Endpoints
# ----------------------
@app.post("/auth/signup", response_model=UserResponse, status_code=201)
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pw = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        password_hash=hashed_pw,
        avatar_url=user.avatar_url
    )
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# All imports at the top
# ...existing code...


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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a review to a profile (auth required)."""
    # Check profile exists
    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Use current user's name as author
    review = Review(
        profile_id=profile_id,
        author=f"{current_user.first_name} {current_user.last_name}",
        rating=data.rating,
        comment=data.comment
    )
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

