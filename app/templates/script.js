const deviceIcons = {
    "default": "https://img.icons8.com/fluency/48/000000/desktop.png",
    "LAMP": "https://img.icons8.com/fluency/48/000000/light-on.png",
    "RADIO": "https://img.icons8.com/fluency/48/000000/radio.png",
    "AIR_CONDITIONING": "https://img.icons8.com/fluency/48/000000/air-conditioner.png"
};

async function loadDevices() {
    try {
        const response = await fetch("/device");
        const devices = await response.json();
        const container = document.getElementById("deviceContainer");

        container.innerHTML = "";

        devices.forEach(device => {
            const card = document.createElement("div");
            card.className = "device-card";
            card.setAttribute("data-device-id", device.device_id);

            const iconUrl = deviceIcons[device.device_type] || deviceIcons["default"];
            const iconElem = document.createElement("div");
            iconElem.className = "device-icon";
            iconElem.innerHTML = `<img src="${iconUrl}" alt="${device.device_type}">`;

            const header = document.createElement("div");
            header.className = "device-header";

            const nameElem = document.createElement("div");
            nameElem.className = "device-name";
            nameElem.innerText = device.name;

            const specificInfo = document.createElement("div");
            specificInfo.className = "device-specific-info";

            if (device.device_type === "LAMP") {
                const color = `#${device.status.color.map(c => c.toString(16).padStart(2, '0')).join('')}`;
                specificInfo.innerHTML = `<p><strong>Cor:</strong> <span class="color-box" style="background-color: ${color};"></span></p>`;

            } else if (device.device_type === "AIR_CONDITIONING") {
                specificInfo.innerHTML = `<p><strong>Temperatura:</strong> ${device.status.temperature}°C</p>`;

            } else if (device.device_type === "RADIO") {
                specificInfo.innerHTML = `<p><strong>Música:</strong> ${device.status.playing_music}</p>`;
            }

            const statusElem = document.createElement("div");
            statusElem.className = "device-status " + (device.status.powered_on ? "on" : "off");
            statusElem.innerText = device.status.powered_on ? "On" : "Off";

            header.appendChild(nameElem);
            header.appendChild(specificInfo);
            header.appendChild(statusElem);

            const infoContainer = document.createElement("div");
            infoContainer.className = "device-info-container";
            infoContainer.appendChild(header);

            const details = document.createElement("div");
            details.className = "device-details";
            details.innerHTML = `
                <div class="details-row">
                    <div class="details-left">
                    <p><strong>Tipo:</strong> ${device.device_type}</p>
                    <p><strong>Último Sinal:</strong> ${new Date(device.last_liveness_probe).toLocaleString()}</p>
                    </div>
                    <div class="details-right">
                    <button class="action-btn" onclick="openActionModal(event, '${encodeURIComponent(JSON.stringify(device))}')">Editar</button>
                    </div>
                </div>
                `;

            infoContainer.appendChild(details);

            card.appendChild(iconElem);
            card.appendChild(infoContainer);

            card.addEventListener("click", function (e) {
                if (!e.target.classList.contains("action-btn")) {
                    toggleCard(card);
                }
            });

            container.appendChild(card);
        });
    } catch (error) {
        console.error("Erro ao carregar dispositivos:", error);
    }
}

function toggleCard(card) {
    document.querySelectorAll(".device-card").forEach(c => {
        if (c !== card) {
            c.classList.remove("open");
        }
    });
    card.classList.toggle("open");
}

function openActionModal(event, deviceDataEncoded) {
    event.stopPropagation();
    const device = JSON.parse(decodeURIComponent(deviceDataEncoded));
    document.getElementById("modalDeviceName").innerText = device.name;
    const modalActions = document.getElementById("modalActions");

    let content = `<div class="modal-section">
                    <button class="action-btn" onclick="toggleDevice('${device.device_id}')">
                      ${device.status.powered_on ? "Desligar" : "Ligar"}
                    </button>
                 </div>`;

    if (device.device_type === "LAMP") {
        const currentColor = `#${device.status.color.map(c => c.toString(16).padStart(2, '0')).join('')}`;
        content += `<div class="modal-section">
                      <label for="colorPicker">Mudar Cor:</label>
                      <input type="color" id="colorPicker" value="${currentColor}">
                      <button class="action-btn" onclick="confirmChangeColor('${device.device_id}')">Confirmar</button>
                    </div>`;
    } else if (device.device_type === "AIR_CONDITIONING") {
        content += `<div class="modal-section">
                      <label for="tempInput">Mudar Temperatura:</label>
                      <input type="number" id="tempInput" value="${device.status.temperature || 22}" min="16" max="30">
                      <button class="action-btn" onclick="confirmChangeTemperature('${device.device_id}')">Confirmar</button>
                    </div>`;
    }

    modalActions.innerHTML = content;
    document.getElementById("actionModal").style.display = "block";
}

function closeModal() {
    document.getElementById("actionModal").style.display = "none";
}

async function sendCommand(deviceId, command, params = []) {
    try {
        const response = await fetch("/control_device", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                device_id: deviceId,
                name: command,
                params: params,
            }),
        });

        if (!response.ok) {
            throw new Error("Erro ao enviar comando");
        }

        const result = await response.json();
        console.log("Comando enviado com sucesso:", result);
        loadDevices(); // Recarrega a lista de dispositivos após a alteração
    } catch (error) {
        console.error("Erro ao enviar comando:", error);
    }
}

function confirmChangeColor(deviceId) {
    const colorPicker = document.getElementById("colorPicker");
    const color = colorPicker.value;
    const rgb = hexToRgb(color);
    sendCommand(deviceId, "CHANGE_COLOR", [rgb.r, rgb.g, rgb.b]);
    closeModal();
}

function confirmChangeTemperature(deviceId) {
    const tempInput = document.getElementById("tempInput");
    const temperature = parseInt(tempInput.value);
    sendCommand(deviceId, "SET_TEMPERATURE", [temperature]);
    closeModal();
}

function toggleDevice(deviceId) {
    sendCommand(deviceId, "TOGGLE_POWER");
    closeModal();
}

function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

function sortDevices() {
    const sortBy = document.getElementById("sortFilter").value;
    const container = document.getElementById("deviceContainer");
    const cards = Array.from(container.getElementsByClassName("device-card"));

    cards.sort((a, b) => {
        const aValue = a.querySelector(`.device-${sortBy}`).innerText.toLowerCase();
        const bValue = b.querySelector(`.device-${sortBy}`).innerText.toLowerCase();
        return aValue.localeCompare(bValue);
    });

    container.innerHTML = "";
    cards.forEach(card => container.appendChild(card));
}

function showDevices() {
    document.getElementById("deviceContainer").style.display = "block";
    document.getElementById("readmeContainer").style.display = "none";
    document.querySelector(".sidebar-list-item.active").classList.remove("active");
    document.querySelector(".sidebar-list-item:nth-child(2)").classList.add("active");
}

function showReadme() {
    document.getElementById("deviceContainer").style.display = "none";
    document.getElementById("readmeContainer").style.display = "block";
    document.querySelector(".sidebar-list-item.active").classList.remove("active");
    document.querySelector(".sidebar-list-item:nth-child(1)").classList.add("active");
}

document.querySelector(".sidebar-list-item:nth-child(1) a").addEventListener("click", showReadme);
document.querySelector(".sidebar-list-item:nth-child(2) a").addEventListener("click", showDevices);

loadDevices();
setInterval(loadDevices, 60000);