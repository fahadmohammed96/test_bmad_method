import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...coreWebVitals,
  ...typescript,
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "playwright-report/**",
      "test-results/**",
      // Output della misura di copertura: non è codice nostro. In CI `lint`
      // gira prima di `test:coverage` e non lo incontrerebbe, ma un giorno
      // qualcuno riordinerà gli step e allora eslint segnalerebbe un file
      // generato — un rumore che si impara a ignorare, e le cose che si
      // imparano a ignorare sono quelle che poi nascondono un difetto vero.
      "coverage/**",
      "lib/api/schema.d.ts",
    ],
  },
];

export default eslintConfig;
