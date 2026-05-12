# LLM Spec Frontend

Vite + React frontend for the LLM Spec platform.

## Development

```bash
pnpm install
pnpm dev:reporter
```

The app defaults to `http://localhost:8788` for backend runs.

## Production Build

```bash
VITE_LLM_SPEC_BACKEND_URL=http://your-backend:8788 pnpm --filter @llm-spec/reporter build
pnpm --filter @llm-spec/reporter preview
```

Standard API tests can run directly in the browser. Switch them to backend mode when the target API blocks CORS. Agent tests always require the backend service.
