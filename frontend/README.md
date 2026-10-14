# Frontend

React + TypeScript + Vite client. It communicates with the backend through
REST endpoints under `/api/`; Vite proxies those requests during development.
Tailwind CSS is configured through its Vite plugin.

## Run locally

```powershell
npm.cmd install
npm.cmd run dev
```

The Vite server is available at `http://localhost:5173`. For a production
bundle, run `npm.cmd run build`. This folder is a client-only app: database
access and secrets belong in the backend, not in browser code.
