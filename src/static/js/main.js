const socket = io();
let driversData = {}; // Cache local de tiempos

// Escuchar actualizaciones de vuelta
socket.on('lap_update', function(data) {
    console.log("Vuelta recibida:", data);
    
    // Actualizar datos locales
    if (!driversData[data.tag_id]) {
        driversData[data.tag_id] = {
            name: data.nickname,
            laps: 0,
            last: 0,
            best: 9999.0
        };
    }
    
    let d = driversData[data.tag_id];
    d.laps = data.lap_number;
    d.last = data.lap_time;
    if (data.lap_time < d.best) d.best = data.lap_time;
    
    renderLeaderboard();
});

function renderLeaderboard() {
    const tbody = document.getElementById('leaderboardBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    // Convertir objeto a array y ordenar
    let sortedDrivers = Object.values(driversData).sort((a, b) => {
        // Lógica simple: más vueltas ganan, luego menor tiempo
        return b.laps - a.laps; 
    });

    if (sortedDrivers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-gray-500">No hay registros para mostrar</td></tr>`;
        return;
    }

    sortedDrivers.forEach((d, index) => {
        let row = `<tr class="bg-gray-800 hover:bg-gray-700">
            <td class="px-4 py-2">${index + 1}</td>
            <td class="px-4 py-2">${d.name}</td>
            <td class="px-4 py-2">${d.laps}</td>
            <td class="px-4 py-2 lap-time-display">${d.last.toFixed(3)}</td>
            <td class="px-4 py-2 text-green-400">${d.best.toFixed(3)}</td>
            <td class="px-4 py-2">-</td>
        </tr>`;
        tbody.innerHTML += row;
    });
}

// Gestión del formulario de pilotos

// La lógica del formulario se activa ahora desde un modal



// Elementos de UI para la carrera

let raceStatusBlock;

let semaphoreOverlay, semaphoreLights, semaphoreTimer;

let settingsModal, settingsForm, prepTimeInput, maxTimeInput, maxLapsInput;

let addDriverModal, driverForm;



// Configuración de la carrera (con valores por defecto)

let prepTime = 60;

let maxTime = 5; // en minutos

let maxLaps = 10;



// Estado de la carrera

const RACE_STATE = {

    IDLE: 'idle',

    PREPARING: 'preparing',

    STARTING: 'starting',

    RUNNING: 'running',

    FINISHED: 'finished'

};

let currentRaceState = RACE_STATE.IDLE;

let gridCountdownInterval, semaphoreCountdownInterval, raceTimerInterval;



document.addEventListener('DOMContentLoaded', () => {
    // Elementos de carrera
    raceStatusBlock = document.getElementById('raceStatusBlock');
    semaphoreOverlay = document.getElementById('semaphoreOverlay');
    semaphoreLights = document.getElementById('semaphoreLights').children;
    semaphoreTimer = document.getElementById('semaphoreTimer');

    // Elementos del modal de opciones
    settingsModal = document.getElementById('settingsModal');
    settingsForm = document.getElementById('settingsForm');
    prepTimeInput = document.getElementById('prepTime');
    maxTimeInput = document.getElementById('maxTime');
    maxLapsInput = document.getElementById('maxLaps');

    const settingsBtn = document.getElementById('settingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettings');

    settingsBtn.addEventListener('click', openSettingsModal);
    cancelSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsForm.addEventListener('submit', handleSettingsSave);

    // Elementos del modal de piloto
    addDriverModal = document.getElementById('addDriverModal');
    driverForm = document.getElementById('driverForm');
    const addDriverBtn = document.getElementById('addDriverBtn');
    const cancelDriverBtn = document.getElementById('cancelDriver');

    addDriverBtn.addEventListener('click', () => openDriverModal()); // Abrir en modo creación
    cancelDriverBtn.addEventListener('click', closeDriverModal);
    driverForm.addEventListener('submit', handleDriverSave);
});

function openSettingsModal() {
    if (currentRaceState !== RACE_STATE.IDLE) {
        console.log("No se pueden cambiar las opciones mientras una carrera está en curso.");
        return;
    }
    prepTimeInput.value = prepTime;
    maxTimeInput.value = maxTime;
    maxLapsInput.value = maxLaps;
    settingsModal.classList.remove('hidden');
}

function closeSettingsModal() {
    settingsModal.classList.add('hidden');
}

function handleSettingsSave(e) {
    e.preventDefault();
    prepTime = parseInt(prepTimeInput.value, 10) || 60;
    maxTime = parseInt(maxTimeInput.value, 10) || 5;
    maxLaps = parseInt(maxLapsInput.value, 10) || 10;
    console.log("Opciones guardadas:", { prepTime, maxTime, maxLaps });
    closeSettingsModal();
}

function openDriverModal(driver = null) {
    const modalTitle = document.getElementById('driverModalTitle');
    const submitButton = driverForm.querySelector('button[type="submit"]');

    driverForm.reset(); // Limpiar el formulario

    if (driver) {
        // Modo Edición
        modalTitle.textContent = 'Editar Piloto';
        submitButton.textContent = 'Guardar Cambios';
        document.getElementById('dId').value = driver.id;
        document.getElementById('dName').value = driver.name;
        document.getElementById('dNick').value = driver.nickname;
        document.getElementById('dTag').value = driver.tag_id;
    } else {
        // Modo Creación
        modalTitle.textContent = 'Registrar Nuevo Piloto';
        submitButton.textContent = 'Registrar Piloto';
        document.getElementById('dId').value = '';
    }
    addDriverModal.classList.remove('hidden');
}

function closeDriverModal() {
    addDriverModal.classList.add('hidden');
}

async function handleDriverSave(e) {
    e.preventDefault();
    const driverId = document.getElementById('dId').value;
    const data = {
        name: document.getElementById('dName').value,
        nickname: document.getElementById('dNick').value,
        tag_id: parseInt(document.getElementById('dTag').value)
    };

    // Simple validation
    if (!data.name || !data.nickname || isNaN(data.tag_id)) {
        alert("Por favor, completa todos los campos correctamente.");
        return;
    }

    const isEdit = Boolean(driverId);
    const url = isEdit ? `/api/drivers/${driverId}` : '/api/drivers';
    const method = isEdit ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        if (res.ok) {
            console.log(isEdit ? 'Piloto actualizado' : 'Piloto registrado');
            closeDriverModal();
            await fetchDrivers(driversPage, driversQuery); // Recargar la página actual de pilotos
        } else {
            const err = await res.json();
            console.log('Error: ' + (err.error || 'Ocurrió un error desconocido.'));
        }
    } catch (e) {
        console.error('Error guardando piloto:', e);
        console.log('Error de conexión al guardar el piloto.');
    }
}

