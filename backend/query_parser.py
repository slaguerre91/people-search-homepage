"""Query parser using OpenAI to extract name and company from natural language search.

Hybrid approach: Fast rule-based parsing first, LLM only for ambiguous queries.
"""

import os
import json
import re
from pydantic import BaseModel
from typing import Optional, Tuple


class ParsedQuery(BaseModel):
    """Parsed search query with extracted name and company."""
    name: Optional[str] = None
    company: Optional[str] = None
    raw_query: str


# Known company names for fast matching (add more as needed)
KNOWN_COMPANIES = {
    "google", "microsoft", "apple", "amazon", "meta", "facebook", "netflix",
    "oracle", "ibm", "intel", "cisco", "salesforce", "adobe", "nvidia",
    "tesla", "uber", "lyft", "airbnb", "spotify", "twitter", "x", "linkedin",
    "stripe", "square", "shopify", "zoom", "slack", "dropbox", "github",
    "openai", "anthropic", "databricks", "snowflake", "palantir", "coinbase",
}

# Initialize OpenAI client only if API key is available
_openai_client = None
OPENAI_AVAILABLE = False

try:
    from openai import AsyncOpenAI
    if os.getenv("OPENAI_API_KEY"):
        _openai_client = AsyncOpenAI()
        OPENAI_AVAILABLE = True
except ImportError:
    pass

SYSTEM_PROMPT = """You are a search query parser. Extract the person's name and company from user search queries.

Return a JSON object with:
- "name": the person's name (or null if not provided)
- "company": the company name (or null if not provided)

Examples:
- "John Williams Netflix" → {"name": "John Williams", "company": "Netflix"}
- "Sarah Chen at Stripe" → {"name": "Sarah Chen", "company": "Stripe"}

Only return the JSON object, nothing else."""


def _rule_based_parse(query: str) -> Tuple[Optional[ParsedQuery], bool]:
    """
    Fast rule-based parser. Returns (ParsedQuery, is_confident).
    If is_confident is False, caller should use LLM for better accuracy.
    """
    query = query.strip()
    original_query = query
    
    if not query:
        return ParsedQuery(raw_query=original_query), True
    
    # Pattern 1: Comma separator - "John Smith, Oracle" (high confidence)
    if "," in query:
        parts = [p.strip() for p in query.split(",", 1)]
        return ParsedQuery(
            name=parts[0] if parts[0] else None,
            company=parts[1] if len(parts) > 1 and parts[1] else None,
            raw_query=original_query
        ), True
    
    # Pattern 2: Keywords "at", "from", "@" - "Sarah at Google" (high confidence)
    for keyword in [" at ", " from ", " @ "]:
        if keyword in query.lower():
            idx = query.lower().index(keyword)
            name = query[:idx].strip()
            company = query[idx + len(keyword):].strip()
            return ParsedQuery(
                name=name if name else None,
                company=company if company else None,
                raw_query=original_query
            ), True
    
    # Pattern 3: Single word - could be name or company
    words = query.split()
    if len(words) == 1:
        word_lower = words[0].lower()
        # Check if it's a known company
        if word_lower in KNOWN_COMPANIES:
            return ParsedQuery(name=None, company=words[0], raw_query=original_query), True
        # Otherwise treat as name
        return ParsedQuery(name=query, company=None, raw_query=original_query), True
    
    # Pattern 4: Two words - likely "FirstName LastName" (high confidence)
    if len(words) == 2:
        # Check if second word is a known company
        if words[1].lower() in KNOWN_COMPANIES:
            return ParsedQuery(name=words[0], company=words[1], raw_query=original_query), True
        # Likely just a full name
        return ParsedQuery(name=query, company=None, raw_query=original_query), True
    
    # Pattern 5: Three+ words - check if last word is known company
    if len(words) >= 3:
        if words[-1].lower() in KNOWN_COMPANIES:
            name = " ".join(words[:-1])
            return ParsedQuery(name=name, company=words[-1], raw_query=original_query), True
    
    # Ambiguous: 3+ words, last word not a known company
    # e.g., "John Williams Netflix" where Netflix isn't in our list
    # Return a guess but mark as not confident
    # Heuristic: assume last word is company if it looks like one (capitalized, not common name)
    if len(words) >= 3:
        last_word = words[-1]
        # If last word is capitalized and doesn't look like a common name suffix
        common_name_parts = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"}
        if last_word[0].isupper() and last_word.lower() not in common_name_parts:
            name = " ".join(words[:-1])
            return ParsedQuery(name=name, company=last_word, raw_query=original_query), False
    
    # Default: treat entire query as name, not confident
    return ParsedQuery(name=query, company=None, raw_query=original_query), False


async def _llm_parse(query: str) -> ParsedQuery:
    """Use OpenAI to parse ambiguous queries."""
    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=100
        )
        
        content = response.choices[0].message.content.strip()
        
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        parsed = json.loads(content)
        
        return ParsedQuery(
            name=parsed.get("name"),
            company=parsed.get("company"),
            raw_query=query
        )
        
    except Exception as e:
        print(f"LLM parsing failed: {e}")
        # Return rule-based result even if not confident
        result, _ = _rule_based_parse(query)
        return result


async def parse_search_query(query: str) -> ParsedQuery:
    """
    Hybrid parser: Fast rules first, LLM only for ambiguous queries.
    
    - Simple patterns (comma, "at/from", known companies): ~0ms
    - Ambiguous queries (unknown company names): ~500ms via LLM
    """
    if not query or not query.strip():
        return ParsedQuery(raw_query=query or "")
    
    # Try fast rule-based parsing first
    result, is_confident = _rule_based_parse(query)
    
    if is_confident:
        return result
    
    # Only use LLM for ambiguous cases if available
    if OPENAI_AVAILABLE and _openai_client:
        return await _llm_parse(query)
    
    # No LLM available, return best-effort rule-based result
    return result
