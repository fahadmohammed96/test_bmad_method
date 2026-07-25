import { PaginaInArrivo } from "@/components/PaginaInArrivo";
import { navCopy } from "@/lib/copy/nav";

export default function AdempimentiPage() {
  return (
    <PaginaInArrivo
      titolo={navCopy.adempimenti}
      descrizione="Il cruscotto degli Adempimenti (Alloggiati Web, Tassa di soggiorno, ISTAT, CIN) arriva con un ciclo di lavoro dedicato."
    />
  );
}
