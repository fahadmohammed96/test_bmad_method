"""Modulo `config_normativa` (AD-9, AD-18).

Proprietario di `comune`, `regione`, `comune_config`, `regione_config` e
del registro di audit delle modifiche. Aliquote, esenzioni, periodicità e
tracciati sono DATI a validità temporale: aggiornarli è un'operazione
dati via endpoint interni auditati, mai un rilascio di codice (NFR-4).

Anagrafica e configurazione NON sono dati tenant-owned: sono riferimenti
condivisi tra tutti gli Host (vedi allowlist in tests/test_tenancy_convention.py).
"""
