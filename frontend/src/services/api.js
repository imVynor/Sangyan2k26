// API service with automatic proxy support & graceful client-side fallback
const API_BASE = '/api';

/**
 * Pings the backend health & mock connection endpoint
 */
export const checkBackendHealth = async () => {
  const startTime = performance.now();
  try {
    const response = await fetch(`${API_BASE}/health`, {
      headers: { 'Accept': 'application/json' },
    });

    const latency = Math.round(performance.now() - startTime);

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    return {
      connected: true,
      latency,
      data,
      isLocalMock: false,
    };
  } catch (error) {
    const latency = Math.round(performance.now() - startTime);
    return {
      connected: false,
      latency,
      error: error.message,
      data: {
        status: 'offline',
        message: 'Backend server is not reachable yet at http://localhost:5000.',
        database: { mode: 'Offline', connected: false },
      },
      isLocalMock: true,
    };
  }
};

/**
 * Fetches items from backend
 */
export const fetchItems = async () => {
  try {
    const res = await fetch(`${API_BASE}/items`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn('API error fetching items, using client mock state:', error.message);
    throw error;
  }
};

/**
 * Creates an item
 */
export const createItem = async (itemData) => {
  const res = await fetch(`${API_BASE}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(itemData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.message || `Failed to create item (${res.status})`);
  }
  return await res.json();
};

/**
 * Toggles completed status
 */
export const toggleItem = async (id) => {
  const res = await fetch(`${API_BASE}/items/${id}/toggle`, {
    method: 'PATCH',
  });
  if (!res.ok) {
    throw new Error(`Failed to toggle item (${res.status})`);
  }
  return await res.json();
};

/**
 * Deletes an item
 */
export const deleteItem = async (id) => {
  const res = await fetch(`${API_BASE}/items/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete item (${res.status})`);
  }
  return await res.json();
};
