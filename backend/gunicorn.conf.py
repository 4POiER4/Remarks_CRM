import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count())))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
