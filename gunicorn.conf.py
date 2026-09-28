"""Gunicorn pour Coolify / Docker.

Le worker sync par défaut ne signale plus qu'il est vivant tant qu'il lit
un corps de requête. Un upload (photo article, logo, preuve) plus long que
le timeout de 30 s est alors tué (SIGABRT puis SIGKILL). Le journal affiche
« Perhaps out of memory? » même quand c'est ce délai qui a tué le processus.

gthread continue de signaler l'activité pendant qu'un thread lit l'upload.
Deux processus au lieu de trois limitent la RAM sur le VPS partagé.
"""

import os

bind = "0.0.0.0:8001"
worker_class = "gthread"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("WEB_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 100
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP", "/cimentapp/tmp")
limit_request_line = 8190
limit_request_fields = 200
limit_request_field_size = 8190
accesslog = "-"
errorlog = "-"
capture_output = True
preload_app = False
