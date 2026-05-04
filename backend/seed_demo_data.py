"""Seed demo data for the People Search app.

Run from the repository root:

    python backend/seed_demo_data.py

To upload demo images into the configured Cloudinary account:

    python backend/seed_demo_data.py --upload-images
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import cloudinary
import cloudinary.uploader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import LeaderProfileVerification, Profile, Review, User


DEMO_PASSWORD = "DemoPass123!"
DEMO_USER_DOMAIN = "example.test"
DEMO_REVIEWERS = [
    ("Avery", "Brooks"),
    ("Jordan", "Lee"),
    ("Morgan", "Patel"),
    ("Taylor", "Kim"),
    ("Casey", "Rivera"),
]

FIRST_NAMES = [
    "John",
    "Sarah",
    "Michael",
    "Emily",
    "David",
    "Jessica",
    "Robert",
    "Amanda",
    "James",
    "Lisa",
    "Christopher",
    "Jennifer",
    "Daniel",
    "Michelle",
    "Kevin",
    "Rachel",
    "Brian",
    "Nicole",
    "Samantha",
    "Matthew",
    "Ashley",
    "Joshua",
    "Elizabeth",
    "Andrew",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
]

COMPANIES = [
    "Oracle",
    "Google",
    "Microsoft",
    "Apple",
    "Amazon",
    "Meta",
    "Salesforce",
    "IBM",
    "Stripe",
    "Airbnb",
    "Netflix",
    "Adobe",
    "Figma",
    "Shopify",
    "Deloitte",
    "JPMorgan Chase",
    "City of Boston",
    "Boston University",
]

ROLES = [
    "Senior Software Engineer",
    "Product Manager",
    "Data Architect",
    "Staff Engineer",
    "UX Designer",
    "Engineering Manager",
    "Solutions Architect",
    "Program Manager",
    "Design Lead",
    "Data Scientist",
    "Platform Engineer",
    "Technical Architect",
    "Product Strategy Lead",
    "Director of Civic Innovation",
    "Technology Partnerships Director",
]

LOCATIONS = [
    "Austin, TX",
    "Mountain View, CA",
    "Redmond, WA",
    "Cupertino, CA",
    "Seattle, WA",
    "Menlo Park, CA",
    "San Francisco, CA",
    "New York, NY",
    "Boston, MA",
    "Chicago, IL",
    "Atlanta, GA",
    "Raleigh, NC",
]

REVIEW_COMMENTS = [
    "Clear communicator with a strong record of shipping practical work.",
    "Known for thoughtful collaboration and reliable follow-through.",
    "Brings useful context to hard decisions and keeps teams moving.",
    "Balances technical depth with a strong sense for the customer.",
    "Generous mentor who raises the quality bar around them.",
]


@dataclass(frozen=True)
class DemoProfile:
    name: str
    company: str
    role: str
    location: str
    bio: str
    linkedin_url: str
    avatar_source_url: str
    is_verified: bool


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_demo_profiles(limit: int) -> list[DemoProfile]:
    profiles: list[DemoProfile] = []
    repeated_showcase_names = [
        ("John Smith", "Oracle"),
        ("John Smith", "Google"),
        ("John Smith", "Microsoft"),
        ("Sarah Johnson", "Oracle"),
        ("Sarah Johnson", "Meta"),
        ("Michael Chen", "Google"),
        ("Michael Chen", "Stripe"),
        ("Emily Davis", "Apple"),
        ("Emily Davis", "Amazon"),
        ("Samyr Laguerre", "City of Boston"),
        ("Samyr Laguerre", "Meta"),
        ("Samyr Laguerre", "Boston University"),
    ]

    for index, (name, company) in enumerate(repeated_showcase_names):
        seed = slugify(f"{name}-{company}")
        profiles.append(
            DemoProfile(
                name=name,
                company=company,
                role=ROLES[index % len(ROLES)],
                location=LOCATIONS[index % len(LOCATIONS)],
                bio=f"Demo profile for autocomplete and duplicate-name search at {company}.",
                linkedin_url=f"https://www.linkedin.com/in/demo-{seed}",
                avatar_source_url=f"https://i.pravatar.cc/300?u={seed}",
                is_verified=index % 2 == 0,
            )
        )

    index = len(profiles)
    for first in FIRST_NAMES:
        for last in LAST_NAMES:
            if len(profiles) >= limit:
                return profiles
            name = f"{first} {last}"
            company = COMPANIES[index % len(COMPANIES)]
            seed = slugify(f"{name}-{company}-{index}")
            profiles.append(
                DemoProfile(
                    name=name,
                    company=company,
                    role=ROLES[index % len(ROLES)],
                    location=LOCATIONS[index % len(LOCATIONS)],
                    bio=f"{ROLES[index % len(ROLES)]} focused on teams, systems, and measurable delivery.",
                    linkedin_url=f"https://www.linkedin.com/in/demo-{seed}",
                    avatar_source_url=f"https://i.pravatar.cc/300?u={seed}",
                    is_verified=index % 6 == 0,
                )
            )
            index += 1
    return profiles


def configure_cloudinary() -> None:
    config = {"secure": True}
    if not os.getenv("CLOUDINARY_URL"):
        config.update(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )
    cloudinary.config(**config)


def cloudinary_ready() -> bool:
    current = cloudinary.config()
    return bool(current.cloud_name and current.api_key and current.api_secret)


def upload_image(source_url: str, folder: str, public_id: str) -> str:
    result = cloudinary.uploader.upload(
        source_url,
        folder=folder,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
        type="upload",
        unique_filename=False,
    )
    secure_url = result.get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Cloudinary did not return a secure_url for {source_url}")
    return secure_url


def hash_demo_password() -> str:
    return bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def get_or_create_user(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    password_hash: str,
    avatar_url: Optional[str] = None,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    return user


async def upsert_profile(db: AsyncSession, demo: DemoProfile, avatar_url: str) -> tuple[Profile, bool]:
    result = await db.execute(select(Profile).where(Profile.linkedin_url == demo.linkedin_url))
    profile = result.scalar_one_or_none()
    created = False

    if not profile:
        result = await db.execute(
            select(Profile).where(Profile.name == demo.name, Profile.company == demo.company)
        )
        profile = result.scalars().first()

    if profile:
        profile.role = demo.role
        profile.location = demo.location
        profile.bio = demo.bio
        profile.linkedin_url = profile.linkedin_url or demo.linkedin_url
        profile.avatar_url = profile.avatar_url or avatar_url
    else:
        profile = Profile(
            name=demo.name,
            company=demo.company,
            role=demo.role,
            location=demo.location,
            bio=demo.bio,
            linkedin_url=demo.linkedin_url,
            avatar_url=avatar_url,
        )
        db.add(profile)
        created = True

    await db.flush()
    return profile, created


async def ensure_reviews(
    db: AsyncSession,
    profile: Profile,
    reviewer_users: list[User],
    profile_index: int,
) -> int:
    created = 0
    desired_count = 1 + (profile_index % 3)
    for offset, reviewer in enumerate(reviewer_users[:desired_count]):
        result = await db.execute(
            select(Review).where(
                Review.profile_id == profile.id,
                Review.user_id == reviewer.id,
            )
        )
        if result.scalar_one_or_none():
            continue

        rating = 3 + ((profile_index + offset) % 3)
        review = Review(
            profile_id=profile.id,
            user_id=reviewer.id,
            author=f"{reviewer.first_name} {reviewer.last_name}",
            rating=rating,
            comment=REVIEW_COMMENTS[(profile_index + offset) % len(REVIEW_COMMENTS)],
        )
        db.add(review)
        profile.total_review_score += rating
        profile.review_count += 1
        created += 1
    return created


async def ensure_verification(
    db: AsyncSession,
    profile: Profile,
    demo: DemoProfile,
    password_hash: str,
    profile_photo_url: str,
    badge_photo_url: str,
) -> bool:
    if not demo.is_verified:
        return False

    seed = slugify(f"{demo.name}-{demo.company}")
    first_name, *last_parts = demo.name.split()
    last_name = " ".join(last_parts) or "Demo"
    verifier = await get_or_create_user(
        db,
        email=f"verified+{seed}@{DEMO_USER_DOMAIN}",
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        avatar_url=profile_photo_url,
    )

    result = await db.execute(
        select(LeaderProfileVerification).where(
            LeaderProfileVerification.profile_id == profile.id
        )
    )
    verification = result.scalar_one_or_none()
    if verification:
        profile.is_verified = True
        profile.verification_status = verification.status
        profile.verified_by_user_id = verification.user_id
        profile.verified_at = profile.verified_at or verification.created_at or datetime.now(timezone.utc)
        profile.avatar_url = profile.avatar_url or verification.profile_photo_url
        return False

    verification = LeaderProfileVerification(
        profile_id=profile.id,
        user_id=verifier.id,
        profile_photo_url=profile_photo_url,
        badge_photo_url=badge_photo_url,
        status="self_verified",
    )
    db.add(verification)
    profile.avatar_url = profile_photo_url
    profile.is_verified = True
    profile.verification_status = "self_verified"
    profile.verified_at = datetime.now(timezone.utc)
    profile.verified_by_user_id = verifier.id
    return True


async def seed(args: argparse.Namespace) -> None:
    configure_cloudinary()
    if args.upload_images and not cloudinary_ready():
        raise RuntimeError("Cloudinary is not configured. Set CLOUDINARY_URL or CLOUDINARY_* values.")

    password_hash = hash_demo_password()
    profiles = build_demo_profiles(args.count)

    created_profiles = 0
    created_reviews = 0
    created_verifications = 0

    async with async_session() as db:
        reviewer_users = []
        for first_name, last_name in DEMO_REVIEWERS:
            seed_value = slugify(f"{first_name}-{last_name}")
            avatar_url = f"https://i.pravatar.cc/300?u=reviewer-{seed_value}"
            reviewer_users.append(
                await get_or_create_user(
                    db,
                    email=f"reviewer+{seed_value}@{DEMO_USER_DOMAIN}",
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=password_hash,
                    avatar_url=avatar_url,
                )
            )

        for index, demo in enumerate(profiles):
            seed_value = slugify(f"{demo.name}-{demo.company}-{index}")
            profile_photo_url = demo.avatar_source_url
            badge_photo_url = f"https://picsum.photos/seed/badge-{seed_value}/900/600"

            if args.upload_images:
                profile_photo_url = upload_image(
                    demo.avatar_source_url,
                    "sumoimperium/demo/profile-pictures",
                    f"profile-{seed_value}",
                )
                if demo.is_verified:
                    badge_photo_url = upload_image(
                        badge_photo_url,
                        "sumoimperium/demo/profile-verifications",
                        f"badge-{seed_value}",
                    )

            profile, created = await upsert_profile(db, demo, profile_photo_url)
            created_profiles += int(created)
            created_reviews += await ensure_reviews(db, profile, reviewer_users, index)
            created_verifications += int(
                await ensure_verification(
                    db,
                    profile,
                    demo,
                    password_hash,
                    profile_photo_url,
                    badge_photo_url,
                )
            )

        await db.commit()

    print(
        "Seed complete: "
        f"{len(profiles)} profiles processed, "
        f"{created_profiles} profiles created, "
        f"{created_reviews} reviews created, "
        f"{created_verifications} verifications created."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo people-search data.")
    parser.add_argument(
        "--count",
        type=int,
        default=120,
        help="Number of demo profiles to process. Default: 120.",
    )
    parser.add_argument(
        "--upload-images",
        action="store_true",
        help="Upload avatar and verification images into the configured Cloudinary account.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
