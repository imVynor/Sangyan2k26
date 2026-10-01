import React, { useState } from 'react';

export default function ConnectionBanner({ healthState, onPing, pinging }) {
  const [showJson, setShowJson] = useState(false);

  const isOnline = healthState.connected;
  const isMock = !healthState.data?.database?.connected;
  const dbMode = healthState.data?.database?.mode || (isOnline ? 'Active' : 'Offline');

  return (
    <div className="connection-card">
      <div className="connection-header">
        <div className="connection-title-wrap">
          <span style={{ fontSize: '1.5rem' }}>🔗</span>
          <div>
            <h2 className="connection-title">Frontend ↔ Backend Mock Connection</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Real-time handshake monitor with automatic fallback handling
            </p>
          </div>
        </div>

        <div>
          {isOnline ? (
            <div className={`status-indicator ${isMock ? 'status-mock' : 'status-online'}`}>
              <span className={`pulse-dot ${isMock ? 'mock' : 'online'}`}></span>
              <span>{isMock ? 'Connected (Mock Mode)' : 'Connected (MongoDB Live)'}</span>
            </div>
          ) : (
            <div className="status-indicator status-offline">
              <span className="pulse-dot offline"></span>
              <span>Backend Offline</span>
            </div>
          )}
        </div>
      </div>

      <div className="connection-metrics">
        <div className="metric-box">
          <div className="metric-label">Server Status</div>
          <div className="metric-value">
            {isOnline ? '🟢 Online' : '🔴 Unreachable'}
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-label">Latency (Roundtrip)</div>
          <div className="metric-value mono">
            {healthState.latency !== undefined ? `${healthState.latency} ms` : '--'}
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-label">Database Storage Mode</div>
          <div className="metric-value" style={{ fontSize: '0.95rem' }}>
            {dbMode}
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-label">API Health Route</div>
          <div className="metric-value mono" style={{ fontSize: '0.9rem', color: 'var(--accent-cyan)' }}>
            GET /api/health
          </div>
        </div>
      </div>

      <div className="connection-actions">
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          {isOnline ? (
            <span>
              ✅ Express backend is responding at <strong style={{ color: 'var(--text-primary)' }}>http://localhost:5000</strong>.
              {isMock && ' Running in In-Memory Mock Store (no local MongoDB needed).'}
            </span>
          ) : (
            <span>
              ⚠️ Start the backend with <code className="mono" style={{ color: '#fbbf24' }}>npm run dev:server</code> to connect.
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            className="btn btn-secondary"
            onClick={() => setShowJson(!showJson)}
          >
            {showJson ? 'Hide Raw JSON' : 'Inspect Raw Handshake'}
          </button>

          <button
            className="btn btn-primary"
            onClick={onPing}
            disabled={pinging}
          >
            {pinging ? 'Pinging...' : '⚡ Test Connection'}
          </button>
        </div>
      </div>

      {showJson && (
        <pre className="json-viewer">
          {JSON.stringify(
            {
              mockConnectionActive: true,
              timestamp: new Date().toISOString(),
              healthData: healthState.data,
              latencyMs: healthState.latency,
            },
            null,
            2
          )}
        </pre>
      )}
    </div>
  );
}
