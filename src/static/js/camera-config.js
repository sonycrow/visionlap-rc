// Módulo: configuración de cámara + autotune

function initializeCameraConfig() {
    const cameraBtn = document.getElementById('cameraConfigBtn');
    const cameraModal = document.getElementById('cameraConfigModal');
    const cancelCameraBtn = document.getElementById('cancelCameraConfig');
    const cameraForm = document.getElementById('cameraConfigForm');

    cameraBtn?.addEventListener('click', async () => {
        const res = await fetch('/api/camera-config');
        if (!res.ok) return alert('No se pudo obtener la configuración de la cámara');
        const cfg = await res.json();

        document.getElementById('CAMERA_IDX').value = cfg.CAMERA_IDX ?? '';
        const camRes = cfg.CAMERA_RESOLUTION ?? [];
        document.getElementById('CAMERA_WIDTH').value = camRes[0] ?? '';
        document.getElementById('CAMERA_HEIGHT').value = camRes[1] ?? '';
        document.getElementById('CAMERA_FPS').value = cfg.CAMERA_FPS ?? '';
        document.getElementById('CAMERA_AUTOFOCUS').value = (cfg.CAMERA_AUTOFOCUS !== null && cfg.CAMERA_AUTOFOCUS !== undefined) ? String(cfg.CAMERA_AUTOFOCUS) : '';
        if (cfg.CAMERA_FOCUS !== null) document.getElementById('CAMERA_FOCUS').value = cfg.CAMERA_FOCUS;
        document.getElementById('CAMERA_AUTO_EXPOSURE').value = (cfg.CAMERA_AUTO_EXPOSURE !== null && cfg.CAMERA_AUTO_EXPOSURE !== undefined) ? String(cfg.CAMERA_AUTO_EXPOSURE) : '';
        if (cfg.CAMERA_EXPOSURE !== null) document.getElementById('CAMERA_EXPOSURE').value = cfg.CAMERA_EXPOSURE;
        if (cfg.CAMERA_GAIN !== null) document.getElementById('CAMERA_GAIN').value = cfg.CAMERA_GAIN;
        if (cfg.CAMERA_BRIGHTNESS !== null) document.getElementById('CAMERA_BRIGHTNESS').value = cfg.CAMERA_BRIGHTNESS;
        if (cfg.CAMERA_CONTRAST !== null) document.getElementById('CAMERA_CONTRAST').value = cfg.CAMERA_CONTRAST;

        cameraModal.classList.remove('hidden');
    });

    cancelCameraBtn?.addEventListener('click', () => cameraModal.classList.add('hidden'));

    cameraForm?.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const payload = {};
        const getVal = (id) => document.getElementById(id).value;

        if (getVal('CAMERA_IDX') !== '') payload.CAMERA_IDX = parseInt(getVal('CAMERA_IDX'));
        if (getVal('CAMERA_WIDTH') !== '' && getVal('CAMERA_HEIGHT') !== '') payload.CAMERA_RESOLUTION = [parseInt(getVal('CAMERA_WIDTH')), parseInt(getVal('CAMERA_HEIGHT'))];
        if (getVal('CAMERA_FPS') !== '') payload.CAMERA_FPS = parseInt(getVal('CAMERA_FPS'));
        if (getVal('CAMERA_AUTOFOCUS') !== '') payload.CAMERA_AUTOFOCUS = parseInt(getVal('CAMERA_AUTOFOCUS'));
        if (getVal('CAMERA_FOCUS') !== '') payload.CAMERA_FOCUS = parseInt(getVal('CAMERA_FOCUS'));
        if (getVal('CAMERA_AUTO_EXPOSURE') !== '') payload.CAMERA_AUTO_EXPOSURE = parseInt(getVal('CAMERA_AUTO_EXPOSURE'));
        if (getVal('CAMERA_EXPOSURE') !== '') payload.CAMERA_EXPOSURE = parseInt(getVal('CAMERA_EXPOSURE'));
        if (getVal('CAMERA_GAIN') !== '') payload.CAMERA_GAIN = parseInt(getVal('CAMERA_GAIN'));
        if (getVal('CAMERA_BRIGHTNESS') !== '') payload.CAMERA_BRIGHTNESS = parseInt(getVal('CAMERA_BRIGHTNESS'));
        if (getVal('CAMERA_CONTRAST') !== '') payload.CAMERA_CONTRAST = parseInt(getVal('CAMERA_CONTRAST'));

        const resp = await fetch('/api/camera-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            cameraModal.classList.add('hidden');
            alert('Configuración guardada. El detector se reconfigurará si estaba activo.');
        } else {
            const data = await resp.json();
            alert('Error guardando configuración: ' + (data.error || resp.statusText));
        }
    });

    // Auto Tune Button
    const autoTuneBtn = document.getElementById('autoTuneBtn');
    autoTuneBtn?.addEventListener('click', async () => {
        if (!confirm('Iniciar Auto Tune de nitidez. Esto puede tardar unos segundos.')) return;

        autoTuneBtn.disabled = true;
        autoTuneBtn.textContent = 'Autotune...';

        try {
            const resp = await fetch('/api/camera-autotune', { method: 'POST' });
            const data = await resp.json();
            if (resp.ok && data.ok) {
                alert('Autotune completo: ' + JSON.stringify(data.result));
                if (data.result?.focus !== undefined) {
                    document.getElementById('CAMERA_FOCUS').value = data.result.focus;
                }
            } else {
                alert('Autotune falló: ' + (data.error || JSON.stringify(data)));
            }
        } catch (e) {
            alert('Error ejecutando autotune: ' + e);
        } finally {
            autoTuneBtn.disabled = false;
            autoTuneBtn.textContent = 'Auto Tune Nitidez';
        }
    });
}

// Exponer la función para que initializeModalHandlers() pueda llamarla
window.initializeCameraConfig = initializeCameraConfig;
