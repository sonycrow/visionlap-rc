let raceStatusBlock;
let semaphoreOverlay, semaphoreLights, semaphoreTimer;
let gridCountdownInterval, semaphoreCountdownInterval, raceTimerInterval;

const RACE_STATE = {
    IDLE: 'idle',
    PREPARING: 'preparing',
    STARTING: 'starting',
    RUNNING: 'running',
    FINISHED: 'finished'
};

function initializeRaceControls() {
    raceStatusBlock = document.getElementById('raceStatusBlock');
    semaphoreOverlay = document.getElementById('semaphoreOverlay');
    semaphoreLights = document.getElementById('semaphoreLights').children;
    semaphoreTimer = document.getElementById('semaphoreTimer');

    // Asignar funciones a los botones globales (si no se usa un sistema de módulos con export)
    window.startSession = startSession;
    window.stopSession = stopSession;

    // Estado inicial
    currentRaceState = RACE_STATE.IDLE;
}

function updateRaceStatus(message) {
    if (raceStatusBlock) raceStatusBlock.innerHTML = message;
}

function stopSession() {
    clearInterval(gridCountdownInterval);
    clearInterval(semaphoreCountdownInterval);
    clearInterval(raceTimerInterval);

    semaphoreOverlay.classList.add('hidden');
    semaphoreOverlay.classList.remove('flex');
    
    currentRaceState = RACE_STATE.IDLE;
    driversData = {}; // Reinicia los datos del leaderboard
    renderLeaderboard();
    updateRaceStatus('<p class="text-gray-300">Carrera detenida. Haz clic en "Iniciar" para empezar de nuevo.</p>');
    
    fetch('/api/session/stop', {method: 'POST'});
    console.log("Sesión detenida por el usuario.");
}

async function startSession() {
    if (currentRaceState !== RACE_STATE.IDLE) return;
    
    console.log("Iniciando secuencia de carrera...");
    currentRaceState = RACE_STATE.PREPARING;
    
    let gridTime = prepTime;
    updateRaceStatus(`<h4 class="text-xl font-bold text-yellow-400 mb-2">¡Prepara la parrilla!</h4><p class="text-gray-200">Tiempo: <span class="font-mono text-2xl">${gridTime}</span>s</p>`);
    
    gridCountdownInterval = setInterval(() => {
        gridTime--;
        updateRaceStatus(`<h4 class="text-xl font-bold text-yellow-400 mb-2">¡Prepara la parrilla!</h4><p class="text-gray-200">Tiempo: <span class="font-mono text-2xl">${gridTime}</span>s</p>`);
        if (gridTime <= 0) {
            clearInterval(gridCountdownInterval);
            startSemaphoreCountdown();
        }
    }, 1000);
}

function startSemaphoreCountdown() {
    currentRaceState = RACE_STATE.STARTING;
    semaphoreOverlay.classList.remove('hidden');
    semaphoreOverlay.classList.add('flex');
    let semaphoreTime = 10;
    
    const updateLights = (count) => {
        for (let i = 0; i < semaphoreLights.length; i++) {
            semaphoreLights[i].classList.toggle('red', i < count);
        }
    };
    
    for(const light of semaphoreLights) light.classList.remove('red', 'green');
    
    semaphoreCountdownInterval = setInterval(() => {
        semaphoreTimer.textContent = semaphoreTime;
        
        if (semaphoreTime <= 5 && semaphoreTime > 0) updateLights(6 - semaphoreTime);

        if (semaphoreTime === 0) {
            clearInterval(semaphoreCountdownInterval);
            for(const light of semaphoreLights) {
                light.classList.remove('red');
                light.classList.add('green');
            }
            
            setTimeout(() => {
                semaphoreOverlay.classList.add('hidden');
                semaphoreOverlay.classList.remove('flex');
                startRace();
            }, 1000);
        }
        semaphoreTime--;
    }, 1000);
}

async function startRace() {
    await fetch('/api/session/start', {method: 'POST'});
    currentRaceState = RACE_STATE.RUNNING;
    
    let raceTime = maxTime * 60;
    const formatTime = (s) => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;

    updateRaceStatus(`
        <div class="flex justify-around items-center">
            <div><h5 class="text-sm uppercase text-gray-400">Tiempo</h5><p class="font-mono text-3xl text-green-400">${formatTime(raceTime)}</p></div>
            <div><h5 class="text-sm uppercase text-gray-400">Vueltas Máx.</h5><p class="font-mono text-3xl">${maxLaps}</p></div>
        </div>`);

    raceTimerInterval = setInterval(() => {
        raceTime--;
        const timeElement = raceStatusBlock.querySelector('.text-green-400');
        if (timeElement) timeElement.textContent = formatTime(raceTime);

        if (raceTime <= 0) {
            clearInterval(raceTimerInterval);
            currentRaceState = RACE_STATE.FINISHED;
            updateRaceStatus('<h4 class="text-xl font-bold text-red-500">¡CARRERA FINALIZADA!</h4>');
            stopSession();
        }
    }, 1000);
}