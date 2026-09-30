"""WSGI entrypoint for Vercel and the local development server."""

import os
import tempfile
from pathlib import Path

from saude.app import create_app

# Vercel's application bundle is read-only. SQLite here is temporary and
# isolated per function instance; production persistence needs external storage.
config = {}
if os.environ.get("VERCEL") == "1":
    config["INSTANCE"] = str(Path(tempfile.gettempdir()) / "integra-saude")

app = create_app(config)

if os.environ.get("VERCEL") == "1":
    app.logger.warning(
        "Vercel: SQLite and generated keys use temporary storage; "
        "data is not durable or shared between function instances."
    )

if __name__ == "__main__":
    import argparse
    from waitress import serve

    parser = argparse.ArgumentParser(description="Integra Saúde")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    print(f"Integra Saúde disponível em http://{args.host}:{args.port}", flush=True)
    serve(app, host=args.host, port=args.port, threads=8)
