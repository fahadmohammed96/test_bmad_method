/** Placeholder onesto per le sezioni consegnate dagli Epic successivi. */
export function PaginaInArrivo({
  titolo,
  descrizione,
}: {
  titolo: string;
  descrizione: string;
}) {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">{titolo}</h1>
      <p className="mt-2 text-muted">{descrizione}</p>
    </div>
  );
}