function updateRaceStatus(message) {
    raceStatusBlock.innerHTML = message;
}

function stopSession() {
    // Detener todos los intervalos
    clearInterval(gridCountdownInterval);
    clearInterval(semaphoreCountdownInterval);
    clearInterval(raceTimerInterval);

    // Ocultar semáforo
    semaphoreOverlay.classList.add('hidden');
    semaphoreOverlay.classList.remove('flex');
    
    // Resetear estado
    currentRaceState = RACE_STATE.IDLE;
    driversData = {};
    renderLeaderboard();
    updateRaceStatus('<p class="text-gray-300">Carrera detenida. Haz clic en "Iniciar carrera" para empezar de nuevo.</p>');
    
    // Aquí también se podría llamar a una API para detener la sesión en el backend
    fetch('/api/session/stop', {method: 'POST'});
    console.log("Sesión detenida por el usuario.");
}

async function startSession() {
    if (currentRaceState !== RACE_STATE.IDLE) {
        console.log("La carrera ya está en progreso o iniciándose.");
        return;
    }
    
    console.log("Iniciando secuencia de carrera...");
    currentRaceState = RACE_STATE.PREPARING;
    
    let gridTime = prepTime;
    updateRaceStatus(`
        <h4 class="text-xl font-bold text-yellow-400 mb-2">¡Prepara la parrilla de salida!</h4>
        <p class="text-gray-200">Tiempo restante: <span class="font-mono text-2xl">${gridTime}</span>s</p>
    `);
    
    gridCountdownInterval = setInterval(() => {
        gridTime--;
        updateRaceStatus(`
            <h4 class="text-xl font-bold text-yellow-400 mb-2">¡Prepara la parrilla de salida!</h4>
            <p class="text-gray-200">Tiempo restante: <span class="font-mono text-2xl">${gridTime}</span>s</p>
        `);
        if (gridTime <= 0) {
            clearInterval(gridCountdownInterval);
            startSemaphoreCountdown();
        }
    }, 1000);
}

