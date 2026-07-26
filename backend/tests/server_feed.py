"""Server HTTP locale: la rete si stub-a AL TRASPORTO, non nel service.

`ETag`, redirect, timeout, chiusura anticipata e cap di dimensione **sono**
il comportamento sotto test: un mock del client dentro il service li
cancella dal mondo e il test finisce per misurare il mock. È la lezione §3.3
dell'Epic 1, applicata prima invece che dopo.

Nessuna chiamata verso Internet: il server ascolta su 127.0.0.1 su una porta
effimera, e la guardia di isolamento della suite ammette solo il loopback.
"""

import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType

FINE_RIGA = b"\r\n"


@dataclass
class RispostaPreparata:
    stato: int = 200
    corpo: bytes = b""
    intestazioni: dict[str, str] = field(default_factory=dict)
    # Dichiara un Content-Length più lungo del corpo e chiude: è la
    # risposta troncata «con esito 200» di E2-G3.
    chiudi_a_meta: bool = False
    # Non risponde affatto: il client deve fermarsi sul timeout di lettura.
    non_rispondere: bool = False
    # Sgocciola il corpo un byte alla volta con questa pausa fra i byte.
    # Ogni singolo byte arriva DENTRO il timeout di lettura, quindi nessun
    # timeout per-operazione scatta mai: solo una deadline complessiva
    # sull'intero fetch può fermarlo.
    sgocciola_secondi: float | None = None
    # Sgocciola le INTESTAZIONI, non il corpo: la fase di testa non passa da
    # `iter_bytes`, quindi non incontra nessun checkpoint applicativo. Solo un
    # bound che vive sulla SOCKET la può fermare.
    sgocciola_intestazioni_secondi: float | None = None
    # Risponde normalmente, ma dopo questa attesa: serve a far consumare a
    # ogni hop una FRAZIONE del budget complessivo, che e' l'unico modo di
    # distinguere «budget del fetch» da «budget per hop».
    ritardo_secondi: float | None = None


class ServerFeed:
    def __init__(self) -> None:
        self._risposte: dict[str, RispostaPreparata] = {}
        # (metodo, percorso, intestazioni) di ogni richiesta ricevuta: è così
        # che si asserisce cosa il client ha REALMENTE mandato sul filo.
        self.richieste: list[tuple[str, str, dict[str, str]]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        # Segnalato all'uscita: sblocca gli handler in attesa invece di
        # lasciarli scadere.
        self._chiusura = threading.Event()

    def prepara(self, percorso: str, risposta: RispostaPreparata) -> str:
        self._risposte[percorso] = risposta
        return self.url(percorso)

    def url(self, percorso: str) -> str:
        assert self._server is not None
        indirizzo, porta = self._server.server_address[:2]
        return f"http://{indirizzo}:{porta}{percorso}"

    def __enter__(self) -> "ServerFeed":
        risposte = self._risposte
        richieste = self.richieste

        chiusura = self._chiusura

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 (nome imposto da BaseHTTPRequestHandler)
                try:
                    self._rispondi()
                except OSError:
                    # Il client ha abbandonato la connessione: e' l'esito
                    # atteso dei test di scadenza. Senza questo `socketserver`
                    # stampa un traceback che sembra un errore del test.
                    self.close_connection = True

            def _rispondi(self) -> None:
                richieste.append((self.command, self.path, dict(self.headers.items())))
                preparata = risposte.get(self.path)
                if preparata is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if preparata.non_rispondere:
                    # Connessione aperta e silenziosa: il client deve
                    # arrendersi sul timeout di lettura, non attendere. Il
                    # silenzio finisce quando il server chiude (`chiusura`),
                    # non dopo un'attesa fissa: un `Event` anonimo mai
                    # segnalabile lascerebbe un thread appeso per 30 secondi
                    # a ogni test che usa questa forma.
                    chiusura.wait(30)
                    return
                if preparata.ritardo_secondi is not None and chiusura.wait(
                    preparata.ritardo_secondi
                ):
                    return
                if preparata.sgocciola_intestazioni_secondi is not None:
                    self._sgocciola_intestazioni(preparata)
                    return
                self.send_response(preparata.stato)
                for chiave, valore in preparata.intestazioni.items():
                    self.send_header(chiave, valore)
                if preparata.chiudi_a_meta:
                    self.send_header("Content-Length", str(len(preparata.corpo) * 2))
                    self.end_headers()
                    self.wfile.write(preparata.corpo)
                    self.close_connection = True
                    return
                self.send_header("Content-Length", str(len(preparata.corpo)))
                self.end_headers()
                if preparata.sgocciola_secondi is not None:
                    for byte in preparata.corpo:
                        try:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                        except OSError:
                            return  # il client ha chiuso: e' l'esito atteso
                        # `chiusura`, non un Event anonimo: alla fine del test
                        # l'handler esce subito invece di dormire.
                        if chiusura.wait(preparata.sgocciola_secondi):
                            return
                    return
                if preparata.corpo:
                    self.wfile.write(preparata.corpo)

            def _sgocciola_intestazioni(self, preparata: RispostaPreparata) -> None:
                """Riga di stato, poi intestazioni un byte alla volta, senza
                mai chiudere la testa della risposta."""
                pausa = preparata.sgocciola_intestazioni_secondi or 0.1
                self.wfile.write(b"HTTP/1.1 200 OK" + FINE_RIGA)
                self.wfile.flush()
                indice = 0
                while not chiusura.is_set():
                    # Intestazioni sintetiche e infinite: ogni byte arriva
                    # dentro il timeout di lettura, quindi nessun timeout
                    # per-operazione scatta mai.
                    riga = f"X-Riempimento-{indice}: {indice}".encode() + FINE_RIGA
                    for byte in riga:
                        try:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                        except OSError:
                            return  # il client ha chiuso: e' l'esito atteso
                        if chiusura.wait(pausa):
                            return
                    indice += 1

            def log_message(self, formato: str, *argomenti: object) -> None:
                """Silenzio: l'output del test non è un access log."""

        # 16 > gli 8 client che la barrier del test di gara rilascia insieme:
        # con la coda di ascolto di default (5) tre connessioni verrebbero
        # rifiutate dal sistema operativo e il test misurerebbe quello.
        class Server(ThreadingHTTPServer):
            request_queue_size = 16
            daemon_threads = True

        self._server = Server(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        errore: BaseException | None,
        traccia: TracebackType | None,
    ) -> None:
        self._chiusura.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
