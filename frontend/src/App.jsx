import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import ConnectionBanner from './components/ConnectionBanner';
import ItemForm from './components/ItemForm';
import ItemList from './components/ItemList';
import TechStackGrid from './components/TechStackGrid';
import {
  checkBackendHealth,
  fetchItems,
  createItem,
  toggleItem,
  deleteItem,
} from './services/api';

const DEFAULT_FALLBACK_ITEMS = [
  {
    _id: 'local-1',
    title: 'Initialize MERN Stack Workspace',
    description: 'Scaffolded frontend (Vite React) and backend (Express + Mongoose) with root gitignore.',
    category: 'Setup',
    completed: true,
    createdAt: new Date().toISOString(),
    isMock: true,
  },
  {
    _id: 'local-2',
    title: 'Test Live Mock Connection',
    description: 'Ping Express backend at /api/health to inspect live handshake & latency.',
    category: 'Testing',
    completed: false,
    createdAt: new Date().toISOString(),
    isMock: true,
  },
  {
    _id: 'local-3',
    title: 'Switch to Real MongoDB (Optional)',
    description: 'Add your MongoDB URI to backend/.env whenever ready — no code changes required!',
    category: 'Database',
    completed: false,
    createdAt: new Date().toISOString(),
    isMock: true,
  },
];

export default function App() {
  const [healthState, setHealthState] = useState({
    connected: false,
    latency: undefined,
    data: null,
  });
  const [items, setItems] = useState([]);
  const [dbSource, setDbSource] = useState('Initializing...');
  const [loading, setLoading] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message) => {
    setToast(message);
    setTimeout(() => setToast(null), 3500);
  };

  // Check health and load items
  const loadData = useCallback(async () => {
    setLoading(true);

    // 1. Health check
    const health = await checkBackendHealth();
    setHealthState(health);

    // 2. Load items
    if (health.connected) {
      try {
        const result = await fetchItems();
        if (result.success && Array.isArray(result.data)) {
          setItems(result.data);
          setDbSource(result.source || 'Backend Service');
        }
      } catch (err) {
        console.warn('Could not fetch backend items, using mock set:', err);
        setItems(DEFAULT_FALLBACK_ITEMS);
        setDbSource('Local Client Fallback');
      }
    } else {
      // Offline fallback
      setItems(DEFAULT_FALLBACK_ITEMS);
      setDbSource('Local Mock Store (Server Offline)');
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Ping backend button handler
  const handlePing = async () => {
    setPinging(true);
    const health = await checkBackendHealth();
    setHealthState(health);
    setPinging(false);
    if (health.connected) {
      showToast(`Ping successful! Server latency: ${health.latency}ms ⚡`);
      // Refresh items list
      try {
        const result = await fetchItems();
        if (result.success && Array.isArray(result.data)) {
          setItems(result.data);
          setDbSource(result.source || 'Backend Service');
        }
      } catch (e) {
        // ignore
      }
    } else {
      showToast('Could not reach backend at http://localhost:5000. Is the server running?');
    }
  };

  // Add Item
  const handleAddItem = async (itemData) => {
    setActionLoading(true);
    if (healthState.connected) {
      try {
        const res = await createItem(itemData);
        if (res.success && res.data) {
          setItems((prev) => [res.data, ...prev]);
          showToast(`Item added to ${res.source || 'storage'}! ✅`);
        }
      } catch (err) {
        showToast(`Error: ${err.message}`);
      }
    } else {
      // Local mock append
      const localItem = {
        _id: `local-${Date.now()}`,
        ...itemData,
        completed: false,
        createdAt: new Date().toISOString(),
        isMock: true,
      };
      setItems((prev) => [localItem, ...prev]);
      showToast('Item saved in local mock state! (Backend offline)');
    }
    setActionLoading(false);
  };

  // Toggle Item
  const handleToggle = async (id) => {
    // Optimistic UI update
    setItems((prev) =>
      prev.map((item) => (item._id === id ? { ...item, completed: !item.completed } : item))
    );

    if (healthState.connected) {
      try {
        await toggleItem(id);
      } catch (err) {
        console.warn('Failed to persist toggle to backend:', err);
      }
    }
  };

  // Delete Item
  const handleDelete = async (id) => {
    const originalItems = [...items];
    setItems((prev) => prev.filter((item) => item._id !== id));

    if (healthState.connected) {
      try {
        await deleteItem(id);
        showToast('Record deleted successfully 🗑️');
      } catch (err) {
        setItems(originalItems);
        showToast(`Failed to delete: ${err.message}`);
      }
    } else {
      showToast('Record removed from local mock state.');
    }
  };

  return (
    <>
      <Navbar
        isConnected={healthState.connected}
        isMock={!healthState.data?.database?.connected}
      />

      <main className="container" style={{ flex: 1 }}>
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-tag">
            <span>✨</span> Production-Ready Architecture &bull; Dual-Mode Ready
          </div>
          <h1 className="hero-title">
            MERN Stack <span className="text-gradient">Starter Suite</span>
          </h1>
          <p className="hero-subtitle">
            Complete full-stack template featuring MongoDB/Mongoose, Express REST API, React 19 + Vite,
            and an active mock connection fallback.
          </p>
        </section>

        {/* Mock Connection Hub Banner */}
        <ConnectionBanner
          healthState={healthState}
          onPing={handlePing}
          pinging={pinging}
        />

        {/* Dashboard Grid */}
        <div className="dashboard-grid">
          <ItemForm onAddItem={handleAddItem} loading={actionLoading} />
          <ItemList
            items={items}
            loading={loading}
            onToggle={handleToggle}
            onDelete={handleDelete}
            dbSource={dbSource}
          />
        </div>

        {/* Tech Stack Breakdown */}
        <TechStackGrid />
      </main>

      {/* Toast Notification */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(99, 102, 241, 0.4)',
            color: '#f8fafc',
            padding: '0.85rem 1.4rem',
            borderRadius: '12px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
            zIndex: 9999,
            fontSize: '0.9rem',
            fontWeight: 500,
            backdropFilter: 'blur(12px)',
          }}
        >
          {toast}
        </div>
      )}

      {/* Footer */}
      <footer className="footer">
        <div className="container">
          <p>
            MERN Starter Suite &bull; Built with Express, MongoDB, React, Vite & Node.js
          </p>
          <p style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Start both client & server with <code className="mono" style={{ color: '#a5b4fc' }}>npm run dev</code> in the project root.
          </p>
        </div>
      </footer>
    </>
  );
}
