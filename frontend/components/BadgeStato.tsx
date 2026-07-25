/**
 * Badge di stato: SEMPRE testo + icona, mai solo colore (UX-DR4).
 */
export function BadgeStato({
  icona,
  testo,
  tono,
}: Readonly<{
  icona: string;
  testo: string;
  tono: "ok" | "avviso" | "neutro";
}>) {
  const toni = {
    ok: "border-primary/40 text-primary",
    avviso: "border-danger/40 text-danger",
    neutro: "border-muted/40 text-muted",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${toni[tono]}`}
    >
      <span aria-hidden="true">{icona}</span>
      {testo}
    </span>
  );
}
