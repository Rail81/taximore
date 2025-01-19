bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/taximore/gunicorn_access.log"
errorlog = "/var/log/taximore/gunicorn_error.log"
loglevel = "info"

# Process naming
proc_name = "taximore_backend"

# SSL (if needed)
# keyfile = "/etc/ssl/private/your_domain.key"
# certfile = "/etc/ssl/certs/your_domain.crt"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
