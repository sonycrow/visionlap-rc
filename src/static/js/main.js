// Importar módulos (esto es conceptual, ya que no usamos un bundler como Webpack)
// Los scripts se cargan en orden en layout.html

// Código de entrada principal: inicializa los módulos de la UI.
// Los scripts se cargan en orden desde `layout.html`.

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar módulos existentes
    initializeRaceControls();
    initializeDriverManager();
    initializeDetectorControls();
    initializeModalHandlers();
    // inicializa el modal de settings (módulo extraído)
    if (typeof initializeSettingsModal === 'function') initializeSettingsModal();
    initializeLeaderboard();
});
