import { dashboardCopy } from "@/lib/copy/dashboard";

/**
 * Dashboard frame (UX-DR2): ospita i riepiloghi contribuiti dagli Epic
 * successivi. Oggi: stato vuoto rassicurante, mai un buco.
 */
export default function DashboardPage() {
  const sezioni = [
    {
      titolo: dashboardCopy.sezioneCalendario,
      vuota: dashboardCopy.sezioneCalendarioVuota,
    },
    {
      titolo: dashboardCopy.sezioneAdempimenti,
      vuota: dashboardCopy.sezioneAdempimentiVuota,
    },
    {
      titolo: dashboardCopy.sezionePrezzi,
      vuota: dashboardCopy.sezionePrezziVuota,
    },
  ];
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">{dashboardCopy.titolo}</h1>
      <p className="mt-1 text-muted">{dashboardCopy.sottotitolo}</p>

      <section className="mt-6 rounded-lg border p-6">
        <h2 className="font-semibold">{dashboardCopy.statoVuotoTitolo}</h2>
        <p className="mt-1 text-sm leading-relaxed">
          {dashboardCopy.statoVuotoTesto}
        </p>
      </section>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {sezioni.map((sezione) => (
          <section key={sezione.titolo} className="rounded-lg border p-4">
            <h2 className="text-sm font-semibold">{sezione.titolo}</h2>
            <p className="mt-1 text-sm text-muted">{sezione.vuota}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
