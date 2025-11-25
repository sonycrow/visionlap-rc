// Importar módulos (esto es conceptual, ya que no usamos un bundler como Webpack)
// Los scripts se cargan en orden en layout.html

// Elementos de UI para la carrera
let settingsModal, settingsForm, prepTimeInput, maxTimeInput, maxLapsInput;

// Configuración de la carrera (con valores por defecto)
let prepTime = 60;
let maxTime = 5; // en minutos
let maxLaps = 10;

// Estado de la carrera
let currentRaceState = 'idle'; // Gestionado en race-control.js

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar todos los módulos
    initializeRaceControls();
    initializeDriverManager();
    initializeDetectorControls();
    initializeModalHandlers();
    initializeLeaderboard();

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
});

function openSettingsModal() {
    if (currentRaceState !== 'idle') {
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
