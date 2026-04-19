const API_BASE = 'https://festival-discover.onrender.com';

const btn        = document.getElementById('discover-btn');
const festivalEl = document.getElementById('festival-input');
const artistEl   = document.getElementById('artist-input');
const validMsg   = document.getElementById('validation-msg');

const emptyState    = document.getElementById('empty-state');
const loadingState  = document.getElementById('loading-state');
const resultsContent = document.getElementById('results-content');
const noResults     = document.getElementById('no-results');
const errorState    = document.getElementById('error-state');

const seedLabel     = document.getElementById('seed-label');
const resultsSummary = document.getElementById('results-summary');
const resultsGrid   = document.getElementById('results-grid');

function showOnly(el) {
  [emptyState, loadingState, resultsContent, noResults, errorState].forEach(e => {
    e.classList.toggle('hidden', e !== el);
  });
}

function setLoading(on) {
  btn.disabled = on;
  btn.textContent = on ? 'Discovering…' : 'Discover artists';
}

function renderCard(artist) {
  const tags = (artist.tags || [])
    .map(t => `<span class="tag-pill">${escHtml(t)}</span>`)
    .join('');

  return `
    <div class="artist-card">
      <div class="card-top">
        <span class="artist-name">${escHtml(artist.name)}</span>
        <span class="match-badge">${artist.match}%</span>
      </div>
      <div class="match-bar-track">
        <div class="match-bar-fill" style="width: ${artist.match}%"></div>
      </div>
      ${tags ? `<div class="card-tags">${tags}</div>` : ''}
      <span class="listener-count">${escHtml(artist.listeners || '')}</span>
    </div>
  `.trim();
}

function toTitleCase(str) {
  return str.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function discover() {
  const festival   = toTitleCase(festivalEl.value.trim());
  const seedArtist = toTitleCase(artistEl.value.trim());

  if (!festival || !seedArtist) {
    validMsg.textContent = 'Please enter both a festival and an artist.';
    return;
  }
  validMsg.textContent = '';

  setLoading(true);
  showOnly(loadingState);

  try {
    const res = await fetch(`${API_BASE}/api/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ festival, seed_artist: seedArtist }),
    });

    const data = await res.json();

    if (!res.ok) {
      if (res.status === 404 && data.error && data.error.startsWith('No matches')) {
        showOnly(noResults);
      } else if (res.status === 404) {
        // Festival not found — show as no-results with festival-specific message
        noResults.querySelector('.no-results-title').textContent = 'Festival not found.';
        noResults.querySelector('.no-results-sub').textContent =
          'Check the festival name matches its Wikipedia article title (e.g. "Glastonbury Festival 2024").';
        showOnly(noResults);
      } else {
        showOnly(errorState);
      }
      return;
    }

    // Reset no-results text in case it was changed above
    noResults.querySelector('.no-results-title').textContent = 'No matches found.';
    noResults.querySelector('.no-results-sub').textContent =
      'Try a different artist or festival. More mainstream seed artists tend to produce better results.';

    if (!data.results || data.results.length === 0) {
      showOnly(noResults);
      return;
    }

    seedLabel.textContent = `Based on: ${data.seed_artist}`;
    resultsSummary.textContent =
      `${data.results.length} artist${data.results.length !== 1 ? 's' : ''} found at ${data.festival}`;
    resultsGrid.innerHTML = data.results.map(renderCard).join('');
    showOnly(resultsContent);

  } catch (err) {
    console.error('discover error:', err);
    showOnly(errorState);
  } finally {
    setLoading(false);
  }
}

// Allow Enter key to trigger search from either input
[festivalEl, artistEl].forEach(input => {
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') discover();
  });
});

// Initialise: only empty state visible on load
showOnly(emptyState);
