# Memoria sidecar degli agenti BMAD

Ogni agente della squad ha una **memoria persistente** in `_bmad/_memory/<ruolo>-sidecar/`.
Va **letta all'avvio** di ogni run e **aggiornata via PR** (mai push diretto su `main`) quando l'agente impara qualcosa di importante e riutilizzabile.

## Struttura di ogni sidecar

```
<ruolo>-sidecar/
  memories.md      Fatti durevoli e decisioni apprese (append, con data)
  instructions.md  Preferenze operative e correzioni ricevute dall'umano
  knowledge/       Note di dominio più lunghe (un file per argomento)
```

## Mappa ruolo → agente

| Sidecar | Agente | Ruolo |
|---------|--------|-------|
| `analyst-sidecar/` | Mary | Business Analyst — Fase 1 Analysis |
| `pm-sidecar/` | John | Product Manager — Fase 2 Planning (leader squad) |
| `ux-sidecar/` | Sally | UX Designer — Fase 2 Planning |
| `architect-sidecar/` | Winston | System Architect — Fase 3 Solutioning |
| `dev-sidecar/` | Amelia | Senior Software Engineer — Fase 4 Implementation |
| `tech-writer-sidecar/` | Paige | Technical Writer — trasversale |
| `test-architect-sidecar/` | Murat | Master Test Architect — modulo TEA |

## Regole

- Un fatto per voce, con data e contesto. Non duplicare ciò che è già in `docs/project-context.md`.
- Non scrivere segreti, token o dati personali reali.
- Ogni agente scrive **solo** nella propria sidecar.
