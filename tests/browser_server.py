"""Instância descartável para os roteiros de navegador, sem alterar instance/."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saude.app import create_app
from seed import seed
from waitress import serve

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="integra-browser-") as instance:
        app = create_app({"INSTANCE": instance})
        seed(app)
        print("Instância descartável: http://127.0.0.1:8081", flush=True)
        serve(app, host="127.0.0.1", port=8081, threads=16)
