import argparse
from saude.app import create_app

app=create_app()

if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Integra Saúde")
    parser.add_argument("--port",type=int,default=8080)
    parser.add_argument("--host",default="127.0.0.1")
    args=parser.parse_args()
    from waitress import serve
    print(f"Integra Saúde disponível em http://{args.host}:{args.port}",flush=True)
    serve(app,host=args.host,port=args.port,threads=8)
