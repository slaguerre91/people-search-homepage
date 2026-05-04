import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const APP_NAME = 'Leadmark';
const EXAMPLE_SEARCHES = [
  'Alex Chen, Stripe',
  'Maria Lopez at Google',
  'linkedin.com/in/name',
];
const PROFILE_ROUTE_RE = /^\/profiles\/([^/]+)\/?$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function buildSampleReviews() {
  const names = [
    'Jordan Lee', 'Priya Shah', 'Marcus Reed', 'Elena Torres', 'Sam Carter',
    'Nina Patel', 'Owen Brooks', 'Avery Kim', 'Maya Stone', 'Theo Grant',
    'Lena Brooks', 'Caleb Wright', 'Imani Cole', 'Riley Chen', 'Noah Singh',
    'Amara Scott', 'Julian Park', 'Sofia Rivera', 'Elliot Hayes', 'Tara Mills',
  ];
  const companies = [
    'Northstar Labs', 'Atlas Health', 'Cedar Systems', 'Brightline AI', 'HarborWorks',
    'Kite Financial', 'Fieldstone', 'Nova Retail', 'Pioneer Cloud', 'Summit Bio',
    'Meridian Studio', 'Urban Grid', 'Beacon Data', 'Clearpath', 'Lumen Foods',
    'Arcadia Robotics', 'Evergreen Bank', 'Pulse Media', 'Keystone Energy', 'VistaCare',
  ];
  const quotes = [
    'Clear priorities, fast feedback, and no guessing games.',
    'Strong operator who made room for people to do their best work.',
    'Great strategy conversations, but execution support varied by team.',
    'Set a high bar while keeping the team calm under pressure.',
    'Transparent about tradeoffs and quick to unblock decisions.',
    'Excellent at coaching senior ICs through messy product moments.',
    'Cared about outcomes, but the meeting load could get heavy.',
    'Direct communicator with a thoughtful approach to career growth.',
    'Built trust by following through on hard conversations.',
    'Ambitious roadmap, clear ownership, and useful retrospectives.',
  ];

  return Array.from({ length: 500 }, (_, index) => ({
    id: `sample-review-${index}`,
    name: names[index % names.length],
    company: companies[(index * 7) % companies.length],
    rating: 3 + ((index * 11) % 3),
    quote: quotes[(index * 13) % quotes.length],
  }));
}

const SAMPLE_REVIEWS = buildSampleReviews();

function profileIdFromPath(pathname = window.location.pathname) {
  const match = pathname.match(PROFILE_ROUTE_RE);
  return match ? decodeURIComponent(match[1]) : null;
}

function profilePath(id) {
  return `/profiles/${encodeURIComponent(id)}`;
}

function setBrowserPath(path, { replace = false } = {}) {
  if (window.location.pathname === path) return;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', path);
}

