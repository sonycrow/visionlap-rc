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
const driverForm = document.getElementById('driverForm');
if (driverForm) {
    driverForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            name: document.getElementById('dName').value,
            nickname: document.getElementById('dNick').value,
            tag_id: parseInt(document.getElementById('dTag').value)
        };
        
        await fetch('/api/drivers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        alert('Piloto registrado');
        driverForm.reset();
        // Refrescar lista de pilotos tras registrar uno nuevo
        await fetchDrivers();
    });
}

async function startSession() {
    await fetch('/api/session/start', {method: 'POST'});
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
        editBtn.onclick = () => editDriver(d);
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

// editar piloto (prompt simple)
async function editDriver(driver) {
    const name = prompt('Nombre:', driver.name);
    if (name === null) return;
    const nickname = prompt('Nickname:', driver.nickname);
    if (nickname === null) return;
    const tag = prompt('Tag ID:', driver.tag_id);
    if (tag === null) return;
    try {
        const res = await fetch(`/api/drivers/${driver.id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: name, nickname: nickname, tag_id: parseInt(tag) })
        });
        if (res.ok) {
            await fetchDrivers(driversPage, driversQuery);
            alert('Piloto actualizado');
        } else {
            const err = await res.json();
            alert('Error: ' + (err.error || 'unknown'));
        }
    } catch (e) {
        console.error(e);
    }
}

async function deleteDriverConfirm(driver) {
    if (!confirm(`¿Borrar piloto ${driver.name} (${driver.nickname})?`)) return;
    try {
        const res = await fetch(`/api/drivers/${driver.id}`, { method: 'DELETE' });
        if (res.ok) {
            await fetchDrivers(driversPage, driversQuery);
        } else {
            const err = await res.json();
            alert('Error: ' + (err.error || 'unknown'));
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
            alert('Error: ' + (err.error || 'failed'));
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
