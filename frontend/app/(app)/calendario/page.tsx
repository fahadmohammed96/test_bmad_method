import { PaginaInArrivo } from "@/components/PaginaInArrivo";
import { navCopy } from "@/lib/copy/nav";

export default function CalendarioPage() {
  return (
    <PaginaInArrivo
      titolo={navCopy.calendario}
      descrizione="Il calendario unificato con la sincronizzazione dei Feed iCal arriva con il prossimo ciclo di lavoro."
    />
  );
}
