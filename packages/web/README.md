# llm-spec frontend (React + Tailwind + Vite)

## setup

```bash
cd packages/web
pnpm install
pnpm dev
```

Env:
- `VITE_API_BASE_URL` default `http://localhost:8000`

## features

- Left menu pages: `Testing / Suites / Settings`
- Testing: pick multiple providers/routes/test cases and run in batch
- Suites: read-only registry browser (`provider/route/model`)
- Settings: read/write `llm-spec.toml`
- SSE realtime events + run_result.json rendering
