"""LinkedIn profile search using DuckDuckGo (free, no API key required)."""

import os
import re
import json
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID
from pydantic import BaseModel
from query_parser import parse_search_query

# Initialize OpenAI client if available
_openai_client = None
try:
    from openai import AsyncOpenAI
    if os.getenv("OPENAI_API_KEY"):
        _openai_client = AsyncOpenAI()
except ImportError:
    pass


def _is_allowed_linkedin_host(host: str) -> bool:
    return host in {"linkedin.com", "www.linkedin.com"} or bool(re.fullmatch(r"[a-z]{2,3}\.linkedin\.com", host))


class InvalidLinkedInProfileUrl(ValueError):
    """Raised when URL-shaped input is not a valid LinkedIn profile URL."""


class LinkedInProfile(BaseModel):
    """Parsed LinkedIn profile from search results."""
    name: str
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    url: str
    snippet: Optional[str] = None
    match_score: int = 0  # 0-100, higher = better match
    avatar_url: Optional[str] = None
    existing_profile_id: Optional[UUID] = None
    existing_profile_review_count: int = 0
    existing_profile_average_rating: Optional[float] = None
    existing_profile_avatar_url: Optional[str] = None
    url_verification: Optional[str] = None


class LinkedInSearchResult(BaseModel):
    """Response from LinkedIn search."""
    profiles: list[LinkedInProfile]
    query: str
    parsed_name: Optional[str] = None
    parsed_company: Optional[str] = None


def canonical_linkedin_url(url: str) -> Optional[str]:
    """Return a stable LinkedIn profile URL for dedupe and display."""
    if not url:
        return None

    value = url.strip()
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"

    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    if not _is_allowed_linkedin_host(host):
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0].lower() != "in":
        return None

    slug = path_parts[1].strip().strip("/")
    if not slug or not re.fullmatch(r"[A-Za-z0-9_%.-]+", slug) or not re.search(r"[A-Za-z0-9]", slug):
        return None

    return f"https://www.linkedin.com/in/{slug.lower()}"


def is_linkedin_profile_url(value: str) -> bool:
    """Return true only for direct LinkedIn /in profile URLs."""
    return canonical_linkedin_url(value) is not None


def looks_like_linkedin_url(value: str) -> bool:
    """Return true for direct URL input pointed at LinkedIn."""
    trimmed = (value or "").strip()
    if not trimmed or re.search(r"\s", trimmed) or "linkedin.com" not in trimmed.lower():
        return False
    if not re.match(r"^https?://", trimmed, re.IGNORECASE):
        trimmed = f"https://{trimmed}"
    parsed = urlparse(trimmed)
    host = (parsed.netloc or "").lower()
    return _is_allowed_linkedin_host(host)


def looks_like_url_input(value: str) -> bool:
    """Return true for single-token URL-shaped input."""
    trimmed = (value or "").strip()
    if not trimmed or re.search(r"\s", trimmed):
        return False

    if re.match(r"^https?://", trimmed, re.IGNORECASE):
        parsed = urlparse(trimmed)
        return bool(parsed.netloc)

    parsed = urlparse(f"https://{trimmed}")
    host = (parsed.netloc or "").lower()
    return "." in host and bool(parsed.path.strip("/"))


def _linkedin_slug(url: str) -> str:
    match = re.search(r"linkedin\.com/in/([^/?#\s]+)", url or "", re.IGNORECASE)
    return match.group(1).lower() if match else ""


def _name_parts(value: Optional[str]) -> list[str]:
    return re.findall(r"[a-z]+", (value or "").lower())


def _name_matches_target(name: str, url: str, target_name: Optional[str]) -> bool:
    """Allow common searches like Alex Tingle to match Alexander Tingle."""
    target_parts = _name_parts(target_name)
    if not target_parts:
        return True

    candidate_parts = _name_parts(name)
    slug = _linkedin_slug(url)

    for target_part in target_parts:
        if any(
            candidate_part.startswith(target_part) or target_part.startswith(candidate_part)
            for candidate_part in candidate_parts
        ):
            continue
        if target_part in slug:
            continue
        return False
    return True


