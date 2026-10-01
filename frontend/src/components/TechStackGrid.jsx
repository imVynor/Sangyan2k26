import React from 'react';

export default function TechStackGrid() {
  const stack = [
    {
      name: 'MongoDB',
      role: 'Database Layer',
      icon: '🍃',
      accent: 'rgba(16, 185, 129, 0.2)',
      desc: 'NoSQL document database via Mongoose ODM. Automatically falls back to an in-memory mock store if disconnected.',
    },
    {
      name: 'Express.js',
      role: 'Server Framework',
      icon: '⚡',
      accent: 'rgba(245, 158, 11, 0.2)',
      desc: 'Lightweight REST API backend with modular routing, CORS, JSON parsers, and health diagnostics.',
    },
    {
      name: 'React 19 + Vite',
      role: 'Client Interface',
      icon: '⚛️',
      accent: 'rgba(6, 182, 212, 0.2)',
      desc: 'Ultra-fast HMR frontend with custom glassmorphic design system and real-time state synchronization.',
    },
    {
      name: 'Node.js',
      role: 'JavaScript Runtime',
      icon: '🟢',
      accent: 'rgba(139, 92, 246, 0.2)',
      desc: 'High-performance asynchronous runtime running the server and managing dependencies.',
    },
  ];

  return (
    <section className="tech-section">
      <h2 className="section-title">Architecture & Tech Stack</h2>
      <p className="section-subtitle">
        A decoupled full-stack architecture with production standards and seamless local mock connection
      </p>

      <div className="tech-grid">
        {stack.map((item) => (
          <div key={item.name} className="tech-card">
            <div
              className="tech-icon-wrap"
              style={{ background: item.accent }}
            >
              {item.icon}
            </div>
            <div className="tech-role">{item.role}</div>
            <h3 className="tech-name">{item.name}</h3>
            <p className="tech-desc">{item.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
