
"""People Search API — FastAPI backend with PostgreSQL database."""

# Load environment variables from .env file (must be before other imports)
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from uuid import UUID

from database import get_db, engine, Base
from models import Profile, Review, User, LeaderProfileVerification
from schemas import (
    ProfileCreate, ProfileResponse, ProfileSummary,
    LinkedInReviewCreate, ReviewCreate, ReviewResponse,
    UserCreate, UserLogin, UserResponse,
    VerificationStatusResponse, ProfileVerificationResponse
)
from query_parser import (
    clean_query_part,
    parse_name_company_candidates,
    parse_search_query,
    ParsedQuery,
)
from linkedin_search import (
    InvalidLinkedInProfileUrl,
    LinkedInProfile,
    canonical_linkedin_url,
    is_linkedin_profile_url,
    search_linkedin,
    LinkedInSearchResult,
)
import jwt

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import status
import os
import io
import re
from datetime import timedelta, datetime
from typing import Optional

# Initialize FastAPI app immediately after imports
app = FastAPI(title="People Search API", version="0.4.0")

cloudinary_config = {"secure": True}
if not os.getenv("CLOUDINARY_URL"):
    cloudinary_config.update(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )
cloudinary.config(**cloudinary_config)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ----------------------
# JWT Auth Helpers
# ----------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
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


@app.get("/auth/me/verification", response_model=VerificationStatusResponse)
async def get_my_verification_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Profile).where(Profile.verified_by_user_id == current_user.id)
    )
    profile = result.scalars().first()
    return {"has_verified_profile": profile is not None, "profile": profile}

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

def _clean_autocomplete_part(value: str) -> str:
    """Normalize user-typed autocomplete fragments."""
    return clean_query_part(value)


def _autocomplete_name_company_candidates(query: str) -> list[tuple[str, str]]:
    return parse_name_company_candidates(query)


