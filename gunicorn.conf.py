import multiprocessing

bind = "0.0.0.0:10000"
workers = 3  # Для разработки достаточно 3-5
# workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
timeout = 120
keepalive = 5
max_requests = 500
max_requests_jitter = 50

# (Необязательно, но полезно для отладки)
accesslog = "-"
errorlog = "-"
loglevel = "info"




# Для production
preload_app = True  # Ускоряет запуск workers
worker_class = "gthread"  # Явно указываем тип workers (у вас используется по умолчанию)

# Для безопасности
limit_request_line = 4094
limit_request_fields = 100

# Graceful shutdown
graceful_timeout = 30
