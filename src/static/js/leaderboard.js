let driversData = {}; // Cache local de tiempos

function initializeLeaderboard() {
    const socket = io();

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

    renderLeaderboard(); // Render inicial
}

function renderLeaderboard() {
    const tbody = document.getElementById('leaderboardBody');
    if (!tbody) return;
    
    let sortedDrivers = Object.values(driversData).sort((a, b) => b.laps - a.laps);

    if (sortedDrivers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-gray-500">No hay registros para mostrar</td></tr>`;
        return;
    }

    tbody.innerHTML = sortedDrivers.map((d, index) => `
        <tr class="bg-gray-800 hover:bg-gray-700">
            <td class="px-4 py-2">${index + 1}</td><td class="px-4 py-2">${d.name}</td><td class="px-4 py-2">${d.laps}</td>
            <td class="px-4 py-2 lap-time-display">${d.last.toFixed(3)}</td><td class="px-4 py-2 text-green-400">${d.best.toFixed(3)}</td><td class="px-4 py-2">-</td>
        </tr>`).join('');
}