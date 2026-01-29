web: gunicorn app:app
worker: celery -A celery_worker.celery_app worker --loglevel=info
