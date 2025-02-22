#!/bin/bash
echo "Starting Bot..."
gunicorn -k uvicorn.workers.UvicornWorker bot:app --bind 0.0.0.0:8000