def _company_in_result(profile: "LinkedInProfile", company: Optional[str], *, include_snippet: bool = True) -> bool:
    if not company:
        return False

    company_lower = company.lower()
    snippet = profile.snippet or ""
    if not include_snippet:
        snippet = ""
    text = f"{profile.name} {profile.title or ''} {snippet}".lower()
    if company_lower in {"linkedin", "linked in"}:
        text = re.sub(r"\|\s*linkedin\b", "", text)
        text = re.sub(r"\bview\b.*?\bprofile on linkedin\b", "", text)
        text = re.sub(r"\bprofessional community\b.*", "", text)
        return bool(re.search(r"\b(linkedin|linked in|linkedin corporation)\b", text))

    return company_lower in text


def _result_title_anchor(title: str) -> str:
    """Use only the first LinkedIn profile segment from bundled search titles."""
    title = re.split(r"\s*\|\s*LinkedIn\b", title or "", maxsplit=1, flags=re.IGNORECASE)[0]
    title = re.split(r"\s*\.\.\.\s*", title, maxsplit=1)[0]
    return title.strip()


def parse_linkedin_result(result: dict) -> Optional[LinkedInProfile]:
    """Parse a DuckDuckGo search result into a LinkedIn profile."""
    url = result.get('href', '')
    title = result.get('title', '')
    snippet = result.get('body', '')
    
    # Only process LinkedIn profile URLs
    url = canonical_linkedin_url(url)
    if not url:
        return None

    title = _result_title_anchor(title)
    
    # Parse name from title (usually "Name - Title | LinkedIn" or "Name | LinkedIn")
    name = title
    job_title = None
    
    # Common patterns: "John Smith - Software Engineer | LinkedIn"
    if ' - ' in title:
        parts = title.split(' - ', 1)
        name = parts[0].strip()
        if len(parts) > 1:
            job_part = parts[1].replace(' | LinkedIn', '').replace('| LinkedIn', '').strip()
            if job_part and job_part.lower() != 'linkedin':
                job_title = job_part
    elif ' | ' in title:
        name = title.split(' | ')[0].strip()
    
    # Clean up name
    name = name.replace(' | LinkedIn', '').replace('| LinkedIn', '').strip()
    if not name or name.lower() == 'linkedin':
        name = "LinkedIn Member"
    
    # Try to extract location from snippet
    location = None
    location_patterns = [
        r'Location:\s*([^·•\n]+)',
        r'(?:based in|located in|from)\s+([^·•\n\.]+)',
    ]
    for pattern in location_patterns:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            location = match.group(1).strip()[:50]  # Limit length
            break
    
    return LinkedInProfile(
        name=name,
        company=None,
        title=job_title,
        location=location,
        url=url,
        snippet=snippet[:200] if snippet else None,
        match_score=0
    )


def _extract_json_array(content: str):
    """Extract a JSON array from a model response."""
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    start = content.find("[")
    end = content.rfind("]") + 1
    if start >= 0 and end > start:
        content = content[start:end]

    return json.loads(content)


