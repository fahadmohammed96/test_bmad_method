import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["app/**/*.test.{ts,tsx}", "components/**/*.test.{ts,tsx}", "lib/**/*.test.{ts,tsx}"],
    // Copertura misurata, non dichiarata (MYL-59). Fino al 30/07 questo
    // progetto non produceva alcun report di copertura: il
    // `0.0% Coverage on New Code` del Quality Gate SonarCloud non era un
    // esito, era l'assenza del dato.
    coverage: {
      provider: "v8",
      // `lcovonly` per `diff-cover` nella CI, `text` per chi legge il log,
      // `json-summary` perche' il numero finisca nel riepilogo del job senza
      // che qualcuno lo debba ricavare a occhio da una tabella.
      //
      // `lcovonly` e non `lcov`: il secondo genera anche il report HTML in
      // `coverage/lcov-report/`, decine di file JS generati che nessuno apre in
      // CI e che eslint finisce per analizzare al primo riordino degli step.
      reporter: ["text", "lcovonly", "json-summary"],
      reportsDirectory: "./coverage",
      // `all: true` — i file che nessun test importa contano 0, non "assente".
      // Senza questo un componente consegnato senza test SPARISCE dalla misura
      // invece di abbassarla: e' il modo piu' silenzioso di avere una
      // copertura finta, ed e' la stessa forma del difetto di MYL-59.
      all: true,
      include: ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
      exclude: [
        "**/*.test.{ts,tsx}",
        "**/*.d.ts",
        // Client generato dall'OpenAPI: non e' codice nostro ed e' gia'
        // sorvegliato dal job `api-contract`, che fallisce se divergesse dal
        // contratto. Misurarlo direbbe solo quanta parte del contratto
        // toccano i test.
        "lib/api/schema.d.ts",
      ],
      // Pavimento GLOBALE, da leggere come backstop. Misura reale al 30/07 su
      // `main` (7d4eb7c), 140 test verdi: **73.93%** di riga.
      //
      // Molto piu' basso del backend (96.44%) per una ragione strutturale, non
      // per disciplina: le `page.tsx` e `lib/api/hooks.ts` sono esercitate
      // dagli **e2e Playwright**, la cui copertura non viene raccolta. Alzare
      // la soglia sopra la misura reale spingerebbe a scrivere unit test per
      // cio' che gli e2e coprono gia', cioe' a produrre rumore per far salire
      // un numero. Il pavimento sta a 70.
      //
      // Il cancello che morde e' `diff-cover` sulle righe toccate dalla PR
      // (job `frontend` della CI), non questa soglia.
      thresholds: {
        lines: 70,
        statements: 70,
        branches: 80,
        functions: 70,
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
