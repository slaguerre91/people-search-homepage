"""LinkedIn profile search using DuckDuckGo (free, no API key required)."""

import os
import re
import json
from ddgs import DDGS
from pydantic import BaseModel
from query_parser import parse_search_query, ParsedQuery

# Initialize OpenAI client if available
_openai_client = None
try:
    from openai import AsyncOpenAI
    if os.getenv("OPENAI_API_KEY"):
        _openai_client = AsyncOpenAI()
except ImportError:
    pass


class LinkedInProfile(BaseModel):
    """Parsed LinkedIn profile from search results."""
    name: str
    title: str | None = None
    location: str | None = None
    url: str
    snippet: str | None = None
    match_score: int = 0  # 0-100, higher = better match


class LinkedInSearchResult(BaseModel):
    """Response from LinkedIn search."""
    profiles: list[LinkedInProfile]
    query: str
    parsed_name: str | None = None
    parsed_company: str | None = None


def parse_linkedin_result(result: dict) -> LinkedInProfile | None:
    """Parse a DuckDuckGo search result into a LinkedIn profile."""
    url = result.get('href', '')
    title = result.get('title', '')
    snippet = result.get('body', '')
    
    # Only process LinkedIn profile URLs
    if 'linkedin.com/in/' not in url:
        return None
    
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
        title=job_title,
        location=location,
        url=url,
        snippet=snippet[:200] if snippet else None,
        match_score=0
    )


async def rank_profiles_with_gpt(
    profiles: list[LinkedInProfile], 
    target_name: str | None, 
    target_company: str | None
) -> list[LinkedInProfile]:
    """Use ChatGPT to score and rank profiles based on how well they match the search."""
    if not _openai_client or not profiles:
        return profiles
    
    if not target_name and not target_company:
        return profiles
    
    # Build the ranking prompt
    profiles_text = "\n".join([
        f"{i+1}. Name: {p.name}, Title: {p.title or 'Unknown'}, Snippet: {p.snippet or 'None'}"
        for i, p in enumerate(profiles[:15])  # Limit to avoid token overflow
    ])
    
    target_desc = []
    if target_name:
        target_desc.append(f"Name: {target_name}")
    if target_company:
        target_desc.append(f"Company: {target_company}")
    
    prompt = f"""Score each LinkedIn profile on how well it matches the target person.
    
Target: {', '.join(target_desc)}

Profiles:
{profiles_text}

IMPORTANT SCORING RULES:
- Names must match EXACTLY (first AND last name). "Jonathan Laguerre" is NOT "Johnathan Laguerre" or "Jonathan Smith".
- If company is specified, person should work there (check title/snippet).
- Check the URL slug - it often contains the real name.

Scoring guide:
- 100 = Perfect match: exact name AND confirmed at target company
- 80 = Strong match: exact name, company appears likely in title/snippet  
- 60 = Good match: exact name, company unknown
- 40 = Partial: slight name variation (e.g., "Jon" vs "Jonathan") with company match
- 20 = Weak: only first OR last name matches
- 0 = No match: different person

Return ONLY a JSON array of scores in order, like: [85, 60, 40, ...]"""

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a profile matching expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extract JSON array from response
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        # Find the array in the response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            content = content[start:end]
        
        scores = json.loads(content)
        
        # Apply scores to profiles
        for i, score in enumerate(scores):
            if i < len(profiles):
                profiles[i].match_score = min(100, max(0, int(score)))
        
        # Sort by score descending
        profiles.sort(key=lambda p: p.match_score, reverse=True)
        
    except Exception as e:
        print(f"GPT ranking failed: {e}")
        # Fall back to basic ranking
        profiles = basic_rank_profiles(profiles, target_name, target_company)
    
    return profiles


def basic_rank_profiles(
    profiles: list[LinkedInProfile], 
    target_name: str | None, 
    target_company: str | None
) -> list[LinkedInProfile]:
    """Simple keyword-based ranking as fallback."""
    for p in profiles:
        score = 50  # Base score
        text = f"{p.name} {p.title or ''} {p.snippet or ''}".lower()
        
        if target_name:
            name_parts = target_name.lower().split()
            for part in name_parts:
                if part in p.name.lower():
                    score += 15
        
        if target_company:
            if target_company.lower() in text:
                score += 25
        
        p.match_score = min(100, score)
    
    profiles.sort(key=lambda p: p.match_score, reverse=True)
    return profiles


def extract_profile_from_url(url: str) -> LinkedInProfile | None:
    """Extract profile info from a direct LinkedIn URL."""
    if 'linkedin.com/in/' not in url:
        return None
    
    # Extract the username/slug from the URL
    match = re.search(r'linkedin\.com/in/([^/?]+)', url)
    if not match:
        return None
    
    slug = match.group(1)
    
    # Convert slug to readable name (e.g., "jonathan-n-laguerre" -> "Jonathan N Laguerre")
    name_parts = slug.split('-')
    # Filter out random ID suffixes (usually long hex strings at the end)
    name_parts = [p for p in name_parts if not (len(p) > 6 and p.isalnum() and any(c.isdigit() for c in p))]
    name = ' '.join(part.capitalize() for part in name_parts if part)
    
    if not name:
        name = "LinkedIn Member"
    
    return LinkedInProfile(
        name=name,
        title=None,
        location=None,
        url=url if url.startswith('http') else f'https://www.linkedin.com/in/{slug}',
        snippet="Direct URL - profile details available on LinkedIn",
        match_score=100  # Direct URL = perfect match
    )


async def search_linkedin(query: str, max_results: int = 10) -> LinkedInSearchResult:
    """
    Search for LinkedIn profiles using DuckDuckGo.
    Uses ChatGPT to parse query and rank results intelligently.
    Also supports direct LinkedIn URL input.
    """
    
    # Step 0: Check if query is a direct LinkedIn URL
    if 'linkedin.com/in/' in query:
        profile = extract_profile_from_url(query.strip())
        if profile:
            return LinkedInSearchResult(
                profiles=[profile],
                query=query,
                parsed_name=profile.name,
                parsed_company=None
            )
    
    # Step 1: Parse query to extract name and company
    parsed = await parse_search_query(query)
    target_name = parsed.name
    target_company = parsed.company
    
    # Handle "LinkedIn" as company - user probably just wants to find the person
    if target_company and target_company.lower() in ["linkedin", "linked in"]:
        target_company = None
    
    # Step 2: Build search queries - try multiple variations for better coverage
    search_queries = []
    
    if target_name and target_company:
        # Primary: name + company
        search_queries.append(f'"{target_name}" {target_company} site:linkedin.com/in')
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
    
    for search_query in search_queries:
        try:
            results = DDGS().text(search_query, max_results=max_results)
            for r in results:
                url = r.get('href', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"DuckDuckGo search failed for '{search_query}': {e}")
            continue
        
        # Stop if we have enough results
        if len(all_results) >= max_results * 2:
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
    
    # Step 5: Rank profiles using GPT (or fallback to basic ranking)
    if profiles and (target_name or target_company):
        if _openai_client:
            profiles = await rank_profiles_with_gpt(profiles, target_name, target_company)
        else:
            profiles = basic_rank_profiles(profiles, target_name, target_company)
    
    return LinkedInSearchResult(
        profiles=profiles[:max_results],
        query=query,
        parsed_name=target_name,
        parsed_company=target_company
    )