def _clean_metadata_value(value: Optional[str], max_length: int = 100) -> Optional[str]:
    """Keep only compact single-field metadata."""
    if not value:
        return None
    value = re.sub(r"\s*\|\s*LinkedIn.*$", "", str(value), flags=re.IGNORECASE)
    value = re.sub(r"\s*\.\.\..*$", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -,\t\n\r")
    if not value:
        return None
    return value[:max_length]


def _apply_conservative_metadata(
    profile: LinkedInProfile,
    cleaned: dict,
    target_name: Optional[str],
    target_company: Optional[str],
) -> None:
    """Apply model-cleaned fields only when they still fit the profile URL/title."""
    name = _clean_metadata_value(cleaned.get("name"))
    company = _clean_metadata_value(cleaned.get("company"))
    location = _clean_metadata_value(cleaned.get("location"), max_length=100)

    if name and _name_matches_target(name, profile.url, target_name):
        profile.name = name
    if company and _company_in_result(profile, company, include_snippet=False):
        profile.company = company
    elif target_company and _company_in_result(profile, target_company, include_snippet=False):
        profile.company = target_company
    if location:
        profile.location = location

    profile.snippet = None
    profile.title = None


async def clean_profiles_with_gpt(
    profiles: list[LinkedInProfile],
    query: str,
    target_name: Optional[str],
    target_company: Optional[str],
) -> list[LinkedInProfile]:
    """Use ChatGPT to produce conservative user-facing metadata."""
    if not _openai_client or not profiles:
        return profiles

    results_text = "\n".join([
        "\n".join([
            f"{i}.",
            f"URL: {p.url}",
            f"Search title: {p.name}{' - ' + p.title if p.title else ''}",
            f"Search snippet: {p.snippet or ''}",
            f"Parsed location: {p.location or ''}",
        ])
        for i, p in enumerate(profiles[:10])
    ])

    prompt = f"""Clean LinkedIn search results for display in a review app.

User search: {query}
Parsed target name: {target_name or ""}
Parsed target company: {target_company or ""}

Raw results:
{results_text}

Return ONLY a JSON array with one object per result, in the same order:
[
  {{"name": "...", "company": "...", "location": "..."}}
]

Rules:
- Be conservative. Only include values directly supported by the result title, URL slug, or snippet.
- The name must be one person's name. Never include company prefixes, lists of people, or text after "...".
- The company must be one organization. Prefer the user's searched company when the result appears to match it.
- The location must be a location only, or null.
- If a snippet appears to mention multiple people, ignore the snippet for name/company.
- Use null for uncertain fields. Do not invent work history, education, role, or biography."""

    try:
        response = await _openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You clean noisy search results into conservative JSON metadata."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=900,
        )
        content = response.choices[0].message.content.strip()
        cleaned_results = _extract_json_array(content)

        for i, cleaned in enumerate(cleaned_results):
            if i >= len(profiles) or not isinstance(cleaned, dict):
                continue
            _apply_conservative_metadata(profiles[i], cleaned, target_name, target_company)
    except Exception as e:
        print(f"GPT metadata cleanup failed: {e}")

    return profiles


def basic_rank_profiles(
    profiles: list[LinkedInProfile], 
    target_name: Optional[str], 
    target_company: Optional[str]
) -> list[LinkedInProfile]:
    """Simple keyword-based ranking as fallback."""
    for p in profiles:
        score = 50  # Base score
        slug = _linkedin_slug(p.url)
        identity_text = f"{p.name} {slug}".lower()
        
        if target_name:
            name_parts = target_name.lower().split()
            for part in name_parts:
                if part in identity_text:
                    score += 15
            if _name_matches_target(p.name, p.url, target_name):
                score += 20
            elif len(name_parts) > 1:
                score -= 60
        
        if target_company:
            if _company_in_result(p, target_company, include_snippet=False):
                score += 35
            elif _company_in_result(p, target_company):
                score += 10

        if any(char.isdigit() for char in slug):
            score -= 8
        
        p.match_score = score
    
    profiles.sort(key=lambda p: p.match_score, reverse=True)
    return profiles


def enrich_profiles_from_anchored_metadata(
    profiles: list[LinkedInProfile],
    target_company: Optional[str],
) -> list[LinkedInProfile]:
    """Fill display metadata only when it is present in the title/name anchor."""
    if not target_company:
        return profiles

    for profile in profiles:
        if not profile.company and _company_in_result(profile, target_company, include_snippet=False):
            profile.company = target_company
    return profiles


def profile_from_url_slug(url: str) -> Optional[LinkedInProfile]:
    """Create a URL-only profile result without claiming LinkedIn existence."""
    canonical_url = canonical_linkedin_url(url)
    if not canonical_url:
        return None

    slug = _linkedin_slug(canonical_url)
    name_parts = slug.split("-")
    name_parts = [p for p in name_parts if not (len(p) > 6 and p.isalnum() and any(c.isdigit() for c in p))]
    name = " ".join(part.capitalize() for part in name_parts if part) or "LinkedIn Profile"

    return LinkedInProfile(
        name=name,
        company=None,
        title=None,
        location=None,
        url=canonical_url,
        snippet=None,
        match_score=100,
        url_verification="unverified",
    )


def search_profile_from_url(url: str) -> Optional[LinkedInProfile]:
    """Return a direct URL profile only when search results confirm it exists."""
    canonical_url = canonical_linkedin_url(url)
    if not canonical_url:
        return None

    slug = _linkedin_slug(canonical_url)
    queries = [
        f'"{canonical_url}"',
        f'"linkedin.com/in/{slug}" site:linkedin.com/in',
    ]

    for search_query in queries:
        try:
            from ddgs import DDGS
            results = DDGS().text(search_query, max_results=5)
        except Exception as e:
            print(f"DuckDuckGo direct URL validation failed for '{search_query}': {e}")
            continue

        for result in results:
            if canonical_linkedin_url(result.get("href", "")) != canonical_url:
                continue
            profile = parse_linkedin_result(result)
            if profile:
                profile.match_score = 100
                profile.url_verification = "confirmed"
                return profile

    return None


