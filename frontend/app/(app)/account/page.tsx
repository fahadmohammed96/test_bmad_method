"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  useAggiornaPreferenze,
  useCambiaPassword,
  useLogout,
  useMe,
  type CanaleNotifica,
} from "@/lib/api/hooks";
import { accountCopy } from "@/lib/copy/account";
import { authCopy } from "@/lib/copy/auth";
import { navCopy } from "@/lib/copy/nav";

export default function AccountPage() {
  const router = useRouter();
  const { data: me } = useMe();
  const preferenze = useAggiornaPreferenze();
  const cambioPassword = useCambiaPassword();
  const logout = useLogout();

  const [passwordAttuale, setPasswordAttuale] = useState("");
  const [passwordNuova, setPasswordNuova] = useState("");

  if (!me) return null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">{accountCopy.titolo}</h1>
        <p className="mt-1 text-sm text-muted">
          {accountCopy.emailEtichetta}: {me.email}
        </p>
      </div>

      <section aria-labelledby="titolo-notifiche">
        <h2 id="titolo-notifiche" className="font-semibold">
          {accountCopy.sezioneNotifiche}
        </h2>
        <label className="mt-2 flex items-center gap-2 text-sm">
          {accountCopy.canaleEtichetta}
          <select
            aria-label={accountCopy.canaleEtichetta}
            value={me.canale_notifica_preferito}
            onChange={(evento) =>
              preferenze.mutate(evento.target.value as CanaleNotifica)
            }
            className="rounded border px-2 py-1"
          >
            <option value="email">{accountCopy.canaleEmail}</option>
            <option value="in_app">{accountCopy.canaleInApp}</option>
          </select>
        </label>
        {preferenze.isSuccess && (
          <p role="status" className="mt-1 text-sm text-muted">
            {accountCopy.preferenzeSalvate}
          </p>
        )}
      </section>

      <section aria-labelledby="titolo-password">
        <h2 id="titolo-password" className="font-semibold">
          {accountCopy.sezionePassword}
        </h2>
        <form
          className="mt-2 flex max-w-sm flex-col gap-3"
          onSubmit={(evento) => {
            evento.preventDefault();
            cambioPassword.mutate(
              {
                password_attuale: passwordAttuale,
                password_nuova: passwordNuova,
              },
              {
                onSuccess: () => {
                  setPasswordAttuale("");
                  setPasswordNuova("");
                },
              },
            );
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            {accountCopy.passwordAttuale}
            <input
              type="password"
              required
              autoComplete="current-password"
              value={passwordAttuale}
              onChange={(evento) => setPasswordAttuale(evento.target.value)}
              className="rounded border px-2 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {accountCopy.passwordNuova}
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={passwordNuova}
              onChange={(evento) => setPasswordNuova(evento.target.value)}
              className="rounded border px-2 py-2"
            />
          </label>
          <p className="text-xs text-muted">{authCopy.passwordRequisito}</p>
          <button
            type="submit"
            disabled={cambioPassword.isPending}
            className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
          >
            {accountCopy.salvaPassword}
          </button>
          {cambioPassword.isSuccess && (
            <p role="status" className="text-sm text-muted">
              {accountCopy.passwordAggiornata}
            </p>
          )}
          {cambioPassword.isError && (
            <p role="alert" className="text-sm text-danger">
              {cambioPassword.error.message}
            </p>
          )}
        </form>
      </section>

      <section aria-labelledby="titolo-strutture">
        <h2 id="titolo-strutture" className="font-semibold">
          {navCopy.strutture}
        </h2>
        <Link
          href="/strutture"
          className="mt-1 inline-block text-sm underline-offset-2 hover:underline"
        >
          {accountCopy.gestisciStrutture}
        </Link>
      </section>

      <div>
        <button
          type="button"
          onClick={() =>
            logout.mutate(undefined, {
              onSuccess: () => router.replace("/accesso"),
            })
          }
          className="rounded border px-3 py-2 text-sm"
        >
          {accountCopy.esci}
        </button>
      </div>
    </div>
  );
}
