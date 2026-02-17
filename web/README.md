# Art Findr Web (React Migration)

React + Tailwind + shadcn-style frontend for Art Findr.

## Run locally

```bash
cd web
npm install
npm run dev
```

The app runs at `http://localhost:5173` and proxies API requests to `http://localhost:8000`.

## Build

```bash
npm run build
npm run preview
```

## Test

```bash
# Unit/integration (Vitest + Testing Library)
npm run test

# Browser e2e (Playwright)
npm run test:e2e
```

## Notes

- Uses TypeScript + Vite.
- Tailwind is configured in `tailwind.config.js`.
- UI primitives live in `src/components/ui`.
- API calls are in `src/lib/api.ts`.
