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
                    pausa = threading.Event()
                    for byte in preparata.corpo:
                        try:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                        except OSError:
                            return  # il client ha chiuso: e' l'esito atteso
                        pausa.wait(preparata.sgocciola_secondi)
                    return
                if preparata.corpo:
                    self.wfile.write(preparata.corpo)

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
