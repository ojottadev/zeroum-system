"""
index.py - Ponto de entrada alternativo para serviços que exigem 'index.py'.
"""
from app import app

# Exporta a aplicação Flask
application = app

if __name__ == "__main__":
    app.run()
