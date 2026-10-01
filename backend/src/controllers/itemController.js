import Item from '../models/Item.js';
import { getDBStatus } from '../config/db.js';

// Pre-seeded mock data when running without MongoDB
let mockItems = [
  {
    _id: 'mock-1',
    title: 'Explore MERN Project Structure',
    description: 'Frontend (Vite + React) & Backend (Express) connected successfully!',
    category: 'Setup',
    completed: true,
    createdAt: new Date(Date.now() - 3600000).toISOString(),
    isMock: true,
  },
  {
    _id: 'mock-2',
    title: 'Test Mock Connection API',
    description: 'Try adding or deleting an item from the frontend interface.',
    category: 'Testing',
    completed: false,
    createdAt: new Date(Date.now() - 1800000).toISOString(),
    isMock: true,
  },
  {
    _id: 'mock-3',
    title: 'Connect Real MongoDB (Optional)',
    description: 'Provide your MONGO_URI in backend/.env to automatically switch from mock to live DB.',
    category: 'Database',
    completed: false,
    createdAt: new Date().toISOString(),
    isMock: true,
  },
];

// @desc    Get all items
// @route   GET /api/items
export const getItems = async (req, res) => {
  try {
    const { isConnected } = getDBStatus();

    if (isConnected) {
      const items = await Item.find().sort({ createdAt: -1 });
      return res.status(200).json({
        success: true,
        source: 'MongoDB',
        count: items.length,
        data: items,
      });
    }

    // Return in-memory mock items
    return res.status(200).json({
      success: true,
      source: 'Mock In-Memory Store',
      count: mockItems.length,
      data: mockItems,
    });
  } catch (error) {
    return res.status(500).json({
      success: false,
      message: 'Failed to retrieve items',
      error: error.message,
    });
  }
};

// @desc    Create a new item
// @route   POST /api/items
export const createItem = async (req, res) => {
  try {
    const { title, description, category } = req.body;

    if (!title || title.trim() === '') {
      return res.status(400).json({
        success: false,
        message: 'Title is required',
      });
    }

    const { isConnected } = getDBStatus();

    if (isConnected) {
      const newItem = await Item.create({
        title: title.trim(),
        description: description?.trim() || '',
        category: category || 'General',
        completed: false,
      });

      return res.status(201).json({
        success: true,
        source: 'MongoDB',
        data: newItem,
      });
    }

    // Fallback Mock create
    const newItem = {
      _id: `mock-${Date.now()}`,
      title: title.trim(),
      description: description?.trim() || '',
      category: category || 'General',
      completed: false,
      createdAt: new Date().toISOString(),
      isMock: true,
    };

    mockItems.unshift(newItem);

    return res.status(201).json({
      success: true,
      source: 'Mock In-Memory Store',
      data: newItem,
    });
  } catch (error) {
    return res.status(500).json({
      success: false,
      message: 'Failed to create item',
      error: error.message,
    });
  }
};

// @desc    Toggle item completed status
// @route   PATCH /api/items/:id/toggle
export const toggleItem = async (req, res) => {
  try {
    const { id } = req.params;
    const { isConnected } = getDBStatus();

    if (isConnected) {
      const item = await Item.findById(id);
      if (!item) {
        return res.status(404).json({ success: false, message: 'Item not found' });
      }
      item.completed = !item.completed;
      await item.save();
      return res.status(200).json({ success: true, source: 'MongoDB', data: item });
    }

    const item = mockItems.find((i) => i._id === id);
    if (!item) {
      return res.status(404).json({ success: false, message: 'Item not found' });
    }
    item.completed = !item.completed;
    return res.status(200).json({ success: true, source: 'Mock In-Memory Store', data: item });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
};

// @desc    Delete an item
// @route   DELETE /api/items/:id
export const deleteItem = async (req, res) => {
  try {
    const { id } = req.params;
    const { isConnected } = getDBStatus();

    if (isConnected) {
      const deleted = await Item.findByIdAndDelete(id);
      if (!deleted) {
        return res.status(404).json({ success: false, message: 'Item not found' });
      }
      return res.status(200).json({
        success: true,
        source: 'MongoDB',
        message: 'Item deleted successfully',
        id,
      });
    }

    const index = mockItems.findIndex((i) => i._id === id);
    if (index === -1) {
      return res.status(404).json({ success: false, message: 'Item not found' });
    }

    mockItems.splice(index, 1);
    return res.status(200).json({
      success: true,
      source: 'Mock In-Memory Store',
      message: 'Mock item deleted successfully',
      id,
    });
  } catch (error) {
    return res.status(500).json({
      success: false,
      message: 'Failed to delete item',
      error: error.message,
    });
  }
};
