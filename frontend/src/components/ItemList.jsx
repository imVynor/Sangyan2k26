import React, { useState } from 'react';

export default function ItemList({
  items,
  loading,
  onToggle,
  onDelete,
  dbSource,
}) {
  const [filter, setFilter] = useState('all');

  const filteredItems = items.filter((item) => {
    if (filter === 'completed') return item.completed;
    if (filter === 'pending') return !item.completed;
    return true;
  });

  const completedCount = items.filter((i) => i.completed).length;

  return (
    <div className="items-card">
      <div className="items-header">
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            Live Items Feed{' '}
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 400 }}>
              ({items.length} total &bull; {completedCount} completed)
            </span>
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Data synchronized from{' '}
            <strong style={{ color: 'var(--text-primary)' }}>
              {dbSource || 'Backend Service'}
            </strong>
          </p>
        </div>

        <div className="items-filters">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({items.length})
          </button>
          <button
            className={`filter-btn ${filter === 'pending' ? 'active' : ''}`}
            onClick={() => setFilter('pending')}
          >
            Active ({items.length - completedCount})
          </button>
          <button
            className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
            onClick={() => setFilter('completed')}
          >
            Done ({completedCount})
          </button>
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⏳</div>
          <p>Connecting to backend API...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📂</div>
          <p>No records found in this view.</p>
          <p style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
            {filter !== 'all' ? 'Try changing the filter tab.' : 'Create your first item using the form on the left!'}
          </p>
        </div>
      ) : (
        <div className="item-list">
          {filteredItems.map((item) => (
            <div key={item._id} className="item-row">
              <div className="item-left">
                <input
                  type="checkbox"
                  className="item-checkbox"
                  checked={item.completed}
                  onChange={() => onToggle(item._id)}
                  title="Toggle status"
                />
                <div className="item-info">
                  <span className={`item-title ${item.completed ? 'completed' : ''}`}>
                    {item.title}
                  </span>
                  {item.description && (
                    <span className="item-desc">{item.description}</span>
                  )}
                  <div className="item-meta">
                    <span className="category-tag">{item.category || 'General'}</span>
                    <span className={`source-tag ${item.isMock ? 'source-mock' : 'source-mongo'}`}>
                      {item.isMock ? '⚡ Mock Store' : '🍃 MongoDB'}
                    </span>
                    {item.createdAt && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        &bull; {new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <button
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                  onClick={() => onDelete(item._id)}
                  title="Delete record"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
