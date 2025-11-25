// Módulo: ajuste (tuning) del detector

function initializeDetectorConfig() {
    const detectorBtn = document.getElementById('detectorConfigBtn');
    const detectorModal = document.getElementById('detectorConfigModal');
    const cancelDetector = document.getElementById('cancelDetectorConfig');
    const detectorForm = document.getElementById('detectorConfigForm');

    detectorBtn?.addEventListener('click', async () => {
        const res = await fetch('/api/detector-config');
        if (!res.ok) return alert('No se pudo obtener configuración del detector');
        const cfg = await res.json();

        const setIfExists = (id, val) => { if (val !== undefined && val !== null) document.getElementById(id).value = val; };
        setIfExists('quad_decimate', cfg.quad_decimate);
        setIfExists('quad_sigma', cfg.quad_sigma);
        setIfExists('decode_sharpening', cfg.decode_sharpening);
        setIfExists('min_tag_area', cfg.min_tag_area);
        setIfExists('min_decision_margin', cfg.min_decision_margin);
        setIfExists('min_detection_frames', cfg.min_detection_frames);
        if (cfg.allow_quick_pass !== undefined && cfg.allow_quick_pass !== null) {
            document.getElementById('allow_quick_pass').value = cfg.allow_quick_pass ? 'true' : 'false';
        }
        setIfExists('quick_pass_time', cfg.quick_pass_time);

        detectorModal.classList.remove('hidden');
    });

    cancelDetector?.addEventListener('click', () => detectorModal.classList.add('hidden'));

    detectorForm?.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const payload = {};
        const getVal = id => document.getElementById(id).value;

        if (getVal('quad_decimate') !== '') payload.quad_decimate = parseFloat(getVal('quad_decimate'));
        if (getVal('quad_sigma') !== '') payload.quad_sigma = parseFloat(getVal('quad_sigma'));
        if (getVal('decode_sharpening') !== '') payload.decode_sharpening = parseFloat(getVal('decode_sharpening'));
        if (getVal('min_tag_area') !== '') payload.min_tag_area = parseInt(getVal('min_tag_area'));
        if (getVal('min_decision_margin') !== '') payload.min_decision_margin = parseFloat(getVal('min_decision_margin'));
        if (getVal('min_detection_frames') !== '') payload.min_detection_frames = parseInt(getVal('min_detection_frames'));
        if (getVal('allow_quick_pass') !== '') payload.allow_quick_pass = (getVal('allow_quick_pass') === 'true');
        if (getVal('quick_pass_time') !== '') payload.quick_pass_time = parseFloat(getVal('quick_pass_time'));

        const resp = await fetch('/api/detector-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            detectorModal.classList.add('hidden');
            alert('Parámetros del detector aplicados.');
        } else {
            const data = await resp.json();
            alert('Error aplicando parámetros: ' + (data.error || resp.statusText));
        }
    });
}

window.initializeDetectorConfig = initializeDetectorConfig;
