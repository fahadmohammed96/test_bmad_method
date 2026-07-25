import { PaginaInArrivo } from "@/components/PaginaInArrivo";
import { navCopy } from "@/lib/copy/nav";

export default function PrezziPage() {
  return (
    <PaginaInArrivo
      titolo={navCopy.prezzi}
      descrizione="Le Regole di prezzo con anteprima spiegata arrivano con un ciclo di lavoro dedicato."
    />
  );
}
