from random import randbytes
from time import sleep, time
from kafka import KafkaProducer
from threading import Thread
from concurrent import futures
import grpc
from proto import grpc_pb2
from proto import grpc_pb2_grpc
import json

class RemoteDeviceServicer(grpc_pb2_grpc.RemoteDeviceServicer):
    def __init__(self, device):
        super()

        self.device = device

    def SendMessage(self, request, context):
        print("Device", self.device.get_short_id(), "Recebou uma mensagem")
        if request.name == "TURN_ON":
            print("Ligando o radio de id " + self.device.get_short_id())
            self.device.powered_on = True
        elif request.name == "TURN_OFF":
            print("Desligando o radio de id " + self.device.get_short_id())
            self.device.powered_on = False
        elif request.name == "CHANGE_MUSIC":
            print(
                "Mudando a musica do radio de id "
                + self.device.get_short_id()
                + " para "
                + self.request.params[0]
            )
            self.device.playing_music = self.request.params[0]

        response = grpc_pb2.MessageResponse(
            success=True,
            message="Mensagem recebida com sucesso",
        )

        return response

class Radio:
    def __init__(
        self,
        name="Radio",
        broker_ip="localhost",
        broker_port=9092,
        grpc_listen_port=50000,
        host="localhost",
    ):
        self.run = True
        self.server = None

        self.name = name
        self.type = "RADIO"

        self.powered_on = True
        self.playing_music = 0

        self.host = host
        self.grpc_listen_port = grpc_listen_port

        self.broker_ip = broker_ip
        self.broker_port = broker_port

        self.device_id = f"{int(time() * 1000)}-{randbytes(20).hex()}"

        self.producer = KafkaProducer(
            bootstrap_servers=f"{self.broker_ip}:{self.broker_port}",
            value_serializer=lambda x: json.dumps(x).encode(),
        )

    def get_short_id(self):
        return self.device_id[:8]

    def send_status(self):
        try:
            while self.run:
                if self.powered_on:
                    self.producer.send(
                        "device_message",
                        {
                            "device_id": self.device_id,
                            "name": self.name,
                            "device_type": self.type,
                            "message_type": "STATUS_REPORT",
                            "status": {
                                "powered_on": self.powered_on,
                                "playing_music": self.playing_music,
                            },
                            "device_ip": self.host,
                            "device_port": self.grpc_listen_port,
                        },
                    )
                sleep(1)
        except Exception as e:
            print(f"Erro ao enviar status: {e}")

    def send_liveness_probe(self):
        try:
            while self.run:
                self.producer.send(
                    "liveness_probe",
                    {"device_id": self.device_id},
                )
                sleep(4)
        except Exception as e:
            print(f"Erro ao enviar status: {e}")

    def listen_messages(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        grpc_pb2_grpc.add_RemoteDeviceServicer_to_server(
            RemoteDeviceServicer(self), self.server
        )

        # Escutando na porta 50051
        print(f"Servidor gRPC ouvindo na porta {self.grpc_listen_port}...")
        self.server.add_insecure_port(f"[::]:{self.grpc_listen_port}")
        self.server.start()

    def start(self):
        send_status_thread = Thread(target=self.send_status)
        send_status_thread.start()

        listen_messages = Thread(target=self.listen_messages)
        listen_messages.start()

        liveness_probe = Thread(target=self.send_liveness_probe)
        liveness_probe.start()

        input("Pressione Enter para encerrar o dispositivo!\n")
        print("Encerrando o dispositivo")
        self.run = False

        self.server.stop(0)
        listen_messages.join()
        send_status_thread.join()

name = input("Digite o nome do dispositivo: (Ex: Radio da Sala): ") or "Radio"

grpc_listen_port = 50000
try:
    grpc_listen_port = int(
        input(
            "Digite a porta que o grpc vai escutar (Geralmente um numero entre 50000 e 60000): "
        )
    )
except Exception:
    pass

Radio(name=name, grpc_listen_port=grpc_listen_port).start()
