import React, { useState } from 'react';

export default function ItemForm({ onAddItem, loading }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Frontend');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    onAddItem({
      title: title.trim(),
      description: description.trim(),
      category,
    });

    setTitle('');
    setDescription('');
  };

  return (
    <div className="form-card">
      <h3 className="form-card-title">Add New Record</h3>
      <p className="form-card-desc">
        Dispatches a <code className="mono">POST /api/items</code> payload across the connection
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="item-title">
            Title *
          </label>
          <input
            id="item-title"
            className="form-input"
            type="text"
            placeholder="e.g., Implement authentication"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="item-category">
            Category
          </label>
          <select
            id="item-category"
            className="form-select"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="Frontend">Frontend (React/Vite)</option>
            <option value="Backend">Backend (Express/Node)</option>
            <option value="Database">Database (MongoDB/Mock)</option>
            <option value="DevOps">DevOps & Tooling</option>
            <option value="General">General</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="item-desc">
            Description (Optional)
          </label>
          <textarea
            id="item-desc"
            className="form-textarea"
            rows="3"
            placeholder="Brief notes or acceptance criteria..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '0.5rem' }}
          disabled={loading || !title.trim()}
        >
          {loading ? 'Transmitting...' : '✨ Send to API'}
        </button>
      </form>
    </div>
  );
}
