function initializeDetectorControls() {
    const detectorToggleBtn = document.getElementById('detectorToggle');
    if (detectorToggleBtn) {
        detectorToggleBtn.addEventListener('click', toggleDetector);
    }
    fetchDetectorStatus(); // Consultar estado inicial
}

async function fetchDetectorStatus() {
    try {
        const res = await fetch('/api/detector/status');
        const payload = res.ok ? await res.json() : { running: false };
        updateDetectorUI(Boolean(payload.running));
    } catch (e) {
        console.error('Error comprobando estado del detector', e);
        updateDetectorUI(false);
    }
}

async function toggleDetector() {
    const btn = document.getElementById('detectorToggle');
    const isRunning = btn.dataset.running === 'true';
    const endpoint = isRunning ? '/api/detector/stop' : '/api/detector/start';
    
    try {
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
        btn.dataset.running = running;
        btn.textContent = running ? 'Detener detector' : 'Activar detector';
        btn.classList.toggle('bg-red-600', running);
        btn.classList.toggle('bg-indigo-600', !running);
    }
    if (overlay) overlay.classList.toggle('hidden', running);
    if (status) status.textContent = running ? 'Estado: activo' : 'Estado: detenido';
}