const API_ENDPOINT = '/api/links';
const PREVIEW_ENDPOINT = '/api/preview';
const DB_NAME = 'notekeep-offline';
const STORE_NAME = 'pending-links';

const statusEl = document.querySelector('#add-status');
const form = document.querySelector('#add-form');
const urlInput = document.querySelector('input[name="url"]');
const titleInput = document.querySelector('input[name="title"]');
const previewEl = document.querySelector('#link-preview');
let dbPromise;
let fetchTimeout;
let recommendedPicker;

function setStatus(message, type = 'muted') {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.classList.remove('hidden', 'text-green-700', 'text-red-600', 'text-amber-700', 'text-gray-600');
  if (type === 'success') {
    statusEl.classList.add('text-green-700');
  } else if (type === 'error') {
    statusEl.classList.add('text-red-600');
  } else if (type === 'offline') {
    statusEl.classList.add('text-amber-700');
  } else {
    statusEl.classList.add('text-gray-600');
  }
}

function clearStatus() {
  if (!statusEl) return;
  statusEl.textContent = '';
  statusEl.classList.add('hidden');
}

function openDatabase() {
  if (dbPromise) {
    return dbPromise;
  }
  if (!('indexedDB' in window)) {
    return Promise.reject(new Error('IndexedDB not supported'));
  }
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Failed to open offline store'));
  });
  return dbPromise;
}

async function storePending(entry) {
  try {
    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.onerror = () => reject(tx.error ?? new Error('Failed to queue link'));
      tx.oncomplete = () => resolve();
      tx.objectStore(STORE_NAME).add(entry);
    });
    setStatus('Saved offline. Will sync once you are back online.', 'offline');
  } catch (error) {
    console.error(error);
    setStatus('Offline and unable to queue locally.', 'error');
  }
}

async function readAllPending() {
  try {
    const db = await openDatabase();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const request = tx.objectStore(STORE_NAME).getAll();
      request.onsuccess = () => resolve(request.result ?? []);
      request.onerror = () => reject(request.error ?? new Error('Failed to read pending links'));
    });
  } catch (error) {
    console.error(error);
    return [];
  }
}

async function removePending(id) {
  try {
    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.onerror = () => reject(tx.error ?? new Error('Failed to remove queued link'));
      tx.oncomplete = () => resolve();
      tx.objectStore(STORE_NAME).delete(id);
    });
  } catch (error) {
    console.error(error);
  }
}

async function submitLink(data) {
  const response = await fetch(API_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    
    // Handle duplicate link (409 Conflict)
    if (response.status === 409) {
      const errorData = detail.detail || {};
      const existingTitle = errorData.existing_link_title || 'Untitled';
      const existingId = errorData.existing_link_id;
      throw new Error(`⚠️ Link already exists: "${existingTitle}" (ID: ${existingId})`);
    }
    
    throw new Error(detail.detail || 'Failed to save link');
  }

  return response.json();
}

async function handleSubmit(event) {
  event.preventDefault();
  const formData = new FormData(form);
  const link = {
    url: formData.get('url'),
    title: formData.get('title') || null,
    notes: null,
    tags: [],
    collection: null,
  };
  const selectedTagsRaw = formData.get('selected_tags');
  if (selectedTagsRaw) {
    link.tags = selectedTagsRaw
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 4);
  }
  if (!link.url) {
    setStatus('URL is required.', 'error');
    return;
  }

  try {
    await submitLink(link);
    window.location.href = '/links';
    return;
  } catch (error) {
    if (!navigator.onLine || (error instanceof TypeError && error.message.includes('fetch'))) {
      await storePending({ payload: link, createdAt: Date.now() });
      form.reset();
      if (recommendedPicker) {
        recommendedPicker.reset();
      }
      return;
    }
    console.error(error);
    setStatus(error.message || 'Unable to save link.', 'error');
  }
}

async function flushQueue() {
  const pending = await readAllPending();
  if (!pending.length) {
    return;
  }
  setStatus(`Syncing ${pending.length} saved item(s)…`, 'muted');
  for (const entry of pending) {
    try {
      await submitLink(entry.payload);
      await removePending(entry.id);
    } catch (error) {
      console.error('Failed to sync queued link', error);
      setStatus('Still offline. Will retry later.', 'error');
      return;
    }
  }
  setStatus('All queued links are synced.', 'success');
}

async function fetchPreview(url) {
  if (!url) {
    return;
  }
  try {
    showLoadingPreview();
    const response = await fetch(`${PREVIEW_ENDPOINT}?url=${encodeURIComponent(url)}`);
    if (!response.ok) {
      throw new Error('Failed to fetch preview');
    }
    const data = await response.json();
    if (data.title || data.image) {
      displayPreview(data);
      maybeUpdateTitle(data.title, url);
    } else {
      clearPreview();
    }
  } catch (error) {
    console.error('Preview fetch error:', error);
    clearPreview();
  }
}