def _profile_name_prefix_condition(prefix: str):
    escaped_prefix = (
        prefix.lower()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return func.lower(Profile.name).like(f"{escaped_prefix}%", escape="\\")


def _autocomplete_match_score(profile: Profile, query: str, candidates: list[tuple[str, str]]) -> int:
    clean_query = _clean_autocomplete_part(query).lower()
    profile_name = profile.name.lower()
    profile_company = profile.company.lower()
    score = 0

    if profile_name.startswith(clean_query):
        score = max(score, 100 + len(clean_query))

    for name, company in candidates:
        name_l = name.lower()
        company_l = company.lower()
        if profile_name.startswith(name_l) and company_l in profile_company:
            candidate_score = 200 + len(name_l) + len(company_l)
            if profile_name == name_l:
                candidate_score += 50
            if profile_company.startswith(company_l):
                candidate_score += 25
            score = max(score, candidate_score)

    return score


# Autocomplete endpoint: returns up to 8 profile matches for autocomplete
@app.get("/search/autocomplete")
async def autocomplete_names(q: str = Query(default="", max_length=100), db: AsyncSession = Depends(get_db)):
    """
    Return up to 8 profiles matching a typed name prefix, with optional company
    context such as "John Smith, Oracle" or "John Smith Oracle".
    """
    clean_query = _clean_autocomplete_part(q)
    if not clean_query:
        return []

    name_company_candidates = _autocomplete_name_company_candidates(clean_query)
    conditions = [_profile_name_prefix_condition(clean_query)]
    conditions.extend(
        and_(
            _profile_name_prefix_condition(name),
            Profile.company.ilike(f"%{company}%"),
        )
        for name, company in name_company_candidates
    )

    result = await db.execute(
        select(Profile)
        .where(or_(*conditions))
        .limit(50)
    )
    profiles = result.scalars().all()
    profiles.sort(
        key=lambda profile: (
            -_autocomplete_match_score(profile, clean_query, name_company_candidates),
            profile.name.lower(),
        )
    )

    # Return only preview fields
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "role": p.role,
            "company": p.company,
            "location": p.location,
            "avatar_url": p.avatar_url,
            "is_verified": p.is_verified,
            "verification_status": p.verification_status,
        } for p in profiles[:8]
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
    Parses common name/company query shapes locally without calling an LLM.
    """
    if not q.strip():
        # Return all profiles
        result = await db.execute(select(Profile).limit(50))
        profiles = result.scalars().all()
        return profiles
    
    # Parse the query locally and build database-backed name/company splits.
    parsed = await parse_search_query(q)
    clean_query = clean_query_part(q)
    word_count = len(re.sub(r"\s*,\s*", " ", clean_query).split())
    has_explicit_company_separator = "," in clean_query or any(
        keyword in clean_query.lower() for keyword in (" at ", " from ", " @ ")
    )
    name_company_candidates = parse_name_company_candidates(q)
    if word_count < 3 and not parsed.company and not has_explicit_company_separator:
        name_company_candidates = []
    
    # Build query conditions based on parsed result
    conditions = []
    candidate_conditions = [
        and_(
            _profile_name_prefix_condition(name),
            Profile.company.ilike(f"%{company}%"),
        )
        for name, company in name_company_candidates
    ]
    
    if parsed.name and parsed.company:
        conditions.append(_profile_name_prefix_condition(parsed.name))
    elif parsed.name:
        conditions.append(Profile.name.ilike(f"%{parsed.name}%"))

    if parsed.company:
        conditions.append(Profile.company.ilike(f"%{parsed.company}%"))
    
    search_conditions = []
    if candidate_conditions:
        search_conditions.extend(candidate_conditions)
    if conditions:
        search_conditions.append(and_(*conditions) if len(conditions) > 1 else conditions[0])

    if search_conditions:
        result = await db.execute(select(Profile).where(or_(*search_conditions)))
        profiles = result.scalars().all()
        if profiles:
            return profiles

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
    raise HTTPException(
        status_code=400,
        detail="Profiles must be created from LinkedIn search results",
    )


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


ALLOWED_VERIFICATION_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_VERIFICATION_IMAGE_BYTES = 5 * 1024 * 1024


async def save_verification_image(file: UploadFile, prefix: str, user_id: UUID) -> str:
    extension = ALLOWED_VERIFICATION_IMAGE_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=400, detail="Images must be JPG, PNG, or WebP")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Image file cannot be empty")
    if len(contents) > MAX_VERIFICATION_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Images must be 5MB or smaller")

    if not all((cloudinary.config().cloud_name, cloudinary.config().api_key, cloudinary.config().api_secret)):
        raise HTTPException(status_code=500, detail="Cloudinary storage is not configured")

    public_id = f"{prefix}-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    folder = (
        "sumoimperium/profile-pictures"
        if prefix == "profile"
        else "sumoimperium/profile-verifications"
    )

    try:
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            io.BytesIO(contents),
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=False,
            type="upload",
        )
    except CloudinaryError as exc:
        raise HTTPException(status_code=502, detail="Could not upload image") from exc

    secure_url = result.get("secure_url")
    if not secure_url:
        raise HTTPException(status_code=502, detail="Cloudinary did not return an image URL")
    return secure_url


@app.post("/profiles/{profile_id}/verify", response_model=ProfileVerificationResponse, status_code=201)
async def verify_profile(
    profile_id: UUID,
    profile_photo: UploadFile = File(...),
    badge_photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-verify a leader profile and store badge proof for later review."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.is_verified:
        raise HTTPException(status_code=409, detail="This profile has already been verified")

    existing_result = await db.execute(
        select(Profile).where(
            Profile.verified_by_user_id == current_user.id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already verified a leader profile")

    profile_photo_url = await save_verification_image(profile_photo, "profile", current_user.id)
    badge_photo_url = await save_verification_image(badge_photo, "badge", current_user.id)

    verification = LeaderProfileVerification(
        profile_id=profile.id,
        user_id=current_user.id,
        profile_photo_url=profile_photo_url,
        badge_photo_url=badge_photo_url,
        status="self_verified",
    )
    db.add(verification)

    profile.avatar_url = profile_photo_url
    profile.is_verified = True
    profile.verification_status = "self_verified"
    profile.verified_at = datetime.utcnow()
    profile.verified_by_user_id = current_user.id
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="This profile or user has already been verified")
    await db.refresh(verification)

    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.reviews))
        .where(Profile.id == profile.id)
    )
    verified_profile = result.scalar_one()

    return {
        "id": verification.id,
        "profile_id": profile.id,
        "profile_photo_url": profile_photo_url,
        "badge_photo_url": badge_photo_url,
        "status": verification.status,
        "created_at": verification.created_at,
        "profile": verified_profile,
    }



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

    existing_review_result = await db.execute(
        select(Review.id).where(
            Review.profile_id == profile_id,
            Review.user_id == current_user.id,
        )
    )
    if existing_review_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already reviewed this profile")

    # Use current user's name as author
    review = Review(
        profile_id=profile_id,
        user_id=current_user.id,
        author=f"{current_user.first_name} {current_user.last_name}",
        rating=data.rating,
        comment=data.comment
    )
    db.add(review)
    await db.execute(
        update(Profile)
        .where(Profile.id == profile_id)
        .values(
            total_review_score=Profile.total_review_score + data.rating,
            review_count=Profile.review_count + 1,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="You have already reviewed this profile")
    await db.refresh(review)
    return review


def clean_linkedin_text(value: str) -> str:
    """Remove search-result decoration from LinkedIn-derived fields."""
    value = re.sub(r"\s*\|\s*LinkedIn.*$", "", value or "", flags=re.IGNORECASE)
    value = re.sub(r"\s+LinkedIn\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*\.\.\..*$", "", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_linkedin_company(company: str, name: str) -> str:
    value = clean_linkedin_text(company)
    if name and name.lower() in value.lower():
        value = value[:value.lower().index(name.lower())].strip()
    if " - " in value:
        value = value.split(" - ", 1)[0].strip()
    return value or "Unknown"


def clean_linkedin_role(role: str, name: str) -> str:
    value = clean_linkedin_text(role)
    if " - " in value:
        before_dash, after_dash = value.split(" - ", 1)
        if not name or name.lower() in before_dash.lower():
            value = after_dash.strip()
    if name and value.lower().startswith(name.lower()):
        value = re.sub(r"^[-,\s]+", "", value[len(name):]).strip()
    return value or "LinkedIn Member"


def normalize_linkedin_url(url: Optional[str]) -> Optional[str]:
    """Canonicalize LinkedIn profile URLs for duplicate checks."""
    return canonical_linkedin_url(url or "")


def linkedin_profile_from_saved_profile(profile: Profile) -> LinkedInProfile:
    return LinkedInProfile(
        name=profile.name,
        company=profile.company,
        title=profile.role,
        location=profile.location,
        url=profile.linkedin_url or "",
        snippet=None,
        match_score=100,
        avatar_url=profile.avatar_url,
        existing_profile_id=profile.id,
        existing_profile_review_count=profile.review_count,
        existing_profile_average_rating=profile.average_rating,
        existing_profile_avatar_url=profile.avatar_url,
        url_verification="saved",
    )


@app.post("/linkedin/reviews", response_model=ProfileResponse, status_code=201)
async def create_linkedin_profile_review(
    data: LinkedInReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a profile from LinkedIn result data, or use a profile the user chose."""
    profile_data = data.profile
    linkedin_url = normalize_linkedin_url(profile_data.linkedin_url)
    cleaned_profile_data = profile_data.model_copy(
        update={
            "company": clean_linkedin_company(profile_data.company, profile_data.name)[:100],
            "role": clean_linkedin_role(profile_data.role, profile_data.name)[:100],
            "linkedin_url": linkedin_url,
        }
    )

    if data.existing_profile_id:
        if linkedin_url:
            url_owner_result = await db.execute(
                select(Profile.id).where(Profile.linkedin_url == linkedin_url)
            )
            url_owner_id = url_owner_result.scalar_one_or_none()
            if url_owner_id and url_owner_id != data.existing_profile_id:
                raise HTTPException(status_code=409, detail="A profile already exists for this LinkedIn URL")

        result = await db.execute(
            select(Profile).where(Profile.id == data.existing_profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        if linkedin_url and not profile.linkedin_url:
            profile.linkedin_url = linkedin_url
    else:
        if not linkedin_url:
            raise HTTPException(status_code=400, detail="A LinkedIn profile URL is required")

        existing_result = await db.execute(
            select(Profile).where(Profile.linkedin_url == linkedin_url)
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A profile already exists for this LinkedIn URL")

        profile = Profile(**cleaned_profile_data.model_dump())
        db.add(profile)
        try:
            await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="A profile already exists for this LinkedIn URL")

    existing_review_result = await db.execute(
        select(Review.id).where(
            Review.profile_id == profile.id,
            Review.user_id == current_user.id,
        )
    )
    if existing_review_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already reviewed this profile")

    review = Review(
        profile_id=profile.id,
        user_id=current_user.id,
        author=f"{current_user.first_name} {current_user.last_name}",
        rating=data.review.rating,
        comment=data.review.comment,
    )
    db.add(review)
    await db.execute(
        update(Profile)
        .where(Profile.id == profile.id)
        .values(
            total_review_score=Profile.total_review_score + data.review.rating,
            review_count=Profile.review_count + 1,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="You have already reviewed this profile")

    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.reviews))
        .where(Profile.id == profile.id)
    )
    return result.scalar_one()


