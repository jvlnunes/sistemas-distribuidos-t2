from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json
import redis
import logging
import grpc
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from proto import grpc_pb2, grpc_pb2_grpc

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Inicializa o FastAPI
app = FastAPI()

# Conectando ao Redis
r = redis.Redis(host="localhost", port=6379, db=0)

# Configurar templates para HTML
templates = Jinja2Templates(directory="templates")

# Modelos Pydantic
class DeviceMessage(BaseModel):
    name: str
    device_id: str
    device_type: str
    message_type: str
    status: dict
    device_ip: str
    device_port: int

class LivenessProbe(BaseModel):
    device_id: str

class ControlDeviceMessage(BaseModel):
    name: str
    device_id: str
    params: list[int] = Field(default=[])

# Servindo a interface gráfica
@app.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/device")
def get_devices():
    """
    Retorna a lista dos dispositivos registrados com todas as informações relevantes.
    """
    devices = []
    for key in r.keys():
        device_data = json.loads(r.get(key))

        devices.append({
            "device_id"  : key.decode(),
            "name"       : device_data.get("name"       , "Unknown Device"),
            "status"     : device_data.get("status"     ,              {} ),
            "device_ip"  : device_data.get("device_ip"  ,       "Unknown" ),
            "device_type": device_data.get("device_type",       "Unknown" ),
            "device_port": device_data.get("device_port",               0 ),
            "last_liveness_probe": device_data.get("last_liveness_probe", "N/A")
        })

    return devices

@app.post("/device_message")
def handle_device_message(message: DeviceMessage):
    """
    Recebe uma mensagem de status de um dispositivo e atualiza o estado no Redis.
    """
    logging.info("Dispositivo de id %s mandou uma mensagem", message.device_id)
    device_data = message.dict()
    device_data["last_liveness_probe"] = datetime.now().isoformat()  # Atualiza timestamp
    r.set(message.device_id, json.dumps(device_data))
    return {"message": "ok"}

@app.post("/check_liveness_probe")
def check_liveness_probe():
    """
    Verifica se algum dispositivo não enviou um liveness probe nos últimos 6 segundos e o remove.
    """
    now = datetime.now()
    for key in r.keys():
        device_data = json.loads(r.get(key))
        last_probe = datetime.fromisoformat(device_data["last_liveness_probe"])
        if last_probe < (now - timedelta(seconds=6)):
            logging.info("Dispositivo de id %s inativo. Removendo...", key.decode())
            r.delete(key)
    return {"message": "Liveness probe check complete."}

@app.post("/update_liveness_probe")
def update_liveness_probe(liveness_probe: LivenessProbe):
    """
    Atualiza o timestamp do último liveness probe para o dispositivo.
    """
    device_id = liveness_probe.device_id
    if r.exists(device_id):
        device_data = json.loads(r.get(device_id))
        device_data["last_liveness_probe"] = datetime.now().isoformat()
        r.set(device_id, json.dumps(device_data))
    return {"message": "ok"}

@app.post("/control_device")
def control_device(config: ControlDeviceMessage):
    """
    Envia um comando ao dispositivo via gRPC e atualiza o estado local no Redis.
    """
    if not r.exists(config.device_id):
        raise HTTPException(404, {"message": "Dispositivo não existe!"})
    device = json.loads(r.get(config.device_id))

    channel = grpc.insecure_channel(f"{device['device_ip']}:{device['device_port']}")
    stub = grpc_pb2_grpc.RemoteDeviceStub(channel)
    grpc_message = grpc_pb2.Message(name=config.name, params=config.params)

    try:
        stub.SendMessage(grpc_message)
        logging.info("Comando %s enviado para o dispositivo %s", config.name, config.device_id)
    except Exception as e:
        logging.error("Erro ao enviar comando via gRPC: %s", e)
        raise HTTPException(500, {"message": "Erro ao enviar comando."})

    # Atualiza o estado do dispositivo com base no comando enviado
    if config.name == "CHANGE_COLOR":
        device['status']['color'] = config.params
    elif config.name == "TURN_ON":
        device['status']['powered_on'] = True
    elif config.name == "TURN_OFF":
        device['status']['powered_on'] = False

    # Salva a atualização no Redis
    r.set(config.device_id, json.dumps(device))
    return {"message": "ok"}
