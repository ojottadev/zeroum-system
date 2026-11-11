"""
wsgi.py - Ponto de entrada padrão WSGI para servidores de produção (Gunicorn, uWSGI, PythonAnywhere, etc.).
"""
from app import app

# 'application' é o nome padrão esperado por servidores WSGI como Apache/Passenger
application = app

if __name__ == "__main__":
    app.run()
