FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_DEBUG=false
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=5000

# Use a single worker by default to reduce memory usage during startup/runtime.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "backend.app:app"]
