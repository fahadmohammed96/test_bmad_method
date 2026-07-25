import { PaginaInArrivo } from "@/components/PaginaInArrivo";
import { navCopy } from "@/lib/copy/nav";

export default function OperativitaPage() {
  return (
    <PaginaInArrivo
      titolo={navCopy.operativita}
      descrizione="Turni di pulizia e messaggi automatici agli Ospiti arrivano con un ciclo di lavoro dedicato."
    />
  );
}
