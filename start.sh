#!/bin/bash

# Start Celery
celery -A app.celery_app worker --loglevel=info &

# Start Gunicorn in Standard Mode (No Gevent)
exec gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
