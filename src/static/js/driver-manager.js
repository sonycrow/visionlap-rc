let addDriverModal, driverForm;
let driversPage = 1;
let driversPerPage = 8;
let driversTotalPages = 1;
let driversQuery = '';

function initializeDriverManager() {
    addDriverModal = document.getElementById('addDriverModal');
    driverForm = document.getElementById('driverForm');
    
    const addDriverBtn = document.getElementById('addDriverBtn');
    const cancelDriverBtn = document.getElementById('cancelDriver');
    const driversSearch = document.getElementById('driversSearch');
    const driversReload = document.getElementById('driversReload');
    const driversPrev = document.getElementById('driversPrev');
    const driversNext = document.getElementById('driversNext');

    addDriverBtn.addEventListener('click', () => openDriverModal());
    cancelDriverBtn.addEventListener('click', closeDriverModal);
    driverForm.addEventListener('submit', handleDriverSave);

    driversReload.onclick = () => { driversQuery = driversSearch.value.trim(); fetchDrivers(1, driversQuery); };
    driversPrev.onclick = () => { if (driversPage > 1) fetchDrivers(driversPage - 1, driversQuery); };
    driversNext.onclick = () => { if (driversPage < driversTotalPages) fetchDrivers(driversPage + 1, driversQuery); };

    fetchDrivers(); // Carga inicial
}

function openDriverModal(driver = null) {
    const modalTitle = document.getElementById('driverModalTitle');
    const submitButton = driverForm.querySelector('button[type="submit"]');
    driverForm.reset();

    if (driver) {
        modalTitle.textContent = 'Editar Piloto';
        submitButton.textContent = 'Guardar Cambios';
        document.getElementById('dId').value = driver.id;
        document.getElementById('dName').value = driver.name;
        document.getElementById('dNick').value = driver.nickname;
        document.getElementById('dTag').value = driver.tag_id;
    } else {
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
            closeDriverModal();
            await fetchDrivers(driversPage, driversQuery);
        } else {
            const err = await res.json();
            alert('Error: ' + (err.error || 'Ocurrió un error desconocido.'));
        }
    } catch (e) {
        console.error('Error guardando piloto:', e);
        alert('Error de conexión al guardar el piloto.');
    }
}

async function fetchDrivers(page = 1, q = '') {
    try {
        const params = new URLSearchParams({ page, per_page: driversPerPage });
        if (q) params.set('q', q);
        const res = await fetch('/api/drivers?' + params.toString());
        if (!res.ok) return;
        const payload = await res.json();
        driversPage = payload.page;
        driversTotalPages = payload.pages;
        renderDrivers(payload.items || []);
        renderDriversPager();
    } catch (err) {
        console.error('Error cargando pilotos:', err);
    }
}

function renderDrivers(drivers) {
    const list = document.getElementById('driversList');
    list.innerHTML = drivers.map(d => `
        <li class="px-3 py-2 bg-gray-700 rounded flex justify-between items-center" data-driver-id="${d.id}">
            <div>
                <div class="font-medium">${escapeHtml(d.name)} <span class="text-sm text-gray-400">(${escapeHtml(d.nickname)})</span></div>
                <div class="text-xs text-gray-400">Tag: ${d.tag_id}</div>
            </div>
            <div class="flex gap-2">
                <button class="edit-btn px-2 py-1 bg-yellow-500 hover:bg-yellow-600 rounded text-xs">Editar</button>
                <button class="delete-btn px-2 py-1 bg-red-600 hover:bg-red-700 rounded text-xs">Borrar</button>
            </div>
        </li>`).join('');
    
    // Add event listeners after rendering
    list.querySelectorAll('.edit-btn').forEach((btn, i) => btn.onclick = () => openDriverModal(drivers[i]));
    list.querySelectorAll('.delete-btn').forEach((btn, i) => btn.onclick = () => deleteDriverConfirm(drivers[i]));
}

function renderDriversPager() {
    document.getElementById('driversPagerInfo').textContent = `Página ${driversPage} / ${driversTotalPages}`;
    document.getElementById('driversPrev').disabled = driversPage <= 1;
    document.getElementById('driversNext').disabled = driversPage >= driversTotalPages;
}

async function deleteDriverConfirm(driver) {
    if (!confirm(`¿Borrar piloto ${driver.name}?`)) return;
    const res = await fetch(`/api/drivers/${driver.id}`, { method: 'DELETE' });
    if (res.ok) await fetchDrivers(driversPage, driversQuery);
    else alert('Error al borrar el piloto.');
}

function escapeHtml(unsafe) {
    return String(unsafe).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}