import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

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

function cleanCompany(company, name = '') {
  let value = cleanText(company);
  if (name && value.toLowerCase().includes(name.toLowerCase())) {
    value = value.slice(0, value.toLowerCase().indexOf(name.toLowerCase())).trim();
  }
  if (value.includes(' - ')) value = value.split(' - ')[0].trim();
  return value || 'Unknown';
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

function assetUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
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
  const [existingMatches, setExistingMatches] = useState([]);
  const [selectedExistingId, setSelectedExistingId] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [authMode, setAuthMode] = useState(null);

  const signedIn = Boolean(token);

  useEffect(() => {
    if (token) localStorage.setItem('authToken', token);
    else localStorage.removeItem('authToken');
  }, [token]);

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
    setLoading(true);
    setMessage('');
    setLinkedInResults([]);
    setLinkedInMeta({});
    setView('search');
    setSuggestionsOpen(false);
    try {
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
      if (!res.ok) throw new Error('LinkedIn search failed');
      const data = await res.json();
      setLinkedInResults(data.profiles || []);
      setLinkedInMeta({
        parsedName: data.parsed_name,
        parsedCompany: data.parsed_company,
      });
    } catch {
      setMessage('Could not search LinkedIn.');
    } finally {
      setLoading(false);
    }
  }

  async function openProfile(id) {
    setLoading(true);
    setSuggestionsOpen(false);
    try {
      const res = await fetch(`${API_BASE}/profiles/${id}`);
      if (!res.ok) throw new Error('Profile not found');
      const data = await res.json();
      setProfile(data);
      setView('profile');
    } catch {
      setMessage('Profile not found.');
    } finally {
      setLoading(false);
    }
  }

  function buildLinkedInDraft(result) {
    const company = cleanCompany(result.company || linkedInMeta.parsedCompany || '', result.name);
    const name = cleanName(result.name, company);
    const location = result.location || 'Unknown';
    return {
      name,
      company,
      role: cleanRole(result.title, name),
      location,
      bio: result.url ? `LinkedIn profile: ${result.url}` : '',
      url: result.url || '',
    };
  }

  async function startLinkedInReview(result) {
    const nextDraft = buildLinkedInDraft(result);
    setDraft(nextDraft);
    setSelectedExistingId('new');
    setExistingMatches([]);
    setView('linkedin-review');
    try {
      const matches = await searchDatabase(nextDraft.name);
      setExistingMatches(matches.slice(0, 5));
    } catch {
      setExistingMatches([]);
    }
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
      },
      review: { rating, comment },
    };
    if (selectedExistingId && selectedExistingId !== 'new') payload.existing_profile_id = selectedExistingId;

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
    setView('profile');
    return true;
  }

  async function createProfileFromNoResult() {
    const name = query.trim();
    if (!name) return;
    const company = window.prompt('Company name?');
    if (!company) return;
    const location = window.prompt('Location?') || 'Unknown';
    const role = 'Leader';
    const res = await fetch(`${API_BASE}/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, company, role, location, bio: '' }),
    });
    if (res.ok) {
      const created = await res.json();
      setProfile(created);
      setView('profile');
    }
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
    setView('profile');
    return true;
  }

  function signOut() {
    setToken('');
    setProfile(null);
    setVerificationStatus(null);
    setShowVerifyPrompt(false);
    setView('search');
  }

  return (
    <div className="app">
      <Header
        signedIn={signedIn}
        onLogin={() => setAuthMode('login')}
        onSignup={() => setAuthMode('signup')}
        onSignOut={signOut}
        onHome={() => setView('search')}
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
              setView('verify-profile');
            }}
            onDismissVerify={() => setShowVerifyPrompt(false)}
            onSearch={runSearch}
            onManualLinkedIn={() => searchLinkedIn(query)}
            onProfile={openProfile}
            onLinkedInReview={startLinkedInReview}
            onAddLeader={createProfileFromNoResult}
          />
        )}

        {view === 'profile' && profile && (
          <ProfileView
            profile={profile}
            onBack={() => setView('search')}
            onReview={submitReview}
            signedIn={signedIn}
            onLogin={() => setAuthMode('login')}
            message={message}
          />
        )}

        {view === 'linkedin-review' && draft && (
          <LinkedInReviewView
            draft={draft}
            matches={existingMatches}
            selectedExistingId={selectedExistingId}
            onSelectExisting={setSelectedExistingId}
            onBack={() => setView('search')}
            onSubmit={submitLinkedInReview}
            signedIn={signedIn}
            onLogin={() => setAuthMode('login')}
            message={message}
          />
        )}

        {view === 'verify-profile' && (
          <VerifyProfileView
            onBack={() => setView('search')}
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
      <button className="brand" type="button" onClick={onHome}>SumoImperium</button>
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
  onAddLeader,
}) {
  const hasQuery = query.trim().length > 0;
  const noSavedResults = hasQuery && !loading && dbResults.length === 0;
  const showSuggestions = suggestionsOpen && hasQuery && suggestions.length > 0;

  return (
    <section className="search-page">
      <form className="search-shell" onSubmit={onSearch}>
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
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
                <span>
                  <strong>{cleanName(person.name, person.company)}</strong>
                  <small>{cleanCompany(person.company, person.name)}</small>
                </span>
                {person.location && <small>{person.location}</small>}
              </button>
            ))}
          </div>
        )}
      </form>

      {!hasQuery && (
        <p className="tagline">
          Don't leave your most important career decision up to chance—get the insights you need with SumoImperium,
          and choose a leader who will transform your professional journey.
        </p>
      )}

      {message && <p className="notice">{message}</p>}
      {loading && <p className="notice">Searching...</p>}

      {showVerifyPrompt && !verifiedProfile && (
        <section className="verify-prompt">
          <div>
            <strong>Verify your leader profile</strong>
            <p>Add your profile photo and submit badge proof so people can recognize the official profile.</p>
          </div>
          <div className="verify-prompt-actions">
            <button className="btn primary" type="button" onClick={onVerify}>Verify Profile</button>
            <button className="text-btn" type="button" onClick={onDismissVerify}>Later</button>
          </div>
        </section>
      )}

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

      {noSavedResults && !linkedInResults.length && (
        <section className="empty-state">
          <p>We didn't find any leader by that name... yet.</p>
          <button className="btn primary" onClick={onManualLinkedIn}>Search LinkedIn</button>
          <button className="btn secondary" onClick={onAddLeader}>Add Leader</button>
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
            const company = cleanCompany(result.company || linkedInMeta.parsedCompany || '', result.name);
            const name = cleanName(result.name, company);
            return (
              <article className="linkedin-card" key={result.url}>
                <a href={result.url} target="_blank" rel="noreferrer">{name}</a>
                <p>{company}</p>
                <button className="btn primary small" onClick={() => onLinkedInReview(result)}>Review</button>
              </article>
            );
          })}
        </ResultSection>
      )}
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
      <span>
        <strong>{name}</strong>
        <small>{company} {profile.is_verified ? <span className="verified-inline">Verified</span> : null}</small>
      </span>
      <span className="row-rating">{reviewSummary(profile)}</span>
    </button>
  );
}

function ProfileView({ profile, onBack, onReview, signedIn, onLogin, message }) {
  const company = cleanCompany(profile.company, profile.name);
  const name = cleanName(profile.name, company);
  const average = profile.average_rating || 0;
  const linkedinUrl = linkedInUrlFromBio(profile.bio);

  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>← Back to Search</button>
      <article className="leader-card">
        <div className="cover" />
        <div className="avatar">
          {profile.avatar_url ? <img src={assetUrl(profile.avatar_url)} alt="" /> : name.slice(0, 1)}
        </div>
        <div className="leader-info">
          <h1>
            {name}
            {profile.is_verified && <span className="verified-badge" title="Verified leader profile">✓</span>}
          </h1>
          <p>{company}</p>
          <p>{profile.location}</p>
          <div className="rating-line">
            <Stars value={average} />
            <strong>{reviewSummary(profile)}</strong>
          </div>
          <div className="leader-actions">
            {linkedinUrl && <a href={linkedinUrl} target="_blank" rel="noreferrer">View Profile</a>}
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
  matches,
  selectedExistingId,
  onSelectExisting,
  onBack,
  onSubmit,
  signedIn,
  onLogin,
  message,
}) {
  const creatingNew = selectedExistingId === 'new';
  const submitLabel = creatingNew ? 'Save New Profile and Review' : 'Review Existing Profile';

  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>← Back to Search</button>
      <article className="confirm-card">
        <h1>Confirm Leader</h1>
        <strong>{draft.name}</strong>
        <p>{draft.company}</p>
        <p>{draft.location}</p>
        {draft.url && <a href={draft.url} target="_blank" rel="noreferrer">View LinkedIn profile</a>}
      </article>

      <section className="matches-card">
        <h2>Review Target</h2>
        <label className={`choice-row ${creatingNew ? 'selected' : ''}`}>
          <input
            type="radio"
            name="profile-choice"
            checked={creatingNew}
            onChange={() => onSelectExisting('new')}
          />
          <span>
            <strong>Create a new profile</strong>
            <small>{draft.name} · {draft.company}</small>
          </span>
        </label>

        {matches.length ? matches.map((match) => (
          <label className={`choice-row ${selectedExistingId === match.id ? 'selected' : ''}`} key={match.id}>
            <input
              type="radio"
              name="profile-choice"
              checked={selectedExistingId === match.id}
              onChange={() => onSelectExisting(match.id)}
            />
            <span>
              <strong>Use existing profile: {cleanName(match.name, match.company)}</strong>
              <small>{cleanCompany(match.company, match.name)} · {match.location}</small>
              <small>{reviewSummary(match)}</small>
            </span>
          </label>
        )) : <p className="muted">No saved profiles matched this person.</p>}
      </section>

      {message && <p className="notice">{message}</p>}
      <ReviewForm signedIn={signedIn} onLogin={onLogin} onSubmit={onSubmit} submitLabel={submitLabel} />
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
      setResults(people);
      if (!people.length) setLocalMessage('No saved profiles matched that search.');
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
                  <small>{cleanCompany(person.company, person.name)} · {person.location}</small>
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
