"""Esporta lo schema OpenAPI generato da FastAPI (AD-14).

Output deterministico in `backend/openapi.json`; il client TypeScript del
frontend è generato da questo file (vedi `frontend/package.json`,
script `generate:api`). La CI verifica che contratto e client committati
siano allineati al codice.
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Lo script gira anche quando il progetto non è installato nel venv
# (CI: `uv sync --no-install-project`, vedi .github/workflows/ci.yml).
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

OUTPUT = BACKEND_DIR / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI scritto in {OUTPUT}")


if __name__ == "__main__":
    main()
