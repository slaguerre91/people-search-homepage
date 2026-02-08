
// Main search, profile, review, and autocomplete logic (no auth)
const API = 'http://localhost:8000';

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
async function searchDatabase(q) {
  const section = document.getElementById('dbSection');
  const resultsEl = document.getElementById('dbResults');
  const countEl = document.getElementById('dbCount');
  try {
    const res = await fetch(`${API}/search?q=${encodeURIComponent(q)}`);
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
    resultsEl.innerHTML = people.map(p => `
      <div class="card" onclick="viewProfile('${p.id}')">
        <h3>${p.name}</h3>
        <p><strong>${p.company}</strong> • ${p.role}</p>
        <p style="font-size:12px; color:#64748b;">${p.location}</p>
      </div>
    `).join('');
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
    const res = await fetch(`${API}/search/linkedin?q=${encodeURIComponent(q)}`);
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
  const cards = profiles.map(p => {
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
        <h3><a href="${p.url}" target="_blank">${p.name}</a>${scoreBadge}</h3>
        <p>${p.title || 'LinkedIn Member'}</p>
        ${p.location ? `<p style="font-size:12px;">${p.location}</p>` : ''}
        ${p.snippet ? `<p style="font-size:12px; color:#64748b; margin-top:8px;">${p.snippet}</p>` : ''}
      </div>
    `;
  }).join('');
  el.innerHTML = parsedInfo + cards;
}

// View Profile
async function viewProfile(id) {
  const res = await fetch(`${API}/profiles/${id}`);
  if (!res.ok) { alert('Profile not found'); return; }
  const profile = await res.json();
  renderProfile(profile);
  document.getElementById('searchView').classList.add('hidden');
  document.getElementById('profileView').classList.remove('hidden');
}
window.viewProfile = viewProfile;

function renderProfile(p) {
  const reviews = p.reviews.length 
    ? p.reviews.map(r => `
        <div class="review">
          <strong>${r.author}</strong> — ${'⭐'.repeat(r.rating)}<br>
          <span>${r.comment}</span>
        </div>
      `).join('')
    : '<p>No reviews yet.</p>';
  document.getElementById('profileContent').innerHTML = `
    <h2>${p.name}</h2>
    <p style="font-size:18px; color:#60a5fa;">${p.company}</p>
    <p><strong>${p.role}</strong> • ${p.location}</p>
    <p>${p.bio || 'No bio provided.'}</p>
    <hr style="border-color:#334155; margin:16px 0;">
    <h3>Reviews</h3>
    ${reviews}
    <form class="review-form" id="reviewForm" onsubmit="event.preventDefault(); submitReview('${p.id}');">
      <h4>Add a Review</h4>
      <input id="reviewAuthor" placeholder="Your name">
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
  const author = document.getElementById('reviewAuthor').value.trim();
  const rating = parseInt(document.getElementById('reviewRating').value);
  const comment = document.getElementById('reviewComment').value.trim();
  if (!author || !comment) { alert('Please fill in all fields'); return; }
  const token = localStorage.getItem('authToken');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(`${API}/profiles/${profileId}/reviews`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ author, rating, comment })
  });
  if (res.ok) {
    viewProfile(profileId);
  } else if (res.status === 401) {
    alert('You must be signed in to submit a review.');
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
    const res = await fetch(`${API}/search/autocomplete?q=${encodeURIComponent(q)}`);
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