async def search_linkedin(query: str, max_results: int = 10) -> LinkedInSearchResult:
    """
    Search for LinkedIn profiles using DuckDuckGo.
    Uses local parsing for query generation and optional GPT cleanup for display metadata.
    Also supports direct LinkedIn URL input.
    """
    
    # Step 0: Check if query is a direct LinkedIn URL
    if is_linkedin_profile_url(query):
        profile = search_profile_from_url(query.strip())
        if not profile:
            profile = profile_from_url_slug(query.strip())
        return LinkedInSearchResult(
            profiles=[profile] if profile else [],
            query=query,
            parsed_name=profile.name if profile else None,
            parsed_company=None
        )
    if looks_like_url_input(query):
        raise InvalidLinkedInProfileUrl("Enter a valid LinkedIn profile URL, like https://www.linkedin.com/in/name")
    if looks_like_linkedin_url(query):
        return LinkedInSearchResult(
            profiles=[],
            query=query,
            parsed_name=None,
            parsed_company=None
        )
    
    # Step 1: Parse query to extract name and company
    parsed = await parse_search_query(query)
    target_name = parsed.name
    target_company = parsed.company
    
    # Step 2: Build search queries - try multiple variations for better coverage
    search_queries = []
    
    if target_name and target_company:
        # Primary: name + company
        search_queries.append(f'"{target_name}" {target_company} site:linkedin.com/in')
        search_queries.append(f'{target_name} {target_company} site:linkedin.com/in')
        if target_company.lower() in ["linkedin", "linked in"]:
            search_queries.append(f'"{target_name}" "at LinkedIn" site:linkedin.com/in')
            search_queries.append(f'"{target_name}" "LinkedIn Corporation" site:linkedin.com/in')
        # Fallback: just name
        search_queries.append(f'"{target_name}" site:linkedin.com/in')
    elif target_name:
        # Just name - try quoted and unquoted
        search_queries.append(f'"{target_name}" site:linkedin.com/in')
        # Also try with "linkedin" keyword for better results
        search_queries.append(f'{target_name} linkedin profile site:linkedin.com/in')
    else:
        # No parsing worked, use raw query
        clean_query = re.sub(r'\blinkedin\b', '', query, flags=re.IGNORECASE).strip()
        search_queries.append(f'{clean_query} site:linkedin.com/in')
    
    # Step 3: Search DuckDuckGo with multiple queries
    all_results = []
    seen_urls = set()
    
    searched_company_variants = target_name and target_company
    for index, search_query in enumerate(search_queries):
        try:
            from ddgs import DDGS
            results = DDGS().text(search_query, max_results=max_results)
            for r in results:
                url = canonical_linkedin_url(r.get('href', ''))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"DuckDuckGo search failed for '{search_query}': {e}")
            continue
        
        # Stop if we have enough results. For company searches, try all company
        # variants first because quoted searches can miss nickname/full-name cases.
        searched_company_queries = index >= len(search_queries) - 2
        if len(all_results) >= max_results * 2 and (not searched_company_variants or searched_company_queries):
            break
    
    if not all_results:
        return LinkedInSearchResult(
            profiles=[], 
            query=query,
            parsed_name=target_name,
            parsed_company=target_company
        )
    
    # Step 4: Parse results into profiles
    profiles = []
    for result in all_results:
        profile = parse_linkedin_result(result)
        if profile:
            profiles.append(profile)
            if len(profiles) >= max_results * 2:
                break
    
    # Step 5: Rank profiles locally, then optionally clean display metadata with GPT.
    if profiles and (target_name or target_company):
        profiles = basic_rank_profiles(profiles, target_name, target_company)

    profiles = enrich_profiles_from_anchored_metadata(profiles, target_company)
    profiles = await clean_profiles_with_gpt(profiles, query, target_name, target_company)
    
    return LinkedInSearchResult(
        profiles=profiles[:max_results],
        query=query,
        parsed_name=target_name,
        parsed_company=target_company
    )
