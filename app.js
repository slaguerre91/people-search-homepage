
// Main search, profile, review, and autocomplete logic (no auth)
const API_BASE = window.API || 'http://localhost:8000';
let linkedinReviewDrafts = [];
let linkedinExistingMatches = [];

function updateAuthControls() {
  const signedIn = Boolean(localStorage.getItem('authToken'));
  document.getElementById('signupLink')?.classList.toggle('hidden', signedIn);
  document.getElementById('signinLink')?.classList.toggle('hidden', signedIn);
  document.getElementById('signoutBtn')?.classList.toggle('hidden', !signedIn);
}

function signOut() {
  localStorage.removeItem('authToken');
  updateAuthControls();
  showSearch();
}
window.signOut = signOut;
updateAuthControls();

// Main unified search
async function doSearch() {
  const q = document.getElementById('searchInput').value.trim();
  const btn = document.getElementById('searchBtn');
  // Clear previous results
  document.getElementById('dbSection').classList.add('hidden');
  document.getElementById('linkedinSection').classList.add('hidden');
  if (!q) {
    // Show all DB profiles if no query
    await searchDatabase('');
    return;
  }
  // Disable button during search
  btn.disabled = true;
  btn.textContent = 'Searching...';
  const linkedinSection = document.getElementById('linkedinSection');
  const linkedinResults = document.getElementById('linkedinResults');
  const linkedinCount = document.getElementById('linkedinCount');
  linkedinSection.classList.add('hidden');
  linkedinCount.textContent = '0';
  linkedinResults.innerHTML = '';
  // Search DB first, then decide on LinkedIn
  const found = await searchDatabase(q);
  if (!found) {
    // If no DB results, auto-trigger LinkedIn search
    linkedinSection.classList.remove('hidden');
    linkedinCount.textContent = '...';
    linkedinResults.innerHTML = '<div class="loading">🔍 Searching LinkedIn...</div>';
    await searchLinkedIn(q);
  } else {
    // If DB results found, show LinkedIn prompt and manual button
    linkedinSection.classList.remove('hidden');
    linkedinCount.textContent = '0';
    linkedinResults.innerHTML = `
      <div class="empty-state">
        <div class="icon">🔗</div>
        <p>Didn't find the person you are looking for?</p>
        <button id="linkedinManualBtn" style="margin-top:12px; padding:10px 18px; background:#0077b5; color:white; border:none; border-radius:6px; font-size:15px; cursor:pointer;" onclick="manualLinkedInSearch()">Search on LinkedIn</button>
      </div>
    `;
  }
  btn.disabled = false;
  btn.textContent = 'Search';
}

