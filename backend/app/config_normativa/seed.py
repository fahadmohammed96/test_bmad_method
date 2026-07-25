"""Anagrafica di base seedata dai codici ISTAT (AD-9).

Le 20 Regioni hanno codici stabili e vivono qui. I Comuni sono ~8.000 e
si importano dal file ufficiale ISTAT con `importa_comuni.py`: nessun
codice inventato nel repository. Il perimetro iniziale dei Comuni da
configurare resta la decisione di prodotto G2-B — il sistema degrada in
sicurezza per qualunque Comune non ancora presente o non configurato.
"""

REGIONI_ISTAT: tuple[tuple[str, str], ...] = (
    ("01", "Piemonte"),
    ("02", "Valle d'Aosta/Vallée d'Aoste"),
    ("03", "Lombardia"),
    ("04", "Trentino-Alto Adige/Südtirol"),
    ("05", "Veneto"),
    ("06", "Friuli-Venezia Giulia"),
    ("07", "Liguria"),
    ("08", "Emilia-Romagna"),
    ("09", "Toscana"),
    ("10", "Umbria"),
    ("11", "Marche"),
    ("12", "Lazio"),
    ("13", "Abruzzo"),
    ("14", "Molise"),
    ("15", "Campania"),
    ("16", "Puglia"),
    ("17", "Basilicata"),
    ("18", "Calabria"),
    ("19", "Sicilia"),
    ("20", "Sardegna"),
)
