#!/bin/bash

# Start Gunicorn in Standard Mode
# We have removed the Celery worker to support Serverless/Render deployments
exec gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120