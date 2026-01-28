import os
from app import app, celery_app
if __name__ == '__main__': celery_app.start()
