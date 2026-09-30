"""Backup SQLite consistente, criptografado, com restauração não destrutiva."""
import argparse
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from saude.app import create_app

def create_backup(app, destination=None):
    target=Path(destination or Path(app.config["INSTANCE"])/"backups")
    target.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot=Path(tmp)/"snapshot.db"
        with closing(sqlite3.connect(app.config["DATABASE"])) as source, closing(sqlite3.connect(snapshot)) as output:
            source.backup(output)
            if output.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("A integridade do snapshot não foi confirmada.")
        encrypted=app.extensions["cipher"].encrypt(snapshot.read_bytes())
    filename=target/(datetime.now(timezone.utc).strftime("saude-%Y%m%dT%H%M%S%fZ")+".db.enc")
    temporary=filename.with_suffix(".tmp")
    temporary.write_bytes(encrypted)
    temporary.replace(filename)
    return filename

def restore_backup(app, source, output):
    output=Path(output)
    if output.exists():
        raise ValueError("O destino já existe. Escolha um novo arquivo; a base atual não será sobrescrita.")
    plaintext=app.extensions["cipher"].decrypt(Path(source).read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        check=Path(tmp)/"check.db"; check.write_bytes(plaintext)
        with closing(sqlite3.connect(check)) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Backup inválido.")
    with output.open("xb") as file:
        file.write(plaintext)
    return output

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--watch",action="store_true")
    parser.add_argument("--interval",type=int,default=3600)
    parser.add_argument("--retain",type=int,default=168)
    parser.add_argument("--restore")
    parser.add_argument("--output")
    args=parser.parse_args()
    app=create_app()
    if args.restore:
        if not args.output: parser.error("Use --output para um novo arquivo de restauração.")
        print(restore_backup(app,args.restore,args.output))
    else:
        if args.interval<60 or args.retain<1: parser.error("Intervalo mínimo de 60 segundos e retenção positiva.")
        while True:
            filename=create_backup(app)
            print(f"Backup concluído: {filename}",flush=True)
            backup_root=filename.parent.resolve()
            for old in sorted(backup_root.glob("saude-*.db.enc"),reverse=True)[args.retain:]:
                if old.resolve().parent!=backup_root: raise RuntimeError("Destino de retenção fora do diretório de backups.")
                old.unlink()
            if not args.watch: break
            time.sleep(args.interval)
