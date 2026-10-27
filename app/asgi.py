"""uvicorn から起動する入り口（uvicorn app.asgi:app）"""
from .main import create_app

app = create_app()
