FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

EXPOSE 10000
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 FLASK_ENV=production FLASK_APP=app.py

CMD ["gunicorn","--workers","1","--threads","4","--worker-class","gthread","--timeout","120","--preload","--bind","0.0.0.0:10000","app:app"]
