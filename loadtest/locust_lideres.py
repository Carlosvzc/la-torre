"""Prueba de carga de la tabla de líderes serverless (práctica 3.5): 80 % lecturas, 20 % escrituras.

Uso (URL = Function URL de la Lambda, salida "lambda_url" de Terraform):
  locust -f locust_lideres.py --host https://xxxx.lambda-url.us-east-2.on.aws -u 500 -r 50 -t 5m --headless --csv resultados/lideres

Mientras corre, en CloudWatch → Lambda → torre-lideres → "ConcurrentExecutions" se ve cuántas
instancias levantó AWS, y en la columna p99 de Locust el efecto del arranque en frío.
"""
import random
import uuid

from locust import HttpUser, between, task

SALAS = ("solo", "bots", "grupo")


class Lector(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(8)                                   # 80 %: consultar el top
    def ver_top(self):
        sala = random.choice(SALAS)
        self.client.get(f"/?sala={sala}&orden={random.choice(['tiempo', 'victorias'])}", name="GET top")

    @task(2)                                   # 20 %: registrar el resultado de una run
    def registrar(self):
        self.client.post("/resultado", name="POST resultado", json={
            "sala": random.choice(SALAS), "jugadores": [f"carga-{uuid.uuid4().hex[:6]}"],
            "victoria": random.random() < 0.3, "tiempo_s": round(random.uniform(180, 600), 2)})
