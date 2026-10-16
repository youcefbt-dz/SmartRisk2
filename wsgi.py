"""نقطة دخول الإنتاج:  gunicorn wsgi:app"""
from smartrisk import create_app

app = create_app()
