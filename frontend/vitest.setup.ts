import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Senza `globals: true` l'auto-cleanup di Testing Library non si aggancia:
// smontiamo esplicitamente tra un test e l'altro.
afterEach(cleanup);
