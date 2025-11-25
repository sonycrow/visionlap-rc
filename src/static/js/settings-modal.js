// Manejo del modal de opciones (settings)
// Mantiene la configuración de la carrera y provee una función de inicialización

// valores por defecto (se usan en race-control.js cuando corresponde)
let prepTime = 60; // segundos de preparación (parrilla)
let maxTime = 5;   // minutos - tiempo máximo de carrera
let maxLaps = 10;  // número máximo de vueltas

// Exponer un estado compartido por nombre (manteniendo compatibilidad con el código existente)

// Elementos del DOM del modal (se establecerán en init)
let settingsModal, settingsForm, prepTimeInput, maxTimeInput, maxLapsInput;

function initializeSettingsModal() {
    settingsModal = document.getElementById('settingsModal');
    settingsForm = document.getElementById('settingsForm');
    prepTimeInput = document.getElementById('prepTime');
    maxTimeInput = document.getElementById('maxTime');
    maxLapsInput = document.getElementById('maxLaps');

    const settingsBtn = document.getElementById('settingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettings');

    settingsBtn?.addEventListener('click', openSettingsModal);
    cancelSettingsBtn?.addEventListener('click', closeSettingsModal);
    settingsForm?.addEventListener('submit', handleSettingsSave);
}

function openSettingsModal() {
    const raceState = (window.currentRaceState ?? 'idle');
    if (raceState !== 'idle') {
        console.log("No se pueden cambiar las opciones mientras una carrera está en curso.");
        return;
    }
    if (prepTimeInput) prepTimeInput.value = prepTime;
    if (maxTimeInput) maxTimeInput.value = maxTime;
    if (maxLapsInput) maxLapsInput.value = maxLaps;
    settingsModal?.classList.remove('hidden');
}

function closeSettingsModal() {
    settingsModal?.classList.add('hidden');
}

function handleSettingsSave(e) {
    e.preventDefault();
    prepTime = parseInt(prepTimeInput?.value, 10) || 60;
    maxTime = parseInt(maxTimeInput?.value, 10) || 5;
    maxLaps = parseInt(maxLapsInput?.value, 10) || 10;
    // Actualizar reflejos en window para scripts que los lean via window
    window.prepTime = prepTime;
    window.maxTime = maxTime;
    window.maxLaps = maxLaps;

    console.log("Opciones guardadas:", { prepTime, maxTime, maxLaps });
    closeSettingsModal();
}

// Dejar las funciones accesibles en global para simplicidad y compatibilidad
window.initializeSettingsModal = initializeSettingsModal;
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.handleSettingsSave = handleSettingsSave;

// también exponer valores por si otros scripts los leen/modifican directamente
// Exponer variables al objeto global con getters/setters para mantener sincronía
Object.defineProperty(window, 'prepTime', {
    get() { return prepTime; },
    set(v) { prepTime = v; }
});
Object.defineProperty(window, 'maxTime', {
    get() { return maxTime; },
    set(v) { maxTime = v; }
});
Object.defineProperty(window, 'maxLaps', {
    get() { return maxLaps; },
    set(v) { maxLaps = v; }
});
// Nota: el estado de la carrera ahora es responsabilidad de `race-control.js`.
