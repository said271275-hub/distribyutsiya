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
bundle, run `npm.cmd run build`.

The client provides separate shop-owner and staff sign-in, phone/OTP
registration, role-protected placeholder panels and an account
deletion/recovery flow. The refresh token stays in an HttpOnly cookie; access
tokens are held in memory and renewed through the API wrapper. Business pages
(catalog, orders and trips) are not part of this stage. Database access and
secrets belong in the backend, not in browser code.
