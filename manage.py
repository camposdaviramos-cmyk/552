"""Criação inicial de usuário para ambiente sem dados de demonstração."""
import getpass
from werkzeug.security import generate_password_hash
from saude.app import create_app
from saude.db import db

if __name__=="__main__":
    app=create_app()
    with app.app_context():
        if db().execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise SystemExit("A base já tem usuários. Use a gestão de usuários na aplicação.")
        name=input("Nome do administrador: ").strip()
        username=input("Usuário: ").strip().lower()
        password=getpass.getpass("Senha (mínimo 12 caracteres): ")
        if len(name)<3 or len(username)<3 or len(password)<12:
            raise SystemExit("Dados inválidos.")
        db().execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,'admin')",(name,username,generate_password_hash(password)))
        db().commit()
        print("Administrador criado. Cadastre as unidades oficiais antes de operar.")
