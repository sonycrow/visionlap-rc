function initializeModalHandlers() {
    // Wrapper: delega en módulos especializados para cámara y detector
    if (typeof initializeCameraConfig === 'function') initializeCameraConfig();
    if (typeof initializeDetectorConfig === 'function') initializeDetectorConfig();
}