function getToken() {
  return localStorage.getItem('authToken');
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function cleanText(value) {
  return String(value || '')
    .replace(/\s*\|\s*LinkedIn.*$/i, '')
    .replace(/\s+LinkedIn\s*$/i, '')
    .replace(/\s*\.\.\..*$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function isMissingMetadata(value) {
  return !value || /^(unknown|n\/a|none|null|undefined)$/i.test(String(value).trim());
}

function toDisplayCase(value, { acronymWords = [], uppercaseTrailingRegion = false } = {}) {
  const text = cleanText(value);
  if (isMissingMetadata(text)) return '';
  if (/[A-Z]/.test(text)) return text;
  let result = text.replace(/\b[a-z][a-z'&-]*/g, (word) => {
    const lower = word.toLowerCase();
    if (acronymWords.includes(lower)) {
      return lower.toUpperCase();
    }
    if (['of', 'and', 'or', 'the', 'at', 'in', 'for'].includes(lower)) return lower;
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }).replace(/^([a-z])/, (match) => match.toUpperCase());
  if (uppercaseTrailingRegion) {
    result = result.replace(/,\s*([A-Za-z]{2,3})$/, (_, region) => `, ${region.toUpperCase()}`);
  }
  return result;
}

function cleanCompany(company, name = '') {
  let value = cleanText(company);
  if (isMissingMetadata(value)) return '';
  if (name && value.toLowerCase().includes(name.toLowerCase())) {
    value = value.slice(0, value.toLowerCase().indexOf(name.toLowerCase())).trim();
  }
  if (value.includes(' - ')) value = value.split(' - ')[0].trim();
  return toDisplayCase(value, { acronymWords: ['llc', 'inc', 'plc', 'gmbh'] });
}

function cleanLocation(location) {
  return toDisplayCase(location, { uppercaseTrailingRegion: true });
}

function profileMetadataLine(company, location, name = '') {
  return [cleanCompany(company, name), cleanLocation(location)].filter(Boolean).join(' · ');
}

function cleanName(name, company = '') {
  let value = cleanText(name);
  if (value.includes(' - ')) value = value.split(' - ')[0].trim();
  if (company && value.toLowerCase().startsWith(company.toLowerCase())) {
    value = value.slice(company.length).trim();
  }
  return value || 'LinkedIn Member';
}

function cleanRole(role, name = '') {
  let value = cleanText(role);
  if (value.includes(' - ')) {
    const [beforeDash, afterDash] = value.split(' - ', 2);
    const looksLikeRole = /\b(chief|officer|director|manager|engineer|lead|head|president|founder|staff|policy|people|operations)\b/i.test(afterDash);
    if (!name || beforeDash.toLowerCase().includes(name.toLowerCase()) || looksLikeRole) value = afterDash.trim();
  }
  if (name && value.toLowerCase().startsWith(name.toLowerCase())) {
    value = value.slice(name.length).replace(/^[-,\s]+/, '').trim();
  }
  return value || 'LinkedIn Member';
}

function linkedInUrlFromBio(bio) {
  return String(bio || '').match(/https?:\/\/(?:www\.)?linkedin\.com\/in\/[^\s]+/i)?.[0] || '';
}

function isLinkedInProfileUrl(value) {
  const input = String(value || '').trim();
  if (!input || /\s/.test(input)) return false;
  try {
    const url = new URL(/^https?:\/\//i.test(input) ? input : `https://${input}`);
    const host = url.hostname.toLowerCase();
    return (host === 'linkedin.com' || host === 'www.linkedin.com' || /^[a-z]{2,3}\.linkedin\.com$/i.test(host))
      && /^\/in\/[A-Za-z0-9_.%-]+\/?$/i.test(url.pathname);
  } catch {
    return false;
  }
}

function assetUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}

const PROFILE_IMAGE_TRANSFORMS = {
  autocomplete: 'c_fill,g_face,w_48,h_48,f_auto,q_auto',
  search: 'c_fill,g_face,w_80,h_80,f_auto,q_auto',
  profile: 'c_fill,g_face,w_240,h_240,f_auto,q_auto',
};

function profileImageUrl(path, size = 'search') {
  const url = assetUrl(path);
  const transform = PROFILE_IMAGE_TRANSFORMS[size];
  if (!url || !transform) return url;

  try {
    const parsed = new URL(url);
    if (!/res\.cloudinary\.com$/i.test(parsed.hostname)) return url;
    if (!parsed.pathname.includes('/image/upload/')) return url;
    parsed.pathname = parsed.pathname.replace('/image/upload/', `/image/upload/${transform}/`);
    return parsed.toString();
  } catch {
    return url;
  }
}

function ProfileAvatar({ name, avatarUrl, className = '', size = 'search' }) {
  const initial = cleanName(name).slice(0, 1).toUpperCase() || '?';
  return (
    <span className={`profile-thumb ${className}`.trim()} aria-hidden="true">
      {avatarUrl ? <img src={profileImageUrl(avatarUrl, size)} alt="" /> : initial}
    </span>
  );
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" focusable="false">
        <path d="M8 24V8h4v12h12v4H8Z" />
        <path d="M16 16V8h8v4h-4v4h-4Z" />
      </svg>
    </span>
  );
}

function LinkedInIcon({ className = '' }) {
  return (
    <svg className={`linkedin-icon ${className}`.trim()} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M20.45 20.45h-3.56v-5.58c0-1.33-.02-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.95v5.67H9.34V8.98h3.42v1.57h.05c.48-.9 1.64-1.85 3.37-1.85 3.61 0 4.27 2.37 4.27 5.46v6.29ZM5.32 7.41a2.07 2.07 0 1 1 0-4.14 2.07 2.07 0 0 1 0 4.14Zm1.78 13.04H3.54V8.98H7.1v11.47Z" />
    </svg>
  );
}

function LinkedInProfileLink({ href, label = 'Open LinkedIn profile' }) {
  if (!href) return null;
  return (
    <a className="linkedin-link" href={href} target="_blank" rel="noreferrer" aria-label={label} title={label}>
      <LinkedInIcon />
    </a>
  );
}

function reviewSummary(profile) {
  const count = profile?.review_count || 0;
  if (!count || profile.average_rating == null) return 'No reviews yet';
  return `${Number(profile.average_rating).toFixed(1)} (${count} ${count === 1 ? 'Review' : 'Reviews'})`;
}

function Stars({ value = 0, size = 'md' }) {
  const rounded = Math.round(Number(value) || 0);
  return (
    <span className={`stars stars-${size}`} aria-label={`${rounded} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={star <= rounded ? 'star filled' : 'star'}>
          {star <= rounded ? '★' : '☆'}
        </span>
      ))}
    </span>
  );
}

function App() {
  const [token, setToken] = useState(getToken());
  const [view, setView] = useState('search');
  const [query, setQuery] = useState('');
  const [dbResults, setDbResults] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [linkedInResults, setLinkedInResults] = useState([]);
  const [linkedInMeta, setLinkedInMeta] = useState({});
  const [profile, setProfile] = useState(null);
  const [verificationStatus, setVerificationStatus] = useState(null);
  const [showVerifyPrompt, setShowVerifyPrompt] = useState(false);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [authMode, setAuthMode] = useState(null);

  const signedIn = Boolean(token);

  useEffect(() => {
    if (token) localStorage.setItem('authToken', token);
    else localStorage.removeItem('authToken');
  }, [token]);

  useEffect(() => {
    function syncViewToUrl() {
      const profileId = profileIdFromPath();
      if (!profileId) {
        setProfile(null);
        setDraft(null);
        setView('search');
        return;
      }
      openProfile(profileId, { updateUrl: false });
    }

    syncViewToUrl();
    window.addEventListener('popstate', syncViewToUrl);
    return () => window.removeEventListener('popstate', syncViewToUrl);
  }, []);

  useEffect(() => {
    if (!token) {
      setVerificationStatus(null);
      setShowVerifyPrompt(false);
      return;
    }

    let cancelled = false;
    async function loadVerificationStatus() {
      try {
        const res = await fetch(`${API_BASE}/auth/me/verification`, {
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error('Could not load verification status');
        const data = await res.json();
        if (!cancelled) {
          setVerificationStatus(data);
          setShowVerifyPrompt(!data.has_verified_profile);
        }
      } catch {
        if (!cancelled) {
          setVerificationStatus(null);
          setShowVerifyPrompt(false);
        }
      }
    }
    loadVerificationStatus();

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    const searchQuery = query.trim();
    if (!searchQuery || view !== 'search') {
      setSuggestions([]);
      if (!searchQuery) {
        setDbResults([]);
        setLinkedInResults([]);
        setLinkedInMeta({});
        setMessage('');
      }
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/search/autocomplete?q=${encodeURIComponent(searchQuery)}`, {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error('Autocomplete failed');
        const people = await res.json();
        setSuggestions(people);
      } catch (error) {
        if (error.name !== 'AbortError') setSuggestions([]);
      }
    }, 180);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, view]);

  async function searchDatabase(searchQuery) {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(searchQuery)}`);
    if (!res.ok) throw new Error('Could not search saved profiles');
    const people = await res.json();
    setDbResults(people);
    return people;
  }

  async function runSearch(event, forcedQuery = query) {
    event?.preventDefault();
    const searchQuery = forcedQuery.trim();
    if (!searchQuery) {
      setDbResults([]);
      setLinkedInResults([]);
      setLinkedInMeta({});
      setSuggestions([]);
      setSuggestionsOpen(false);
      setMessage('');
      setView('search');
      return;
    }
    setLoading(true);
    setMessage('');
    setLinkedInResults([]);
    setLinkedInMeta({});
    setView('search');
    setSuggestionsOpen(false);
    try {
      if (isLinkedInProfileUrl(searchQuery)) {
        setDbResults([]);
        await searchLinkedIn(searchQuery);
        return;
      }
      const people = await searchDatabase(searchQuery);
      if (searchQuery && !people.length) {
        await searchLinkedIn(searchQuery);
      }
    } catch {
      setMessage('Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  async function searchLinkedIn(searchQuery = query) {
    const q = searchQuery.trim();
    if (!q) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/search/linkedin?q=${encodeURIComponent(q)}`);
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || 'LinkedIn search failed');
      }
      const data = await res.json();
      const profiles = await hydrateLinkedInProfiles(data.profiles || []);
      setLinkedInResults(profiles);
      setLinkedInMeta({
        parsedName: data.parsed_name,
        parsedCompany: data.parsed_company,
      });
      if (profiles.some((profile) => profile.url_verification === 'unverified')) {
        setMessage('We could not independently verify this LinkedIn URL. Open it to confirm before reviewing.');
      }
    } catch (error) {
      setMessage(error.message || 'Could not search LinkedIn.');
    } finally {
      setLoading(false);
    }
  }

  async function hydrateLinkedInProfiles(profiles) {
    const missingSavedAvatars = profiles.filter((profile) => (
      profile.existing_profile_id
      && !profile.avatar_url
      && !profile.existing_profile_avatar_url
    ));

    if (!missingSavedAvatars.length) return profiles;

    const savedProfiles = await Promise.all(
      missingSavedAvatars.map(async (profile) => {
        try {
          const res = await fetch(`${API_BASE}/profiles/${profile.existing_profile_id}`);
          if (!res.ok) return null;
          return await res.json();
        } catch {
          return null;
        }
      })
    );

    const savedById = new Map(
      savedProfiles
        .filter(Boolean)
        .map((profile) => [profile.id, profile])
    );

    return profiles.map((profile) => {
      const savedProfile = savedById.get(profile.existing_profile_id);
      if (!savedProfile) return profile;
      return {
        ...profile,
        avatar_url: profile.avatar_url || savedProfile.avatar_url,
        existing_profile_avatar_url: profile.existing_profile_avatar_url || savedProfile.avatar_url,
      };
    });
  }

  function goHome({ replace = false, keepMessage = false } = {}) {
    setBrowserPath('/', { replace });
    setProfile(null);
    setDraft(null);
    if (!keepMessage) setMessage('');
    setView('search');
  }

  async function openProfile(id, { updateUrl = true, replaceUrl = false } = {}) {
    const normalizedId = String(id || '').trim();
    if (!UUID_RE.test(normalizedId)) {
      setProfile(null);
      setMessage('Profile link is invalid.');
      goHome({ replace: true, keepMessage: true });
      return false;
    }

    setLoading(true);
    setMessage('');
    setSuggestionsOpen(false);
    try {
      const res = await fetch(`${API_BASE}/profiles/${normalizedId}`);
      if (res.status === 404) throw new Error('not-found');
      if (!res.ok) throw new Error('load-failed');
      const data = await res.json();
      setProfile(data);
      setView('profile');
      if (updateUrl) setBrowserPath(profilePath(normalizedId), { replace: replaceUrl });
      return true;
    } catch {
      setProfile(null);
      setMessage('Profile not found or could not be loaded.');
      goHome({ replace: true, keepMessage: true });
      return false;
    } finally {
      setLoading(false);
    }
  }

  function buildLinkedInDraft(result) {
    const company = result.company || 'Unknown';
    const name = cleanName(result.name, cleanCompany(company, result.name));
    const location = result.location || 'Unknown';
    return {
      name,
      company,
      role: cleanRole(result.title, name),
      location,
      bio: '',
      linkedin_url: result.url || '',
    };
  }

  async function startLinkedInReview(result) {
    const nextDraft = buildLinkedInDraft(result);
    setDraft(nextDraft);
    setView('linkedin-review');
  }

  async function submitReview(profileId, rating, comment) {
    setMessage('');
    if (!signedIn) {
      setAuthMode('login');
      return false;
    }
    const res = await fetch(`${API_BASE}/profiles/${profileId}/reviews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ rating, comment }),
    });
    if (res.status === 401 || res.status === 403) {
      setToken('');
      setMessage('Please log in to post a review.');
      setAuthMode('login');
      return false;
    }
    if (res.status === 409) {
      setMessage('You have already reviewed this profile.');
      return false;
    }
    if (!res.ok) {
      setMessage('Failed to save review.');
      return false;
    }
    await openProfile(profileId);
    return true;
  }

  async function submitLinkedInReview(rating, comment) {
    setMessage('');
    if (!signedIn) {
      setAuthMode('login');
      return false;
    }
    const payload = {
      profile: {
        name: draft.name,
        company: draft.company,
        role: draft.role,
        location: draft.location,
        bio: draft.bio,
        linkedin_url: draft.linkedin_url,
      },
      review: { rating, comment },
    };

    const res = await fetch(`${API_BASE}/linkedin/reviews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (res.status === 401 || res.status === 403) {
      setToken('');
      setMessage('Please log in to post a review.');
      setAuthMode('login');
      return false;
    }
    if (res.status === 409) {
      setMessage('You have already reviewed this profile.');
      return false;
    }
    if (!res.ok) {
      setMessage('Failed to save review.');
      return false;
    }
    const savedProfile = await res.json();
    setProfile(savedProfile);
    setBrowserPath(profilePath(savedProfile.id));
    setView('profile');
    return true;
  }

  async function submitProfileVerification(profileId, profilePhoto, badgePhoto) {
    setMessage('');
    if (!signedIn) {
      setAuthMode('login');
      return false;
    }

    const formData = new FormData();
    formData.append('profile_photo', profilePhoto);
    formData.append('badge_photo', badgePhoto);

    const res = await fetch(`${API_BASE}/profiles/${profileId}/verify`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    if (res.status === 401 || res.status === 403) {
      setToken('');
      setMessage('Please log in to verify your profile.');
      setAuthMode('login');
      return false;
    }
    if (res.status === 409) {
      const data = await res.json().catch(() => ({}));
      setMessage(data.detail || 'This account has already verified a leader profile.');
      return false;
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setMessage(data.detail || 'Could not verify this profile.');
      return false;
    }

    const data = await res.json();
    setVerificationStatus({ has_verified_profile: true, profile: data.profile });
    setShowVerifyPrompt(false);
    setProfile(data.profile);
    setBrowserPath(profilePath(data.profile.id));
    setView('profile');
    return true;
  }

  function signOut() {
    setToken('');
    setProfile(null);
    setVerificationStatus(null);
    setShowVerifyPrompt(false);
    goHome();
  }

  return (
    <div className="app">
      <Header
        signedIn={signedIn}
        onLogin={() => setAuthMode('login')}
        onSignup={() => setAuthMode('signup')}
        onSignOut={signOut}
        onHome={() => goHome()}
      />

      <main>
        {view === 'search' && (
          <SearchView
            query={query}
            setQuery={setQuery}
            suggestions={suggestions}
            suggestionsOpen={suggestionsOpen}
            setSuggestionsOpen={setSuggestionsOpen}
            dbResults={dbResults}
            linkedInResults={linkedInResults}
            linkedInMeta={linkedInMeta}
            loading={loading}
            message={message}
            showVerifyPrompt={showVerifyPrompt}
            verifiedProfile={verificationStatus?.profile}
            onVerify={() => {
              setMessage('');
              setBrowserPath('/');
              setView('verify-profile');
            }}
            onDismissVerify={() => setShowVerifyPrompt(false)}
            onSearch={runSearch}
            onManualLinkedIn={() => searchLinkedIn(query)}
            onProfile={openProfile}
            onLinkedInReview={startLinkedInReview}
          />
        )}

        {view === 'profile' && profile && (
          <ProfileView
            profile={profile}
            onBack={() => goHome()}
            onReview={submitReview}
            signedIn={signedIn}
            onLogin={() => setAuthMode('login')}
            message={message}
          />
        )}

        {view === 'linkedin-review' && draft && (
          <LinkedInReviewView
            draft={draft}
            onBack={() => goHome()}
            onSubmit={submitLinkedInReview}
            signedIn={signedIn}
            onLogin={() => setAuthMode('login')}
            message={message}
          />
        )}

        {view === 'verify-profile' && (
          <VerifyProfileView
            onBack={() => goHome()}
            onSearch={searchDatabase}
            onSubmit={submitProfileVerification}
            message={message}
          />
        )}
      </main>

      {authMode && (
        <AuthDialog
          mode={authMode}
          setMode={setAuthMode}
          onClose={() => setAuthMode(null)}
          onToken={setToken}
        />
      )}
    </div>
  );
}

function Header({ signedIn, onLogin, onSignup, onSignOut, onHome }) {
  return (
    <header className="nav">
      <button className="brand" type="button" onClick={onHome}>
        <BrandMark />
        <span>{APP_NAME}</span>
      </button>
      <div className="nav-actions">
        {signedIn ? (
          <button className="btn secondary" onClick={onSignOut}>Sign out</button>
        ) : (
          <>
            <button className="btn primary" onClick={onLogin}>Log In</button>
            <button className="btn secondary" onClick={onSignup}>Sign up</button>
          </>
        )}
      </div>
    </header>
  );
}

function SearchView({
  query,
  setQuery,
  suggestions,
  suggestionsOpen,
  setSuggestionsOpen,
  dbResults,
  linkedInResults,
  linkedInMeta,
  loading,
  message,
  showVerifyPrompt,
  verifiedProfile,
  onVerify,
  onDismissVerify,
  onSearch,
  onManualLinkedIn,
  onProfile,
  onLinkedInReview,
}) {
  const hasQuery = query.trim().length > 0;
  const noSavedResults = hasQuery && !loading && dbResults.length === 0;
  const showSuggestions = suggestionsOpen && hasQuery && suggestions.length > 0;

  return (
    <section className="search-page">
      {showVerifyPrompt && !verifiedProfile && (
        <section className="verify-prompt">
          <div>
            <strong>Verify your leader profile</strong>
            <p>Add a profile photo and badge proof so people can recognize the official profile.</p>
          </div>
          <div className="verify-prompt-actions">
            <button className="btn primary small" type="button" onClick={onVerify}>Verify</button>
            <button className="text-btn" type="button" onClick={onDismissVerify}>Later</button>
          </div>
        </section>
      )}

      <form className="search-shell" onSubmit={onSearch}>
        <input
          value={query}
          onChange={(event) => {
            const nextQuery = event.target.value;
            setQuery(nextQuery);
            setSuggestionsOpen(true);
          }}
          onFocus={() => setSuggestionsOpen(true)}
          onBlur={() => window.setTimeout(() => setSuggestionsOpen(false), 150)}
          placeholder="Type a name, company"
          autoComplete="off"
        />
        {query && (
          <button
            type="button"
            className="clear-btn"
            onClick={() => {
              setQuery('');
              setSuggestionsOpen(false);
            }}
          >
            ×
          </button>
        )}
        {showSuggestions && (
          <div className="suggestions" role="listbox">
            {suggestions.map((person) => (
              <button
                type="button"
                className="suggestion-row"
                key={person.id}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => onProfile(person.id)}
              >
                <span className="row-main">
                  <ProfileAvatar
                    name={person.name}
                    avatarUrl={person.avatar_url}
                    className="profile-thumb-sm"
                    size="autocomplete"
                  />
                  <span>
                    <strong>{cleanName(person.name, person.company)}</strong>
                    {cleanCompany(person.company, person.name) && <small>{cleanCompany(person.company, person.name)}</small>}
                  </span>
                </span>
                {cleanLocation(person.location) && <small>{cleanLocation(person.location)}</small>}
              </button>
            ))}
          </div>
        )}
      </form>

      {!hasQuery && (
        <section className="home-state" aria-label={`${APP_NAME} introduction`}>
          <h1>Find reviews of leaders before you work with them.</h1>
          <p className="home-copy">Search by name, company, or a LinkedIn profile URL.</p>
          <div className="example-searches" aria-label="Example searches">
            {EXAMPLE_SEARCHES.map((example) => (
              <span
                className="example-chip"
                key={example}
              >
                {example}
              </span>
            ))}
          </div>
          <SampleReviewCarousel />
        </section>
      )}

      {message && <p className="notice">{message}</p>}
      {loading && <p className="notice">Searching...</p>}

      {dbResults.length > 0 && (
        <ResultSection title="Saved Profiles">
          {dbResults.map((person) => (
            <ProfileResult key={person.id} profile={person} onClick={() => onProfile(person.id)} />
          ))}
          {hasQuery && (
            <div className="result-actions">
              <button className="btn secondary" onClick={onManualLinkedIn}>Search LinkedIn</button>
            </div>
          )}
        </ResultSection>
      )}

      {noSavedResults && !linkedInResults.length && !message && (
        <section className="empty-state">
          <p>We didn't find any leader by that name... yet.</p>
          <button className="btn primary" onClick={onManualLinkedIn}>Search LinkedIn</button>
        </section>
      )}

      {linkedInResults.length > 0 && (
        <ResultSection title="LinkedIn Matches">
          {linkedInMeta.parsedName || linkedInMeta.parsedCompany ? (
            <p className="parsed">
              Searching for {[linkedInMeta.parsedName, linkedInMeta.parsedCompany].filter(Boolean).join(' · ')}
            </p>
          ) : null}
          {linkedInResults.map((result) => {
            const isUnverifiedUrl = result.url_verification === 'unverified';
            const company = isUnverifiedUrl ? 'Unverified LinkedIn URL' : cleanCompany(result.company || '', result.name);
            const name = cleanName(result.name, company);
            const hasSavedProfile = Boolean(result.existing_profile_id);
            const savedAvatarUrl = result.existing_profile_avatar_url || result.avatar_url;
            const reviewCount = result.existing_profile_review_count || 0;
            const rating = result.existing_profile_average_rating;
            return (
              <article className="linkedin-card" key={result.url}>
                <div className="linkedin-card-main">
                  {hasSavedProfile && savedAvatarUrl && (
                    <ProfileAvatar
                      name={name}
                      avatarUrl={savedAvatarUrl}
                      className="linkedin-avatar"
                    />
                  )}
                  <div className="linkedin-copy">
                    {hasSavedProfile ? (
                      <button className="linkedin-name-btn" type="button" onClick={() => onProfile(result.existing_profile_id)}>
                        {name}
                      </button>
                    ) : (
                      <strong>{name}</strong>
                    )}
                    {company && <p>{company}</p>}
                    {hasSavedProfile && (
                      <small className="muted">
                        Saved profile · {rating == null ? 'No reviews yet' : `${Number(rating).toFixed(1)} (${reviewCount})`}
                      </small>
                    )}
                  </div>
                  <LinkedInProfileLink href={result.url} />
                </div>
                <button
                  className="btn primary small"
                  onClick={() => hasSavedProfile ? onProfile(result.existing_profile_id) : onLinkedInReview(result)}
                >
                  {hasSavedProfile ? 'View Saved Profile' : 'Review'}
                </button>
              </article>
            );
          })}
        </ResultSection>
      )}
    </section>
  );
}

