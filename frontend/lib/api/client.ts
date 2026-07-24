/**
 * Client API tipizzato (AD-14): il frontend consuma ESCLUSIVAMENTE questo
 * client generato dallo schema OpenAPI del backend — vietato scrivere
 * fetch tipizzati a mano.
 *
 * Rigenerare i tipi dopo ogni modifica al contratto: `npm run generate:api`.
 */
import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({
  baseUrl: apiBaseUrl,
  // Sessione server-side via cookie HttpOnly (AD-15).
  credentials: "include",
  // Risolta a ogni chiamata, non all'import: rispetta il fetch corrente
  // del runtime (patch di Next.js, stub nei test).
  fetch: (request) => globalThis.fetch(request),
});
