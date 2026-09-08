FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_DATABASE_URL=sqlite:///db.sqlite3 DJANGO_ALLOW_DEV_SECRET=1 python manage.py collectstatic --noinput
EXPOSE 8000
# The default single sync worker means one slow request blocks the whole API,
# including the container healthcheck. Two workers with two threads each fit the
# 512m limit and bound the DB connections (4 with CONN_MAX_AGE) while keeping a
# stalled request from starving the rest. The timeout is above the frontend's
# 10s fetch budget so gunicorn never kills a request the client still awaits.
# Access logging stays off on purpose: ObservabilityMiddleware already emits one
# structured JSON line per request, and gunicorn's plain-text log would mix two
# formats into the same stdout stream.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "2", "--timeout", "30", \
     "--graceful-timeout", "30", "--keep-alive", "5", \
     "--max-requests", "2000", "--max-requests-jitter", "200"]
