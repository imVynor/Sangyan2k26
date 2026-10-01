import React from 'react';

export default function Navbar({ isConnected, isMock }) {
  return (
    <header className="navbar">
      <div className="container nav-content">
        <div className="brand">
          <div className="brand-icon">M</div>
          <div>
            <div className="brand-title">
              MERN<span className="text-gradient">Hub</span>
              <span className="brand-badge">Starter</span>
            </div>
          </div>
        </div>

        <div className="nav-badges">
          <span className="tech-pill">
            <span style={{ color: '#10b981' }}>🍃</span> Mongo
          </span>
          <span className="tech-pill">
            <span style={{ color: '#f59e0b' }}>⚡</span> Express
          </span>
          <span className="tech-pill">
            <span style={{ color: '#06b6d4' }}>⚛️</span> React
          </span>
          <span className="tech-pill">
            <span style={{ color: '#8b5cf6' }}>🟢</span> Node
          </span>
        </div>
      </div>
    </header>
  );
}
