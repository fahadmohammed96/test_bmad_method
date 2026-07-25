"use client";

import { useState } from "react";
import { authCopy } from "@/lib/copy/auth";

/** Form email+password condiviso da accesso e registrazione (AD-15). */
export function FormCredenziali({
  titolo,
  azione,
  inCorso,
  errore,
  onSubmit,
  nuovaPassword,
}: {
  titolo: string;
  azione: string;
  inCorso: boolean;
  errore: string | null;
  onSubmit: (credenziali: { email: string; password: string }) => void;
  nuovaPassword: boolean;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <form
      className="flex w-full max-w-sm flex-col gap-3"
      onSubmit={(evento) => {
        evento.preventDefault();
        onSubmit({ email, password });
      }}
    >
      <h1 className="text-2xl font-semibold">{titolo}</h1>
      <label className="flex flex-col gap-1 text-sm">
        {authCopy.emailEtichetta}
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(evento) => setEmail(evento.target.value)}
          className="rounded border px-2 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {authCopy.passwordEtichetta}
        <input
          type="password"
          required
          minLength={8}
          autoComplete={nuovaPassword ? "new-password" : "current-password"}
          value={password}
          onChange={(evento) => setPassword(evento.target.value)}
          className="rounded border px-2 py-2"
        />
      </label>
      {nuovaPassword && (
        <p className="text-xs text-muted">{authCopy.passwordRequisito}</p>
      )}
      <button
        type="submit"
        disabled={inCorso}
        className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
      >
        {azione}
      </button>
      {errore && (
        <p role="alert" className="text-sm text-danger">
          {errore}
        </p>
      )}
    </form>
  );
}
