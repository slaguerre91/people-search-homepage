"""Deterministic query parser for extracting name and company search intent."""

import re
from pydantic import BaseModel
from typing import Optional


class ParsedQuery(BaseModel):
    """Parsed search query with extracted name and company."""
    name: Optional[str] = None
    company: Optional[str] = None
    raw_query: str


# Known company names for fast matching (top 100 + tech companies)
KNOWN_COMPANIES = {
    # Tech giants
    "google", "alphabet", "microsoft", "apple", "amazon", "meta", "facebook", 
    "netflix", "oracle", "ibm", "intel", "cisco", "salesforce", "adobe", "nvidia",
    "tesla", "uber", "lyft", "airbnb", "spotify", "twitter", "x", "linkedin",
    "stripe", "square", "block", "shopify", "zoom", "slack", "dropbox", "github",
    "openai", "anthropic", "databricks", "snowflake", "palantir", "coinbase",
    "samsung", "sony", "dell", "hp", "lenovo", "qualcomm", "broadcom", "amd",
    "vmware", "servicenow", "workday", "splunk", "docusign", "twilio", "atlassian",
    
    # Fortune 100 / Major employers
    "walmart", "exxon", "exxonmobil", "chevron", "berkshire", "unitedhealth",
    "mckesson", "cvs", "amerisource", "costco", "cigna", "marathon", "phillips",
    "valero", "kroger", "walgreens", "homedepot", "home depot", "jpmorgan", 
    "chase", "bank of america", "bofa", "citi", "citibank", "wells fargo",
    "fannie mae", "verizon", "att", "at&t", "comcast", "target", "lowes", "lowe's",
    "ups", "fedex", "boeing", "lockheed", "raytheon", "northrop", "general dynamics",
    "ford", "gm", "general motors", "chrysler", "stellantis", "toyota", "honda",
    "humana", "centene", "elevance", "cardinal", "abbvie", "pfizer", "johnson",
    "merck", "bristol", "eli lilly", "lilly", "amgen", "gilead", "regeneron",
    "procter", "p&g", "unilever", "pepsi", "pepsico", "coca-cola", "coke",
    "tyson", "sysco", "kraft", "general mills", "kellogg", "mondelez",
    "disney", "warner", "paramount", "fox", "nbc", "universal", "paramount",
    "morgan stanley", "goldman", "blackrock", "fidelity", "schwab", "state street",
    "american express", "amex", "visa", "mastercard", "paypal", "capital one",
    "prudential", "metlife", "aig", "allstate", "progressive", "travelers",
    "delta", "united airlines", "american airlines", "southwest", "jetblue",
    "hilton", "marriott", "hyatt", "mgm", "wynn", "starbucks", "mcdonalds",
    "nike", "adidas", "under armour", "lululemon", "gap", "nordstrom", "macys",
    "caterpillar", "deere", "john deere", "3m", "honeywell", "ge", "siemens",
    "accenture", "deloitte", "pwc", "kpmg", "ey", "mckinsey", "bain", "bcg",
}

def clean_query_part(value: str) -> str:
    """Normalize user-typed query fragments."""
    return re.sub(r"\s+", " ", value.strip(" \t\n\r,")).strip()


def parse_name_company_candidates(query: str) -> list[tuple[str, str]]:
    """Return possible (name, company) pairs without using AI."""
    clean_query = clean_query_part(query)
    candidates: list[tuple[str, str]] = []

    if not clean_query:
        return candidates

    if "," in clean_query:
        name, company = clean_query.split(",", 1)
        name = clean_query_part(name)
        company = clean_query_part(company)
        if name and company:
            candidates.append((name, company))

    lowered = clean_query.lower()
    for keyword in (" at ", " from ", " @ "):
        if keyword in lowered:
            idx = lowered.index(keyword)
            name = clean_query_part(clean_query[:idx])
            company = clean_query_part(clean_query[idx + len(keyword):])
            if name and company:
                candidates.append((name, company))
            break

    split_query = re.sub(r"\s*,\s*", " ", clean_query)
    words = split_query.split()
    if len(words) >= 2:
        for split_index in range(1, len(words)):
            name = " ".join(words[:split_index])
            company = " ".join(words[split_index:])
            if len(name) >= 2 and len(company) >= 2:
                candidates.append((name, company))

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, company in candidates:
        key = (name.lower(), company.lower())
        if key not in seen:
            seen.add(key)
            deduped.append((name, company))
    return deduped


def _known_company_suffix(words: list[str]) -> Optional[tuple[str, str]]:
    """Find the longest known company suffix in a tokenized query."""
    for split_index in range(1, len(words)):
        name = " ".join(words[:split_index])
        company = " ".join(words[split_index:])
        if company.lower() in KNOWN_COMPANIES:
            return name, company
    return None


def _rule_based_parse(query: str) -> ParsedQuery:
    """Fast local parser for the most useful name/company query forms."""
    query = clean_query_part(query)
    original_query = query
    
    if not query:
        return ParsedQuery(raw_query=original_query)
    
    # Pattern 1: Comma separator - "John Smith, Oracle"
    if "," in query:
        parts = [p.strip() for p in query.split(",", 1)]
        return ParsedQuery(
            name=parts[0] if parts[0] else None,
            company=parts[1] if len(parts) > 1 and parts[1] else None,
            raw_query=original_query
        )
    
    # Pattern 2: Keywords "at", "from", "@" - "Sarah at Google"
    for keyword in [" at ", " from ", " @ "]:
        if keyword in query.lower():
            idx = query.lower().index(keyword)
            name = query[:idx].strip()
            company = query[idx + len(keyword):].strip()
            return ParsedQuery(
                name=name if name else None,
                company=company if company else None,
                raw_query=original_query
            )
    
    # Pattern 3: Single word - could be name or company
    words = query.split()
    if len(words) == 1:
        word_lower = words[0].lower()
        if word_lower in KNOWN_COMPANIES:
            return ParsedQuery(name=None, company=words[0], raw_query=original_query)
        return ParsedQuery(name=query, company=None, raw_query=original_query)
    
    # Pattern 4: Two words - usually "FirstName LastName", unless second is a company.
    if len(words) == 2:
        if words[1].lower() in KNOWN_COMPANIES:
            return ParsedQuery(name=words[0], company=words[1], raw_query=original_query)
        return ParsedQuery(name=query, company=None, raw_query=original_query)
    
    # Pattern 5: Three+ words with a known company suffix.
    if len(words) >= 3:
        known_suffix = _known_company_suffix(words)
        if known_suffix:
            name, company = known_suffix
            return ParsedQuery(name=name, company=company, raw_query=original_query)

        # Common leader lookup shape: first two words are a name and the rest is
        # a company fragment, e.g. "Samyr Laguerre City of Boston".
        return ParsedQuery(
            name=" ".join(words[:2]),
            company=" ".join(words[2:]),
            raw_query=original_query,
        )
    
    return ParsedQuery(name=query, company=None, raw_query=original_query)


async def parse_search_query(query: str) -> ParsedQuery:
    """Parse search intent locally without calling OpenAI."""
    if not query or not query.strip():
        return ParsedQuery(raw_query=query or "")

    return _rule_based_parse(query)