function pickSampleReviews() {
  const picked = new Set();
  while (picked.size < 3) {
    picked.add(Math.floor(Math.random() * SAMPLE_REVIEWS.length));
  }
  return [...picked].map((index) => SAMPLE_REVIEWS[index]);
}

function SampleReviewCarousel() {
  const [reviews, setReviews] = useState(() => pickSampleReviews());
  const [isChanging, setIsChanging] = useState(false);

  useEffect(() => {
    let transitionTimer;
    const timer = window.setInterval(() => {
      setIsChanging(true);
      transitionTimer = window.setTimeout(() => {
        setReviews(pickSampleReviews());
        setIsChanging(false);
      }, 260);
    }, 5200);

    return () => {
      window.clearInterval(timer);
      window.clearTimeout(transitionTimer);
    };
  }, []);

  return (
    <section className="example-reviews" aria-label="Review themes">
      <h2>What a review can capture</h2>
      <div className={`example-review-grid ${isChanging ? 'is-changing' : ''}`}>
        {reviews.map((review) => (
          <article className="example-review-card" key={review.id}>
            <div className="example-review-head">
              <div>
                <strong>{review.name}</strong>
                <small>{review.company}</small>
              </div>
              <Stars value={review.rating} size="sm" />
            </div>
            <p>{review.quote}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ResultSection({ title, children }) {
  return (
    <section className="results-section">
      <h2>{title}</h2>
      <div className="results-list">{children}</div>
    </section>
  );
}

function ProfileResult({ profile, onClick }) {
  const company = cleanCompany(profile.company, profile.name);
  const name = cleanName(profile.name, company);
  return (
    <button className="profile-row" onClick={onClick}>
      <span className="row-main">
        <ProfileAvatar name={name} avatarUrl={profile.avatar_url} />
        <span>
          <strong>{name}</strong>
          {(company || profile.is_verified) && (
            <small>
              {company} {profile.is_verified ? <span className="verified-inline">Verified</span> : null}
            </small>
          )}
        </span>
      </span>
      <span className="row-rating">{reviewSummary(profile)}</span>
    </button>
  );
}

function ProfileView({ profile, onBack, onReview, signedIn, onLogin, message }) {
  const company = cleanCompany(profile.company, profile.name);
  const name = cleanName(profile.name, company);
  const location = cleanLocation(profile.location);
  const average = profile.average_rating || 0;
  const linkedinUrl = profile.linkedin_url || linkedInUrlFromBio(profile.bio);

  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>← Back to Search</button>
      <article className="leader-card">
        <div className="cover" />
        <div className="avatar">
          {profile.avatar_url ? <img src={profileImageUrl(profile.avatar_url, 'profile')} alt="" /> : name.slice(0, 1)}
        </div>
        <div className="leader-info">
          <h1>
            {name}
            {profile.is_verified && <span className="verified-badge" title="Verified leader profile">✓</span>}
          </h1>
          {company && <p>{company}</p>}
          {location && <p>{location}</p>}
          <div className="rating-line">
            <Stars value={average} />
            <strong>{reviewSummary(profile)}</strong>
          </div>
          <div className="leader-actions">
            <LinkedInProfileLink href={linkedinUrl} />
          </div>
        </div>
      </article>

      {message && <p className="notice">{message}</p>}
      <ReviewForm
        signedIn={signedIn}
        onLogin={onLogin}
        onSubmit={(rating, comment) => onReview(profile.id, rating, comment)}
      />

      <section className="review-list">
        <h2>Reviews</h2>
        {profile.reviews?.length ? profile.reviews.map((review) => (
          <article key={review.id} className="review-card">
            <strong>{review.author}</strong>
            <Stars value={review.rating} size="sm" />
            <p>{review.comment}</p>
          </article>
        )) : <p className="muted">No reviews yet.</p>}
      </section>
    </section>
  );
}

function LinkedInReviewView({
  draft,
  onBack,
  onSubmit,
  signedIn,
  onLogin,
  message,
}) {
  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>← Back to Search</button>
      <article className="confirm-card">
        <h1>Confirm Leader</h1>
        <strong>{draft.name}</strong>
        {cleanCompany(draft.company, draft.name) && <p>{cleanCompany(draft.company, draft.name)}</p>}
        {cleanLocation(draft.location) && <p>{cleanLocation(draft.location)}</p>}
        {draft.linkedin_url && (
          <a className="linkedin-text-link" href={draft.linkedin_url} target="_blank" rel="noreferrer">
            <LinkedInIcon />
            <span>LinkedIn Profile</span>
          </a>
        )}
      </article>

      {message && <p className="notice">{message}</p>}
      <ReviewForm signedIn={signedIn} onLogin={onLogin} onSubmit={onSubmit} submitLabel="Save New Profile and Review" />
    </section>
  );
}

function VerifyProfileView({ onBack, onSearch, onSubmit, message }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [badgePhoto, setBadgePhoto] = useState(null);
  const [localMessage, setLocalMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function search(event) {
    event.preventDefault();
    const searchQuery = query.trim();
    if (!searchQuery) return;
    setLoading(true);
    setLocalMessage('');
    setSelectedProfile(null);
    try {
      const people = await onSearch(searchQuery);
      const unverifiedPeople = people.filter((person) => !person.is_verified);
      setResults(unverifiedPeople);
      if (!people.length) {
        setLocalMessage('No saved profiles matched that search.');
      } else if (!unverifiedPeople.length) {
        setLocalMessage('All matching profiles are already verified.');
      }
    } catch {
      setResults([]);
      setLocalMessage('Could not search saved profiles.');
    } finally {
      setLoading(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    setLocalMessage('');
    if (!selectedProfile) {
      setLocalMessage('Choose the profile that belongs to you.');
      return;
    }
    if (!profilePhoto || !badgePhoto) {
      setLocalMessage('Upload both photos to verify your profile.');
      return;
    }
    const saved = await onSubmit(selectedProfile.id, profilePhoto, badgePhoto);
    if (!saved) setLocalMessage('');
  }

  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>← Back to Search</button>
      <article className="verify-card">
        <h1>Verify Leader Profile</h1>
        <p className="muted">Find your saved profile, add the photo people should see, and upload a badge photo for later verification review.</p>

        <form className="verify-search" onSubmit={search}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your name or company" />
          <button className="btn primary" type="submit">{loading ? 'Searching...' : 'Search'}</button>
        </form>

        {results.length > 0 && (
          <div className="verify-results">
            {results.map((person) => (
              <label className={`choice-row ${selectedProfile?.id === person.id ? 'selected' : ''}`} key={person.id}>
                <input
                  type="radio"
                  name="verify-profile"
                  checked={selectedProfile?.id === person.id}
                  onChange={() => setSelectedProfile(person)}
                />
                <span>
                  <strong>{cleanName(person.name, person.company)}</strong>
                  {profileMetadataLine(person.company, person.location, person.name) && (
                    <small>{profileMetadataLine(person.company, person.location, person.name)}</small>
                  )}
                </span>
              </label>
            ))}
          </div>
        )}

        <form className="verify-upload" onSubmit={submit}>
          <label>
            <span>Profile photo</span>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setProfilePhoto(event.target.files?.[0] || null)} />
          </label>
          <label>
            <span>Company badge photo</span>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setBadgePhoto(event.target.files?.[0] || null)} />
          </label>
          {(localMessage || message) && <p className="notice inline-notice">{localMessage || message}</p>}
          <button className="btn primary" type="submit">Verify Profile</button>
        </form>
      </article>
    </section>
  );
}

function ReviewForm({ signedIn, onLogin, onSubmit, submitLabel = 'Submit Review' }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (!signedIn) {
      onLogin?.();
      return;
    }
    if (!comment.trim()) return;
    const saved = await onSubmit(rating, comment.trim());
    if (saved) setComment('');
  }

  return (
    <form className="review-form-card" onSubmit={submit}>
      <h2>Add a Review</h2>
      <select value={rating} onChange={(event) => setRating(Number(event.target.value))}>
        <option value={5}>5 stars</option>
        <option value={4}>4 stars</option>
        <option value={3}>3 stars</option>
        <option value={2}>2 stars</option>
        <option value={1}>1 star</option>
      </select>
      <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Write your review..." required />
      <button className="btn primary" type="submit">{signedIn ? submitLabel : 'Log In to Review'}</button>
    </form>
  );
}

function AuthDialog({ mode, setMode, onClose, onToken }) {
  const isLogin = mode === 'login';
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    avatar_url: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const title = isLogin ? 'Log In' : 'Sign Up';

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setSuccess('');
    try {
      if (isLogin) {
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ username: form.email, password: form.password }),
        });
        if (!res.ok) throw new Error('Invalid credentials');
        const data = await res.json();
        onToken(data.access_token);
        onClose();
      } else {
        const payload = {
          email: form.email,
          password: form.password,
          first_name: form.first_name,
          last_name: form.last_name,
        };
        if (form.avatar_url) payload.avatar_url = form.avatar_url;
        const res = await fetch(`${API_BASE}/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Could not create account');
        setSuccess('Account created. You can log in now.');
        setMode('login');
      }
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="dialog-backdrop" role="dialog" aria-modal="true">
      <form className="auth-dialog" onSubmit={submit}>
        <button className="dialog-close" type="button" onClick={onClose}>×</button>
        <h2>{title}</h2>
        {!isLogin && (
          <div className="auth-grid">
            <input value={form.first_name} onChange={(e) => update('first_name', e.target.value)} placeholder="First name" required />
            <input value={form.last_name} onChange={(e) => update('last_name', e.target.value)} placeholder="Last name" required />
          </div>
        )}
        <input value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="Email" type="email" required />
        <input value={form.password} onChange={(e) => update('password', e.target.value)} placeholder="Password" type="password" required />
        {!isLogin && (
          <input value={form.avatar_url} onChange={(e) => update('avatar_url', e.target.value)} placeholder="Avatar URL (optional)" />
        )}
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <button className="btn dark" type="submit">{title}</button>
        <button className="text-btn" type="button" onClick={() => setMode(isLogin ? 'signup' : 'login')}>
          {isLogin ? 'Need an account? Sign up' : 'Already have an account? Log in'}
        </button>
      </form>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
