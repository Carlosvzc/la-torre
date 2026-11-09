# Imagen del servidor de partida de La Torre (práctica 3.3)
FROM python:3.11-slim

# Sin archivos .pyc y con la salida de logs inmediata (se ve en kubectl logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODO=torre

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY juego/ juego/

# 7654: WebSocket del juego · 9100: /metrics para Prometheus
EXPOSE 7654 9100
USER 1000
CMD ["python", "server.py"]