function startSemaphoreCountdown() {
    console.log("Iniciando cuenta atrás del semáforo...");
    currentRaceState = RACE_STATE.STARTING;
    
    semaphoreOverlay.classList.remove('hidden');
    semaphoreOverlay.classList.add('flex');

    let semaphoreTime = 10;
    
    const updateLights = (count) => {
        for (let i = 0; i < semaphoreLights.length; i++) {
            if (i < count) {
                semaphoreLights[i].classList.add('red');
            } else {
                semaphoreLights[i].classList.remove('red');
            }
        }
    };
    
    // Resetear luces
    for(const light of semaphoreLights) {
        light.classList.remove('red', 'green');
    }
    
    semaphoreCountdownInterval = setInterval(() => {
        semaphoreTimer.textContent = semaphoreTime;
        
        if (semaphoreTime <= 5 && semaphoreTime > 0) {
            // Encender una luz roja por segundo
            updateLights(6 - semaphoreTime);
        }

        if (semaphoreTime === 0) {
            clearInterval(semaphoreCountdownInterval);
            console.log("¡Carrera iniciada!");

            // Apagar luces rojas y encender verdes
            for(const light of semaphoreLights) {
                light.classList.remove('red');
                light.classList.add('green');
            }
            
            // Ocultar semáforo y empezar carrera tras un breve instante
            setTimeout(() => {
                semaphoreOverlay.classList.add('hidden');
                semaphoreOverlay.classList.remove('flex');
                startRace();
            }, 1000); // Muestra las luces verdes por 1 segundo
        }
        
        semaphoreTime--;
        
    }, 1000);
}

async function startRace() {
    await fetch('/api/session/start', {method: 'POST'});
    currentRaceState = RACE_STATE.RUNNING;
    console.log("La carrera está en marcha.");
    
    let raceTime = maxTime * 60; // Convertir minutos a segundos
    
    const formatTime = (seconds) => {
        const min = Math.floor(seconds / 60);
        const sec = seconds % 60;
        return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    };

    updateRaceStatus(`
        <div class="flex justify-around items-center">
            <div>
                <h5 class="text-sm uppercase text-gray-400">Tiempo de Carrera</h5>
                <p class="font-mono text-3xl text-green-400">${formatTime(raceTime)}</p>
            </div>
            <div>
                <h5 class="text-sm uppercase text-gray-400">Vueltas Máximas</h5>
                <p class="font-mono text-3xl">${maxLaps}</p>
            </div>
        </div>
    `);

    raceTimerInterval = setInterval(() => {
        raceTime--;
        // Actualizar solo el tiempo para evitar redibujar todo el bloque
        const timeElement = raceStatusBlock.querySelector('.text-green-400');
        if (timeElement) timeElement.textContent = formatTime(raceTime);

        if (raceTime <= 0) {
            clearInterval(raceTimerInterval);
            currentRaceState = RACE_STATE.FINISHED;
            console.log("La carrera ha terminado (tiempo agotado).");
            updateRaceStatus('<h4 class="text-xl font-bold text-red-500">¡CARRERA FINALIZADA!</h4>');
            stopSession();
        }
    }, 1000);
}


// Obtener y renderizar pilotos registrados
// Paginación y búsqueda
let driversPage = 1;
let driversPerPage = 8;
let driversTotalPages = 1;
let driversQuery = '';

async function fetchDrivers(page = 1, q = '') {
    try {
        const params = new URLSearchParams({ page: page, per_page: driversPerPage });
        if (q) params.set('q', q);
        const res = await fetch('/api/drivers?' + params.toString());
        if (!res.ok) return;
        const payload = await res.json();
        driversPage = payload.page || 1;
        driversPerPage = payload.per_page || driversPerPage;
        driversTotalPages = payload.pages || 1;
        renderDrivers(payload.items || []);
        renderDriversPager();
    } catch (err) {
        console.error('Error cargando pilotos:', err);
    }
}

