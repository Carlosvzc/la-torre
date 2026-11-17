# Imagen de Locust para correr la prueba 3.4 DENTRO del clúster (misma región que los servidores).
# Se construye desde la raíz del repo:  docker build -f loadtest/Dockerfile -t torre-locust .
FROM python:3.11-slim
WORKDIR /app
COPY loadtest/requirements.txt .
RUN pip install --no-cache-dir locust==2.47.0 websocket-client==1.9.2 requests==2.34.2
COPY server/juego /server/juego
COPY loadtest/locustfile.py loadtest/estrategia.py /app/
# estrategia.py busca ../server/juego (desde /app eso es /server/juego)
RUN mkdir -p /app/resultados
ENTRYPOINT ["locust", "-f", "/app/locustfile.py"]
