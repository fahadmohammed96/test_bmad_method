# HostPilot — Frontend

Frontend Next.js del gestionale HostPilot. Le convenzioni operative sono in
**[AGENTS.md](./AGENTS.md)**: è la fonte di verità, questo README è solo
l'ingresso.

## Avvio rapido

```bash
npm ci
cp .env.example .env.local
npm run dev    # http://localhost:3000
```

## Comandi

| Comando                | Cosa fa                                          |
| ---------------------- | ------------------------------------------------ |
| `npm run dev`          | Server di sviluppo                               |
| `npm run build`        | Build di produzione                              |
| `npm test`             | Unit/component test (Vitest)                     |
| `npm run lint`         | Lint                                             |
| `npm run typecheck`    | Typecheck TypeScript                             |
| `npm run generate:api` | Rigenera il client tipizzato da `backend/openapi.json` |
| `npm run test:e2e`     | E2E (Playwright)                                 |
