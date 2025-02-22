import logging
import uuid
import json
from time import sleep, time
from threading import Thread, Event
from concurrent import futures

import grpc
from kafka import KafkaProducer
from proto import grpc_pb2
from proto import grpc_pb2_grpc

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class RemoteDeviceServicer(grpc_pb2_grpc.RemoteDeviceServicer):
    def __init__(self, device):
        super().__init__()
        self.device = device

    def SendMessage(self, request, context):
        logging.info("Device %s recebeu uma mensagem", self.device.get_short_id())
        if request.name == "TURN_ON":
            logging.info("Ligando a lâmpada de id %s", self.device.get_short_id())
            self.device.powered_on = True
        elif request.name == "TURN_OFF":
            logging.info("Desligando a lâmpada de id %s", self.device.get_short_id())
            self.device.powered_on = False
        elif request.name == "CHANGE_COLOR":
            if len(request.params) >= 3:
                logging.info("Mudando a cor da lâmpada de id %s para [%d, %d, %d]",
                             self.device.get_short_id(),
                             request.params[0], request.params[1], request.params[2])
                self.device.color = list(request.params)
            else:
                logging.warning("Parâmetros insuficientes para CHANGE_COLOR")
        elif request.name == "CHANGE_INTENSITY":
            if request.params:
                logging.info("Mudando a intensidade da lâmpada de id %s para %d",
                             self.device.get_short_id(), request.params[0])
                self.device.intensity = request.params[0]
            else:
                logging.warning("Parâmetro ausente para CHANGE_INTENSITY")
        else:
            logging.warning("Comando desconhecido: %s", request.name)

        self.device.send_status_once()

        response = grpc_pb2.MessageResponse(success=True, message="Mensagem recebida com sucesso")
        return response

class Lamp:
    def __init__(self, name="Lampada", broker_ip="localhost", broker_port=9092,
                 grpc_listen_port=50000, host="localhost"):
        self.run_event = Event()     
        self.run_event.set()         
        self.server = None
        self.name = name
        self.type = "LAMP"
        self.powered_on = True
        self.color = [255, 122, 177]
        self.intensity = 50
        self.host = host
        self.grpc_listen_port = grpc_listen_port
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.device_id = str(uuid.uuid4())

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=f"{self.broker_ip}:{self.broker_port}",
                value_serializer=lambda x: json.dumps(x).encode(),
            )
            logging.info("Kafka Producer criado com sucesso.")
        except Exception as e:
            logging.error("Erro ao criar Kafka Producer: %s", e)
            raise e

    def get_short_id(self):
        return self.device_id[:8]

    def send_status(self):
        try:
            while self.run_event.is_set():
                color_to_send = list(self.color) if hasattr(self.color, '__iter__') else self.color
                self.producer.send(
                    "device_message",
                    {
                        "device_id": self.device_id,
                        "name": self.name,
                        "device_type": self.type,
                        "message_type": "STATUS_REPORT",
                        "status": {
                            "powered_on": self.powered_on,
                            "color": color_to_send,
                            "intensity": self.intensity,
                        },
                        "device_ip": self.host,
                        "device_port": self.grpc_listen_port,
                    },
                )
                sleep(1)
        except Exception as e:
            logging.error("Erro ao enviar status: %s", e)

    def send_status_once(self):
        try:
            color_to_send = list(self.color) if hasattr(self.color, '__iter__') else self.color
            self.producer.send(
                "device_message",
                {
                    "device_id": self.device_id,
                    "name": self.name,
                    "device_type": self.type,
                    "message_type": "STATUS_REPORT",
                    "status": {
                        "powered_on": self.powered_on,
                        "color": color_to_send,
                        "intensity": self.intensity,
                    },
                    "device_ip": self.host,
                    "device_port": self.grpc_listen_port,
                },
            )
        except Exception as e:
            logging.error("Erro ao enviar status único: %s", e)

    def send_liveness_probe(self):
        try:
            while self.run_event.is_set():
                self.producer.send(
                    "liveness_probe",
                    {"device_id": self.device_id},
                )
                sleep(4)
        except Exception as e:
            logging.error("Erro ao enviar liveness probe: %s", e)

    def listen_messages(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        grpc_pb2_grpc.add_RemoteDeviceServicer_to_server(RemoteDeviceServicer(self), self.server)

        logging.info("Servidor gRPC ouvindo na porta %s...", self.grpc_listen_port)
        self.server.add_insecure_port(f"[::]:{self.grpc_listen_port}")
        self.server.start()

    def start(self):
        threads = []
        t_status = Thread(target=self.send_status)
        threads.append(t_status)
        t_status.start()

        t_probe = Thread(target=self.send_liveness_probe)
        threads.append(t_probe)
        t_probe.start()

        t_grpc = Thread(target=self.listen_messages)
        threads.append(t_grpc)
        t_grpc.start()

        input("Pressione Enter para encerrar o dispositivo!\n")
        logging.info("Encerrando o dispositivo...")
        self.run_event.clear() 

        if self.server:
            self.server.stop(0)

        for t in threads:
            t.join()
        logging.info("Dispositivo encerrado com sucesso.")

if __name__ == "__main__":
    name = input("Digite o nome do dispositivo (Ex: Lampada da Sala): ") or "Lampada"
    try:
        grpc_listen_port = int(input("Digite a porta que o gRPC vai escutar (50000-60000): "))
    except Exception:
        grpc_listen_port = 50000

    lamp = Lamp(name=name, grpc_listen_port=grpc_listen_port)
    lamp.start()
