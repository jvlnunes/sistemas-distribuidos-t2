import json
import logging
import redis
from kafka import KafkaConsumer
from multiprocessing import Process
from time import sleep
import requests
from datetime import datetime

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Conectando ao Redis (certifique-se de que o Redis esteja rodando)
r = redis.Redis(host="localhost", port=6379, db=0)

def update_device_state(message):
    """
    Atualiza o estado do dispositivo no Redis com todas as informações necessárias.
    """
    device_id = message['device_id']

    # Estado atualizado do dispositivo com todas as informações necessárias
    full_device_data = {
        "device_id": message["device_id"],
        "name": message["name"],
        "device_type": message["device_type"],
        "device_ip": message["device_ip"],
        "device_port": message["device_port"],
        "status": message["status"],  # Mantém a estrutura de status
        "last_liveness_probe": datetime.now().isoformat()  # Armazena o timestamp do último liveness probe
    }

    # Salva no Redis
    r.set(device_id, json.dumps(full_device_data))
    logging.info("Estado do dispositivo %s atualizado para: %s", device_id, full_device_data)

def process_device_message(message):
    """
    Processa a mensagem recebida do dispositivo e armazena no Redis.
    """
    logging.info("Processando mensagem do dispositivo: %s", message)
    update_device_state(message)  # Salva o estado completo no Redis

def listen_device_messages():
    """
    Escuta as mensagens enviadas pelos dispositivos no tópico Kafka "device_message".
    """
    logging.info("Listening device messages")
    consumer = KafkaConsumer("device_message", bootstrap_servers="localhost:9092")

    for msg in consumer:
        logging.info("Chegou uma mensagem no tópico de mensagens: %s", msg.value)
        try:
            message_data = json.loads(msg.value)
            process_device_message(message_data)
        except Exception as e:
            logging.error("Erro ao processar a mensagem: %s", e)

def listen_liveness_probe():
    """
    Escuta as mensagens de liveness probe enviadas pelos dispositivos no Kafka.
    """
    logging.info("Listening liveness probe messages")
    consumer = KafkaConsumer("liveness_probe", bootstrap_servers="localhost:9092")

    for msg in consumer:
        logging.info("Chegou uma mensagem no tópico de liveness_probe: %s", msg.value)
        requests.post("http://localhost:8000/update_liveness_probe", data=msg.value)

def send_liveness_probe_check():
    """
    Periodicamente verifica se há dispositivos inativos e informa ao FastAPI.
    """
    while True:
        sleep(10)
        requests.post("http://localhost:8000/check_liveness_probe")
        logging.info("Checando dispositivos inativos")

if __name__ == "__main__":
    p1 = Process(target=listen_device_messages)
    p2 = Process(target=listen_liveness_probe)
    p3 = Process(target=send_liveness_probe_check)

    p1.start()
    p2.start()
    p3.start()
    p1.join()
    p2.join()
    p3.join()