@app.get("/search/linkedin", response_model=LinkedInSearchResult)
async def linkedin_search(
    q: str = Query(..., min_length=1, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for LinkedIn profiles using DuckDuckGo (free, no API key).
    Returns parsed profile information.
    """
    try:
        canonical_url = normalize_linkedin_url(q)
        if canonical_url and is_linkedin_profile_url(q):
            profile_result = await db.execute(
                select(Profile).where(Profile.linkedin_url == canonical_url)
            )
            existing_profile = profile_result.scalar_one_or_none()
            if existing_profile:
                return LinkedInSearchResult(
                    profiles=[linkedin_profile_from_saved_profile(existing_profile)],
                    query=q,
                    parsed_name=existing_profile.name,
                    parsed_company=existing_profile.company,
                )

        result = await search_linkedin(q, max_results=20)
        normalized_urls = {
            normalize_linkedin_url(profile.url)
            for profile in result.profiles
        }
        normalized_urls.discard(None)
        if normalized_urls:
            profile_result = await db.execute(
                select(Profile).where(Profile.linkedin_url.in_(normalized_urls))
            )
            profiles_by_url = {
                profile.linkedin_url: profile
                for profile in profile_result.scalars().all()
                if profile.linkedin_url
            }
            for linkedin_profile in result.profiles:
                existing_profile = profiles_by_url.get(normalize_linkedin_url(linkedin_profile.url))
                if existing_profile:
                    linkedin_profile.existing_profile_id = existing_profile.id
                    linkedin_profile.existing_profile_review_count = existing_profile.review_count
                    linkedin_profile.existing_profile_average_rating = existing_profile.average_rating
                    linkedin_profile.avatar_url = existing_profile.avatar_url
                    linkedin_profile.existing_profile_avatar_url = existing_profile.avatar_url
        return result
    except InvalidLinkedInProfileUrl as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