function renderDrivers(drivers) {
    const list = document.getElementById('driversList');
    if (!list) return;
    list.innerHTML = '';
    drivers.forEach(d => {
        const li = document.createElement('li');
        li.className = 'px-3 py-2 bg-gray-700 rounded flex justify-between items-center';
        li.innerHTML = `<div><div class="font-medium">${escapeHtml(d.name)} <span class="text-sm text-gray-400">(${escapeHtml(d.nickname)})</span></div><div class="text-xs text-gray-400">Tag: ${d.tag_id}</div></div>`;
        // acciones: editar, borrar
        const actions = document.createElement('div');
        actions.className = 'flex gap-2';
        const editBtn = document.createElement('button');
        editBtn.className = 'px-2 py-1 bg-yellow-500 hover:bg-yellow-600 rounded text-xs';
        editBtn.textContent = 'Editar';
        editBtn.onclick = () => openDriverModal(d); // <- Cambio aquí
        const delBtn = document.createElement('button');
        delBtn.className = 'px-2 py-1 bg-red-600 hover:bg-red-700 rounded text-xs';
        delBtn.textContent = 'Borrar';
        delBtn.onclick = () => deleteDriverConfirm(d);
        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
        li.appendChild(actions);
        list.appendChild(li);
    });
}

function renderDriversPager() {
    const info = document.getElementById('driversPagerInfo');
    if (info) {
        info.textContent = `Página ${driversPage} / ${driversTotalPages} — Total páginas: ${driversTotalPages}`;
    }
    const prev = document.getElementById('driversPrev');
    const next = document.getElementById('driversNext');
    if (prev) prev.disabled = driversPage <= 1;
    if (next) next.disabled = driversPage >= driversTotalPages;
}

async function deleteDriverConfirm(driver) {
    //if (!confirm(`¿Borrar piloto ${driver.name} (${driver.nickname})?`)) return;
    try {
        const res = await fetch(`/api/drivers/${driver.id}`, { method: 'DELETE' });
        if (res.ok) {
            await fetchDrivers(driversPage, driversQuery);
        } else {
            const err = await res.json();
            console.log('Error: ' + (err.error || 'unknown'));
        }
    } catch (e) {
        console.error(e);
    }
}

// eventos de búsqueda y paginador
const driversSearch = document.getElementById('driversSearch');
const driversReload = document.getElementById('driversReload');
const driversPrev = document.getElementById('driversPrev');
const driversNext = document.getElementById('driversNext');
if (driversReload) driversReload.onclick = () => { driversQuery = driversSearch.value.trim(); fetchDrivers(1, driversQuery); };
if (driversPrev) driversPrev.onclick = () => { if (driversPage>1) fetchDrivers(driversPage-1, driversQuery); };
if (driversNext) driversNext.onclick = () => { if (driversPage<driversTotalPages) fetchDrivers(driversPage+1, driversQuery); };

// pequeña función para escapar texto insertado en HTML
function escapeHtml(unsafe) {
    return String(unsafe)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
}

// Cargar pilotos al iniciar la página
fetchDrivers();

// --- Control del detector (camara + reconocimiento)
async function fetchDetectorStatus() {
    try {
        const res = await fetch('/api/detector/status');
        if (!res.ok) return updateDetectorUI(false);
        const payload = await res.json();
        updateDetectorUI(Boolean(payload.running));
    } catch (e) {
        console.error('Error comprobando estado del detector', e);
        updateDetectorUI(false);
    }
}

async function toggleDetector() {
    const btn = document.getElementById('detectorToggle');
    if (!btn) return;
    const current = btn.dataset.running === 'true';
    try {
        const endpoint = current ? '/api/detector/stop' : '/api/detector/start';
        const res = await fetch(endpoint, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            console.log('Error: ' + (err.error || 'failed'));
            return;
        }
        const payload = await res.json();
        updateDetectorUI(Boolean(payload.running));
    } catch (e) {
        console.error('Error toggling detector', e);
    }
}

function updateDetectorUI(running) {
    const btn = document.getElementById('detectorToggle');
    const overlay = document.getElementById('detectorOverlay');
    const status = document.getElementById('detectorStatus');
    if (btn) {
        btn.dataset.running = running ? 'true' : 'false';
        if (running) {
            btn.textContent = 'Detener detector';
            btn.classList.remove('bg-indigo-600');
            btn.classList.add('bg-red-600');
        } else {
            btn.textContent = 'Activar detector';
            btn.classList.remove('bg-red-600');
            btn.classList.add('bg-indigo-600');
        }
    }
    if (overlay) {
        overlay.classList.toggle('hidden', running);
    }
    if (status) {
        status.textContent = running ? 'Estado: activo' : 'Estado: detenido';
    }
}

// Hook de botón
const detectorToggleBtn = document.getElementById('detectorToggle');
if (detectorToggleBtn) detectorToggleBtn.addEventListener('click', toggleDetector);

// Consultar estado inicial del detector
fetchDetectorStatus();

// Renderizar la tabla de posiciones al cargar
renderLeaderboard();
