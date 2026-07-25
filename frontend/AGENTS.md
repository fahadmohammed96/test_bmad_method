# Progetto

Frontend di **HostPilot** — gestionale per host privati di affitti brevi.
Consuma il backend FastAPI ESCLUSIVAMENTE tramite il client TypeScript
generato dall'OpenAPI (AD-14): vietato scrivere fetch tipizzati a mano.
Contratto vincolante: `docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md`.

# Stack

- Next.js 16.2 (App Router) + React 19, TypeScript strict, Node 24
- Styling: Tailwind CSS 4 — token in `app/globals.css` (blocco `@theme`);
  shadcn/ui resta il seed UI ratificato (G3-1): si inizializza alla prima
  Story che richiede componenti complessi (form multi-step, dialog);
  fino ad allora componenti Tailwind semplici coerenti coi token
- Stato server: TanStack Query 5 (provider in `app/providers.tsx`);
  nessuno store globale aggiuntivo senza motivazione registrata
- Package manager: npm — usa SOLO questo (`npm ci` per installare)
- Test: Vitest + React Testing Library; E2E: Playwright

# Comandi (verificati sul repo pulito)

- Dev server: `npm run dev` → http://localhost:3000
- Build: `npm run build`
- Unit/component test: `npm test` — la suite deve passare prima di ogni PR
- Lint: `npm run lint` · Typecheck: `npm run typecheck`
- Client API: `npm run generate:api` — rigenera `lib/api/schema.d.ts` da
  `../backend/openapi.json`; la CI verifica l'allineamento
- E2E: `npm run test:e2e` (prima volta: `npx playwright install --with-deps chromium`)

# Struttura

- `app/` — route, layout, pagine (App Router); test accanto al codice in `__tests__/`
- `components/` — componenti riusabili; un componente per file, PascalCase
- `lib/api/` — client generato da OpenAPI (`schema.d.ts` + `client.ts`)
- `lib/copy/` — stringhe it-IT per feature: NESSUNA stringa di dominio
  hardcoded nei componenti; termini del Glossario verbatim anche in UI
- `e2e/` — suite end-to-end
- `.github/workflows/ci.yml` (root repo) — lint + typecheck + test + build su ogni PR

# Convenzioni di codice

- Componenti PascalCase, file utility kebab-case, import assoluti da `@/`
- Niente `any`; tipi espliciti sulle API pubbliche dei moduli
- Componenti server-first (App Router); stato client solo per interazione locale
- I valori derivati di dominio (`livello_urgenza`, prezzi, stati) arrivano
  dall'API e si PRESENTANO, mai si ricalcolano (AD-14)
- Formati italiani ovunque: date gg/mm/aaaa, valuta €, virgola decimale (UX-DR11)

# Design system

- Token: SOLO in `app/globals.css` (`@theme`). Mai valori hardcoded di
  colore, spaziatura fuori scala, font o raggi nei componenti.
- Contrasto minimo: WCAG 2.1 AA (NFR-8); badge di stato sempre testo +
  icona, mai solo colore (UX-DR4)
- Breakpoint: default Tailwind; layout responsive mobile-first (UX-DR12)
- Motion: transizioni 150–300ms; `prefers-reduced-motion` gestito in `globals.css`

# Layer server del framework

- Route handlers/server components in `app/` secondo le convenzioni Next
- Variabili d'ambiente mai esposte al client se non prefissate `NEXT_PUBLIC_`
- Backend: HostPilot API (`NEXT_PUBLIC_API_URL`), sessione server-side via
  cookie HttpOnly (AD-15): il client usa `credentials: "include"`

# Flusso di lavoro

- I task arrivano come issue su Multica; consegne SEMPRE via PR verso
  `main` (protetto), mai push diretto; il merge è dell'umano
- La CI (lint + typecheck + unit test + build + contratto API) deve essere
  verde perché la PR sia approvabile
