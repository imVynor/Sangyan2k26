# 🚀 MERN Stack Starter with Live Mock Connection

A modern, production-grade **MERN** (MongoDB, Express, React, Node.js) starter template with an interactive **mock connection fallback** system.

---

## 🌟 Key Highlights

- **Seamless Mock Connection**: Works immediately out of the box! If local MongoDB isn't running, the Express backend automatically switches to an in-memory mock store and provides realistic mock CRUD data without crashing.
- **Dual-Mode Ready**: When you are ready to use real MongoDB, simply set your `MONGO_URI` in `backend/.env`.
- **Modern Vite + React 19 Frontend**: Fast Hot Module Replacement (HMR) with pre-configured `/api` proxy.
- **Rich Dark Glassmorphism Design**: Custom vanilla CSS design system with responsive layouts, ambient glowing gradients, modern typography (Inter + Outfit), and micro-animations.
- **RESTful API**: Clean routes, controller architecture, Mongoose schemas, CORS configuration, and request logging.
- **Unified Orchestration**: Root `package.json` with scripts to run both client and server concurrently with one command.
- **Comprehensive `.gitignore`**: Pre-configured ignoring `node_modules`, `.env`, builds, and cache files across all directories.

---

## 📁 Project Structure

```text
Sungyan/
├── .gitignore               # Root gitignore for client, server, and root
├── package.json             # Root orchestrator with concurrently scripts
├── README.md                # Project documentation
│
├── backend/                 # Node.js + Express REST API
│   ├── .env.example         # Example environment configuration
│   ├── .env                 # Local environment variables
│   ├── package.json         # Backend dependencies (express, mongoose, cors, dotenv)
│   └── src/
│       ├── config/
│       │   └── db.js        # Mongoose connection with auto-mock fallback
│       ├── controllers/
│       │   └── itemController.js # Dual-mode controller (MongoDB + Mock memory)
│       ├── models/
│       │   └── Item.js      # Mongoose schema
│       ├── routes/
│       │   └── itemRoutes.js# REST routes (/api/items)
│       └── server.js        # Express app entry & /api/health endpoint
│
└── frontend/                # React 19 + Vite SPA
    ├── index.html           # HTML template with Google Fonts
    ├── package.json         # Frontend dependencies
    ├── vite.config.js       # Vite configuration with /api reverse proxy
    └── src/
        ├── components/
        │   ├── Navbar.jsx           # Top navigation with tech badges
        │   ├── ConnectionBanner.jsx # Real-time latency, status & handshake inspector
        │   ├── ItemForm.jsx         # Create record form
        │   ├── ItemList.jsx         # Interactive list with filters & delete
        │   └── TechStackGrid.jsx    # Visual architecture breakdown
        ├── services/
        │   └── api.js               # API service with client-side fallback
        ├── App.jsx                  # Main application dashboard
        ├── index.css                # Vanilla CSS design system
        └── main.jsx                 # React root renderer
```

---

## ⚡ Quick Start

### 1. Install Dependencies

You can install all dependencies (root, backend, frontend) with a single command:

```bash
npm run install:all
```

Or install individually:
```bash
npm install                     # in root
npm install --prefix backend    # in backend
npm install --prefix frontend   # in frontend
```

### 2. Start Both Frontend & Backend Together

```bash
npm run dev
```

- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:5000](http://localhost:5000)
- **Health / Mock Handshake**: [http://localhost:5000/api/health](http://localhost:5000/api/health)

---

## 🛠️ Running Individually

If you prefer separate terminal windows:

### Terminal 1 (Backend):
```bash
npm run dev:server
# or: cd backend && npm run dev
```

### Terminal 2 (Frontend):
```bash
npm run dev:client
# or: cd frontend && npm run dev
```

---

## 🔌 Mock Connection vs. Real MongoDB

This template features a **zero-friction development setup**:

1. **Mock Mode (Default when MongoDB is not running)**:
   - Express launches normally on port 5000.
   - It attempts to reach MongoDB for 2.5s; if offline or `MONGO_URI` is not set, it switches to an in-memory mock store.
   - The frontend communicates via `/api/items` and `/api/health` with real HTTP requests and realistic mock data.
   - The UI displays a yellow badge: `Connected (Mock Mode)`.

2. **MongoDB Live Mode**:
   - Start MongoDB locally or supply a MongoDB Atlas connection string in `backend/.env`:
     ```env
     MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/mern_db?retryWrites=true&w=majority
     ```
   - Restart the backend. Mongoose will connect and the UI automatically switches to a green badge: `Connected (MongoDB Live)`.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Diagnostic endpoint returning connection status, mode, and uptime |
| `GET` | `/api/items` | Retrieve all items (from MongoDB or Mock Store) |
| `POST` | `/api/items` | Create a new item (`title`, `description`, `category`) |
| `PATCH`| `/api/items/:id/toggle` | Toggle completed boolean status |
| `DELETE`| `/api/items/:id` | Remove an item by ID |

---

## 📦 Production Build

To build the frontend for production:

```bash
npm run build:client
```
The output will be placed in `frontend/dist`.