function showLoadingPreview() {
  if (!previewEl) return;
  previewEl.innerHTML = '<div class="text-center py-4 text-sm text-gray-600">⏳ Fetching details...</div>';
  previewEl.classList.remove('hidden');
}

function displayPreview(data) {
  if (!previewEl) return;
  
  let html = '<div class="border border-gray-200 rounded overflow-hidden bg-white">';
  if (data.image) {
    html += `<img src="${data.image}" alt="Preview" class="w-full h-auto max-h-48 object-cover block" onerror="this.style.display='none'" />`;
  }
  html += '<div class="p-3">';
  if (data.title) {
    html += `<h4 class="font-semibold text-gray-900 mb-2">${data.title}</h4>`;
  }
  if (data.description) {
    html += `<p class="text-sm text-gray-600 line-clamp-2">${data.description}</p>`;
  }
  html += '</div></div>';
  
  previewEl.innerHTML = html;
  previewEl.classList.remove('hidden');
}

function clearPreview() {
  if (previewEl) {
    previewEl.innerHTML = '';
    previewEl.classList.add('hidden');
  }
}

function normalizeForComparison(value) {
  if (!value) return '';
  return value.trim().replace(/^https?:\/\//i, '').replace(/\/$/, '');
}

function maybeUpdateTitle(previewTitle, url) {
  if (!titleInput || !previewTitle) {
    return;
  }
  const current = titleInput.value.trim();
  if (!current) {
    titleInput.value = previewTitle;
    return;
  }

  const normalizedCurrent = normalizeForComparison(current);
  const normalizedUrl = normalizeForComparison(url);

  if (current === url || normalizedCurrent === normalizedUrl) {
    titleInput.value = previewTitle;
  }
}

function handleUrlChange() {
  clearTimeout(fetchTimeout);
  clearPreview();
  
  const url = urlInput.value.trim();
  
  if (url && url.startsWith('http')) {
    fetchTimeout = setTimeout(() => {
      fetchPreview(url);
    }, 800);
  }
}

function setupRecommendedTagPicker() {
  const container = document.querySelector('[data-recommended-tags]');
  const hiddenInput = document.querySelector('#selected-tags');
  if (!container || !hiddenInput) {
    return null;
  }

  const selected = new Set();
  const baseClasses = ['bg-white', 'text-gray-700', 'border-gray-200'];
  const activeClasses = ['bg-primary-600', 'text-white', 'border-primary-600', 'shadow'];

  function syncHiddenInput() {
    hiddenInput.value = Array.from(selected).join(',');
  }

  function setButtonState(button, isActive) {
    if (isActive) {
      button.classList.add(...activeClasses);
      button.classList.remove(...baseClasses);
      button.setAttribute('aria-pressed', 'true');
    } else {
      button.classList.remove(...activeClasses);
      button.classList.add(...baseClasses);
      button.setAttribute('aria-pressed', 'false');
    }
  }

  function toggleTag(button) {
    const value = button.dataset.tagValue;
    if (!value) {
      return;
    }
    if (selected.has(value)) {
      selected.delete(value);
      setButtonState(button, false);
      syncHiddenInput();
      clearStatus();
      return;
    }
    if (selected.size >= 4) {
      setStatus('You can choose up to 4 tags. Remove one to add another.', 'error');
      window.setTimeout(() => {
        clearStatus();
      }, 2500);
      return;
    }
    selected.add(value);
    setButtonState(button, true);
    syncHiddenInput();
  }

  container.querySelectorAll('button[data-tag-value]').forEach((button) => {
    setButtonState(button, false);
    button.addEventListener('click', () => toggleTag(button));
  });

  syncHiddenInput();

  return {
    reset() {
      selected.clear();
      container.querySelectorAll('button[data-tag-value]').forEach((button) => {
        setButtonState(button, false);
      });
      syncHiddenInput();
    },
  };
}

function bootstrap() {
  if (!form) {
    return;
  }
  form.addEventListener('submit', handleSubmit);
  recommendedPicker = setupRecommendedTagPicker();
  if (recommendedPicker) {
    form.addEventListener('reset', () => {
      recommendedPicker.reset();
    });
  }
  
  if (urlInput) {
    urlInput.addEventListener('input', handleUrlChange);
    urlInput.addEventListener('paste', handleUrlChange);
    // Auto-fetch if URL is pre-filled
    if (urlInput.value) {
      handleUrlChange();
    }
  }
  
  if (navigator.onLine) {
    flushQueue().catch((error) => console.error('Flush error', error));
  } else {
    setStatus('Offline. Links will sync later.', 'offline');
  }
  window.addEventListener('online', () => {
    setStatus('Back online. Syncing…', 'muted');
    flushQueue().catch((error) => console.error('Flush error', error));
  });

  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
}

document.addEventListener('DOMContentLoaded', bootstrap);