// Database search
function formatReviewSummary(profile) {
  const count = profile.review_count || 0;
  if (!count || profile.average_rating === null || profile.average_rating === undefined) {
    return 'No reviews yet';
  }
  const label = count === 1 ? 'review' : 'reviews';
  return `⭐ ${Number(profile.average_rating).toFixed(1)} (${count} ${label})`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatProfileBio(bio) {
  if (!bio) return 'No bio provided.';
  const linkedinMatch = bio.match(/https?:\/\/(?:www\.)?linkedin\.com\/in\/[^\s]+/i);
  if (linkedinMatch) {
    const url = linkedinMatch[0];
    return `<a href="${escapeHtml(url)}" target="_blank" style="color:#60a5fa;">LinkedIn profile</a>`;
  }
  return escapeHtml(bio);
}

function cleanLinkedInText(value) {
  return String(value || '')
    .replace(/\s*\|\s*LinkedIn.*$/i, '')
    .replace(/\s+LinkedIn\s*$/i, '')
    .replace(/\s*\.\.\..*$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function cleanCompany(company, name = '') {
  let value = cleanLinkedInText(company);
  if (name && value.toLowerCase().includes(name.toLowerCase())) {
    value = value.slice(0, value.toLowerCase().indexOf(name.toLowerCase())).trim();
  }
  if (value.includes(' - ')) {
    value = value.split(' - ')[0].trim();
  }
  return value || 'Unknown';
}

function cleanLinkedInName(name, company = '') {
  let value = cleanLinkedInText(name);
  if (value.includes(' - ')) {
    value = value.split(' - ')[0].trim();
  }
  if (company && value.toLowerCase().startsWith(company.toLowerCase())) {
    value = value.slice(company.length).trim();
  }
  return value || 'LinkedIn Member';
}

function cleanRole(role, name = '') {
  let value = cleanLinkedInText(role);
  if (value.includes(' - ')) {
    const [beforeDash, afterDash] = value.split(' - ', 2);
    const looksLikeRole = /\b(chief|officer|director|manager|engineer|lead|head|president|founder|staff|policy|people|operations)\b/i.test(afterDash);
    if (!name || beforeDash.toLowerCase().includes(name.toLowerCase()) || looksLikeRole) {
      value = afterDash.trim();
    }
  }
  if (name && value.toLowerCase().startsWith(name.toLowerCase())) {
    value = value.slice(name.length).replace(/^[-,\s]+/, '').trim();
  }
  return value || 'LinkedIn Member';
}

async function searchDatabase(q) {
  const section = document.getElementById('dbSection');
  const resultsEl = document.getElementById('dbResults');
  const countEl = document.getElementById('dbCount');
  try {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
    const people = await res.json();
    section.classList.remove('hidden');
    countEl.textContent = people.length;
    if (!people.length) {
      resultsEl.innerHTML = `
        <div class="empty-state">
          <div class="icon">📭</div>
          <p>No saved profiles found${q ? ` for "${q}"` : ''}</p>
        </div>
      `;
      return false;
    }
    resultsEl.innerHTML = people.map(p => {
      const company = cleanCompany(p.company, p.name);
      const displayName = cleanLinkedInName(p.name, company);
      return `
        <div class="card" onclick="viewProfile('${p.id}')">
          <h3>${escapeHtml(displayName)}</h3>
          <p><strong>${escapeHtml(company)}</strong> • ${escapeHtml(cleanRole(p.role, displayName))}</p>
          <p style="font-size:12px; color:#64748b;">${escapeHtml(p.location)}</p>
          <p style="font-size:12px; color:#fbbf24; margin-top:6px;">${formatReviewSummary(p)}</p>
        </div>
      `;
    }).join('');
    return true;
  } catch (err) {
    section.classList.remove('hidden');
    resultsEl.innerHTML = `<p style="color:#ef4444;">Error loading profiles</p>`;
    return false;
  }
}

// Manual LinkedIn search trigger (must be global for button onclick)
function manualLinkedInSearch() {
  const q = document.getElementById('searchInput').value.trim();
  const linkedinSection = document.getElementById('linkedinSection');
  const linkedinResults = document.getElementById('linkedinResults');
  const linkedinCount = document.getElementById('linkedinCount');
  linkedinSection.classList.remove('hidden');
  linkedinCount.textContent = '...';
  linkedinResults.innerHTML = '<div class="loading">🔍 Searching LinkedIn...</div>';
  searchLinkedIn(q);
}
window.manualLinkedInSearch = manualLinkedInSearch;

// LinkedIn search
async function searchLinkedIn(q) {
  const section = document.getElementById('linkedinSection');
  const resultsEl = document.getElementById('linkedinResults');
  const countEl = document.getElementById('linkedinCount');
  try {
    const res = await fetch(`${API_BASE}/search/linkedin?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error('Search failed');
    const data = await res.json();
    countEl.textContent = data.profiles.length;
    renderLinkedInResults(data.profiles, data.parsed_name, data.parsed_company);
  } catch (err) {
    countEl.textContent = '0';
    resultsEl.innerHTML = `
      <div class="empty-state">
        <div class="icon">⚠️</div>
        <p>Could not search LinkedIn</p>
      </div>
    `;
  }
}

function renderLinkedInResults(profiles, parsedName, parsedCompany) {
  const el = document.getElementById('linkedinResults');
  if (!profiles.length) {
    el.innerHTML = `
      <div class="empty-state">
        <div class="icon">🔍</div>
        <p>No LinkedIn profiles found</p>
      </div>
    `;
    return;
  }
  // Show what was parsed from the query
  let parsedInfo = '';
  if (parsedName || parsedCompany) {
    const parts = [];
    if (parsedName) parts.push(`<strong>Name:</strong> ${parsedName}`);
    if (parsedCompany) parts.push(`<strong>Company:</strong> ${parsedCompany}`);
    parsedInfo = `<div class="parsed-info">🎯 Searching for: ${parts.join(' • ')}</div>`;
  }
  linkedinReviewDrafts = profiles.map(p => buildLinkedInReviewDraft(p, parsedCompany));
  const cards = profiles.map((p, index) => {
    const draft = linkedinReviewDrafts[index];
    let badgeClass = 'match-low';
    let badgeText = 'Low';
    if (p.match_score >= 70) {
      badgeClass = 'match-high';
      badgeText = 'Strong';
    } else if (p.match_score >= 50) {
      badgeClass = 'match-medium';
      badgeText = 'Partial';
    }
    const scoreBadge = p.match_score > 0 
      ? `<span class="match-badge ${badgeClass}">${badgeText} ${p.match_score}%</span>` 
      : '';
    return `
      <div class="linkedin-card">
        <h3><a href="${escapeHtml(p.url)}" target="_blank">${escapeHtml(draft.name)}</a>${scoreBadge}</h3>
        <p>${escapeHtml(draft.company)}</p>
        <button type="button" style="margin-top:12px; padding:8px 12px; background:#3b82f6; color:white; border:none; border-radius:6px; font-size:14px; cursor:pointer;" onclick="startLinkedInReview(${index})">Review</button>
      </div>
    `;
  }).join('');
  el.innerHTML = parsedInfo + cards;
}

function extractCompanyFromTitle(title) {
  const cleanedTitle = cleanLinkedInText(title);
  if (!cleanedTitle) return '';
  const atMatch = cleanedTitle.match(/\b(?:at|@)\s+([^|,]+)/i);
  if (atMatch) return atMatch[1].trim().slice(0, 100);
  return '';
}

function buildLinkedInReviewDraft(profile, parsedCompany) {
  const company = cleanCompany(profile.company || parsedCompany || extractCompanyFromTitle(profile.title) || '', profile.name).slice(0, 100);
  const name = cleanLinkedInName(profile.name, company).slice(0, 100);
  const role = cleanRole(profile.title || 'LinkedIn Member', name).slice(0, 100);
  const location = (profile.location || 'Unknown').slice(0, 100);
  return {
    name,
    company,
    role,
    location,
    bio: profile.url ? `LinkedIn profile: ${profile.url}`.slice(0, 500) : '',
    sourceTitle: role,
    sourceLocation: profile.location || '',
    sourceUrl: profile.url || ''
  };
}

function startLinkedInReview(index) {
  const draft = linkedinReviewDrafts[index];
  if (!draft) return;
  renderLinkedInReviewDraft(draft);
  loadExistingProfileMatches(draft);
  document.getElementById('searchView').classList.add('hidden');
  document.getElementById('profileView').classList.remove('hidden');
}
window.startLinkedInReview = startLinkedInReview;

function renderLinkedInReviewDraft(draft) {
  document.getElementById('profileContent').innerHTML = `
    <h2>Confirm Leader</h2>
    <div class="review" style="margin-bottom:14px;">
      <strong>${escapeHtml(draft.name)}</strong>
      <p>${escapeHtml(draft.company)}</p>
      ${draft.sourceLocation ? `<p style="font-size:12px; color:#94a3b8;">${escapeHtml(draft.sourceLocation)}</p>` : ''}
      ${draft.sourceUrl ? `<p style="font-size:12px; margin-top:8px;"><a href="${escapeHtml(draft.sourceUrl)}" target="_blank" style="color:#60a5fa;">View LinkedIn profile</a></p>` : ''}
    </div>
    <div id="existingProfileMatches" style="margin-bottom:16px;"></div>
    <form class="review-form" id="linkedinReviewForm" onsubmit="event.preventDefault(); submitLinkedInReview();">
      <input id="linkedinExistingProfileId" type="hidden" value="">
      <div id="selectedExistingProfile" class="hidden" style="background:#0f172a; padding:12px; border-radius:6px;"></div>
      <input id="linkedinProfileName" type="hidden" value="${escapeHtml(draft.name)}">
      <input id="linkedinProfileCompany" type="hidden" value="${escapeHtml(draft.company)}">
      <input id="linkedinProfileRole" type="hidden" value="${escapeHtml(draft.role)}">
      <input id="linkedinProfileLocation" type="hidden" value="${escapeHtml(draft.location)}">
      <input id="linkedinProfileBio" type="hidden" value="${escapeHtml(draft.bio)}">
      <h3>Review</h3>
      <select id="linkedinReviewRating" style="padding:10px; background:#0f172a; color:#e2e8f0; border:none; border-radius:6px;">
        <option value="5">⭐⭐⭐⭐⭐ (5)</option>
        <option value="4">⭐⭐⭐⭐ (4)</option>
        <option value="3">⭐⭐⭐ (3)</option>
        <option value="2">⭐⭐ (2)</option>
        <option value="1">⭐ (1)</option>
      </select>
      <textarea id="linkedinReviewComment" placeholder="Write your review..."></textarea>
      <button type="submit">Save Profile and Review</button>
    </form>
  `;
}

async function loadExistingProfileMatches(draft) {
  const container = document.getElementById('existingProfileMatches');
  if (!container) return;
  container.innerHTML = '<p style="font-size:13px; color:#94a3b8;">Checking saved profiles...</p>';
  try {
    const q = draft.name.trim();
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error('Profile match search failed');
    linkedinExistingMatches = (await res.json()).slice(0, 5);
    if (!linkedinExistingMatches.length) {
      container.innerHTML = '';
      return;
    }
    container.innerHTML = `
      <h3>Possible Saved Profiles</h3>
      ${linkedinExistingMatches.map((profile, index) => `
        <div class="review" style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
          <div>
            <strong>${escapeHtml(profile.name)}</strong>
            <p>${escapeHtml(cleanCompany(profile.company, profile.name))} • ${escapeHtml(cleanRole(profile.role, profile.name))}</p>
            <p style="font-size:12px; color:#94a3b8;">${escapeHtml(profile.location)} • ${escapeHtml(formatReviewSummary(profile))}</p>
          </div>
          <button type="button" style="padding:8px 12px; background:#475569; color:white; border:none; border-radius:6px; cursor:pointer;" onclick="selectExistingLinkedInProfile(${index})">Use</button>
        </div>
      `).join('')}
    `;
  } catch {
    container.innerHTML = '';
  }
}

function selectExistingLinkedInProfile(index) {
  const profile = linkedinExistingMatches[index];
  if (!profile) return;
  document.getElementById('linkedinExistingProfileId').value = profile.id;
  document.getElementById('linkedinProfileName').disabled = true;
  document.getElementById('linkedinProfileCompany').disabled = true;
  document.getElementById('linkedinProfileRole').disabled = true;
  document.getElementById('linkedinProfileLocation').disabled = true;
  document.getElementById('linkedinProfileBio').disabled = true;
  const selected = document.getElementById('selectedExistingProfile');
  selected.classList.remove('hidden');
  selected.innerHTML = `
    <strong>Using saved profile:</strong> ${escapeHtml(profile.name)} at ${escapeHtml(cleanCompany(profile.company, profile.name))}
    <button type="button" style="margin-left:8px; padding:6px 10px; background:#475569; color:white; border:none; border-radius:6px; cursor:pointer;" onclick="clearExistingLinkedInProfile()">Create New Instead</button>
  `;
}
window.selectExistingLinkedInProfile = selectExistingLinkedInProfile;

function clearExistingLinkedInProfile() {
  document.getElementById('linkedinExistingProfileId').value = '';
  document.getElementById('linkedinProfileName').disabled = false;
  document.getElementById('linkedinProfileCompany').disabled = false;
  document.getElementById('linkedinProfileRole').disabled = false;
  document.getElementById('linkedinProfileLocation').disabled = false;
  document.getElementById('linkedinProfileBio').disabled = false;
  const selected = document.getElementById('selectedExistingProfile');
  selected.classList.add('hidden');
  selected.innerHTML = '';
}
window.clearExistingLinkedInProfile = clearExistingLinkedInProfile;

async function submitLinkedInReview() {
  const token = localStorage.getItem('authToken');
  if (!token) {
    alert('You must be signed in to submit a review.');
    updateAuthControls();
    return;
  }
  const comment = document.getElementById('linkedinReviewComment').value.trim();
  if (!comment) { alert('Please write a review'); return; }
  const payload = {
    profile: {
      name: document.getElementById('linkedinProfileName').value.trim(),
      company: document.getElementById('linkedinProfileCompany').value.trim(),
      role: document.getElementById('linkedinProfileRole').value.trim(),
      location: document.getElementById('linkedinProfileLocation').value.trim(),
      bio: document.getElementById('linkedinProfileBio').value.trim()
    },
    review: {
      rating: parseInt(document.getElementById('linkedinReviewRating').value),
      comment
    }
  };
  const existingProfileId = document.getElementById('linkedinExistingProfileId').value;
  if (existingProfileId) {
    payload.existing_profile_id = existingProfileId;
  }
  if (!payload.profile.name || !payload.profile.company || !payload.profile.role || !payload.profile.location) {
    alert('Please fill in the profile details');
    return;
  }
  const res = await fetch(`${API_BASE}/linkedin/reviews`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token
    },
    body: JSON.stringify(payload)
  });
  if (res.ok) {
    const profile = await res.json();
    renderProfile(profile);
  } else if (res.status === 401) {
    alert('You must be signed in to submit a review.');
    updateAuthControls();
  } else if (res.status === 409) {
    alert('You have already reviewed this profile.');
  } else {
    alert('Failed to save review');
  }
}
window.submitLinkedInReview = submitLinkedInReview;

// View Profile
async function viewProfile(id) {
  const res = await fetch(`${API_BASE}/profiles/${id}`);
  if (!res.ok) { alert('Profile not found'); return; }
  const profile = await res.json();
  renderProfile(profile);
  document.getElementById('searchView').classList.add('hidden');
  document.getElementById('profileView').classList.remove('hidden');
}
window.viewProfile = viewProfile;

function renderProfile(p) {
  const reviewSummary = formatReviewSummary(p);
  const company = cleanCompany(p.company, p.name);
  const displayName = cleanLinkedInName(p.name, company);
  const reviews = p.reviews.length 
    ? p.reviews.map(r => `
        <div class="review">
          <strong>${r.author}</strong> — ${'⭐'.repeat(r.rating)}<br>
          <span>${r.comment}</span>
        </div>
      `).join('')
    : '<p>No reviews yet.</p>';
  document.getElementById('profileContent').innerHTML = `
    <h2>${escapeHtml(displayName)}</h2>
    <p style="font-size:18px; color:#60a5fa;">${escapeHtml(company)}</p>
    <p>${escapeHtml(p.location)}</p>
    <p style="color:#fbbf24;">${reviewSummary}</p>
    <p>${formatProfileBio(p.bio)}</p>
    <hr style="border-color:#334155; margin:16px 0;">
    <h3>Reviews</h3>
    ${reviews}
    <form class="review-form" id="reviewForm" onsubmit="event.preventDefault(); submitReview('${p.id}');">
      <h4>Add a Review</h4>
      <select id="reviewRating" style="padding:10px; background:#0f172a; color:#e2e8f0; border:none; border-radius:6px;">
        <option value="5">⭐⭐⭐⭐⭐ (5)</option>
        <option value="4">⭐⭐⭐⭐ (4)</option>
        <option value="3">⭐⭐⭐ (3)</option>
        <option value="2">⭐⭐ (2)</option>
        <option value="1">⭐ (1)</option>
      </select>
      <textarea id="reviewComment" placeholder="Write your review..."></textarea>
      <button type="submit">Submit Review</button>
    </form>
  `;
}

// Submit Review
async function submitReview(profileId) {
  const rating = parseInt(document.getElementById('reviewRating').value);
  const comment = document.getElementById('reviewComment').value.trim();
  if (!comment) { alert('Please write a review'); return; }
  const token = localStorage.getItem('authToken');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(`${API_BASE}/profiles/${profileId}/reviews`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ rating, comment })
  });
  if (res.ok) {
    viewProfile(profileId);
  } else if (res.status === 401) {
    alert('You must be signed in to submit a review.');
    updateAuthControls();
  } else if (res.status === 409) {
    alert('You have already reviewed this profile.');
  } else {
    alert('Failed to submit review');
  }
}
window.submitReview = submitReview;

function showSearch() {
  document.getElementById('searchView').classList.remove('hidden');
  document.getElementById('profileView').classList.add('hidden');
}
window.showSearch = showSearch;

// --- Autocomplete logic ---
const searchInput = document.getElementById('searchInput');
let autocompleteBox = null;
let autocompleteResults = [];
searchInput.addEventListener('input', async function(e) {
  const q = searchInput.value.trim();
  if (!q) {
    removeAutocomplete();
    return;
  }
  // Fetch autocomplete suggestions
  try {
    const res = await fetch(`${API_BASE}/search/autocomplete?q=${encodeURIComponent(q)}`);
    const suggestions = await res.json();
    autocompleteResults = suggestions;
    showAutocomplete(suggestions);
  } catch {
    removeAutocomplete();
  }
});
searchInput.addEventListener('blur', () => {
  setTimeout(removeAutocomplete, 150); // Delay to allow click
});
function showAutocomplete(suggestions) {
  removeAutocomplete();
  if (!suggestions.length) return;
  autocompleteBox = document.createElement('div');
  autocompleteBox.className = 'autocomplete-box';
  autocompleteBox.style.position = 'absolute';
  autocompleteBox.style.background = '#1e293b';
  autocompleteBox.style.color = '#e2e8f0';
  autocompleteBox.style.border = '1px solid #334155';
  autocompleteBox.style.borderRadius = '6px';
  autocompleteBox.style.zIndex = 1000;
  autocompleteBox.style.width = searchInput.offsetWidth + 'px';
  autocompleteBox.style.left = searchInput.getBoundingClientRect().left + window.scrollX + 'px';
  autocompleteBox.style.top = (searchInput.getBoundingClientRect().bottom + window.scrollY) + 'px';
  autocompleteBox.innerHTML = suggestions.map((s, i) => `
    <div class="autocomplete-item" style="padding:10px; cursor:pointer; border-bottom:1px solid #334155;" data-idx="${i}">
      <strong>${s.name}</strong> <span style="color:#60a5fa;">${s.role}</span><br>
      <span style="font-size:13px; color:#94a3b8;">${s.company} • ${s.location}</span>
    </div>
  `).join('');
  document.body.appendChild(autocompleteBox);
  // Click handler
  autocompleteBox.querySelectorAll('.autocomplete-item').forEach(item => {
    item.addEventListener('mousedown', function(e) {
      const idx = +item.getAttribute('data-idx');
      if (autocompleteResults[idx] && autocompleteResults[idx].id) {
        removeAutocomplete();
        viewProfile(autocompleteResults[idx].id);
      }
    });
  });
}
function removeAutocomplete() {
  if (autocompleteBox) {
    autocompleteBox.remove();
    autocompleteBox = null;
  }
}
