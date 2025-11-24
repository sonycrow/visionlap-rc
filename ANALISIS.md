# Diseño e Implementación de Sistemas de Cronometraje de Alto Rendimiento para Automodelismo RC mediante Visión Artificial

## 1. Introducción y Análisis de Viabilidad Técnica

La medición precisa del tiempo en competiciones de automovilismo a escala, específicamente en las categorías de 1:28 (Mini-Z) y 1:64 (Diecast/Hot Wheels modificados), ha sido históricamente un desafío técnico y económico.

Los sistemas tradicionales de cronometraje (AMB/MyLaps, Robitronic) presentan barreras significativas:
* **Coste elevado** por vehículo (30-80€/transpondedor).
* **Complejidad** en la infraestructura (bucles de inducción).
* **Peso añadido** que altera la dinámica en escalas pequeñas.

Este informe detalla la arquitectura de **VisionLap RC**, una solución disruptiva que sustituye la telemetría RF por visión por computador, utilizando cámaras de alta velocidad (FPS) y marcadores fiduciales pasivos (AprilTags).

### 1.1. Justificación del Enfoque por Visión Artificial
El análisis de viabilidad sugiere que la visión artificial es la única tecnología capaz de reducir el coste marginal por nuevo piloto a prácticamente cero. Sin embargo, se deben superar tres obstáculos críticos:

1.  **Resolución Temporal:** Un coche 1:28 a 8 m/s recorre >16 cm entre fotogramas a 30 FPS. Se requiere hardware capaz de superar los **60-100 FPS**.
2.  **Robustez de Identificación:** Se debe identificar ID y pose bajo rotaciones extremas y cambios de luz.
3.  **Procesamiento en Tiempo Real:** Latencia total (captura $\to$ web) inferior a 50ms.

### 1.2. Alcance del Proyecto
El sistema es agnóstico a la plataforma y gestiona:
* Registro de pilotos y circuitos.
* Detección simultánea de múltiples vehículos.
* Gestión de sesiones (Práctica, Qualy, Carrera).
* Visualización vía WebSockets y persistencia de datos.

## 2. Arquitectura Óptica y Física

La fiabilidad depende en un 80% de la calidad de la imagen de entrada.

### 2.1. Selección del Sensor de Imagen: El Dilema de los FPS
Para escalas pequeñas, los FPS dominan sobre la resolución.

| Modelo de Cámara | Resolución Máx | FPS Máximos | Tipo de Obturador | Coste | Idoneidad |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sony PS3 Eye** | 640x480 | 75 FPS | Rolling (Rápido) | < 10€ | **Óptima** |
| **Sony PS3 Eye (Mod)** | 320x240 | **187 FPS** | Rolling (Rápido) | < 10€ | **Excelente** |
| Logitech C920 | 1920x1080 | 30 FPS | Rolling (Lento) | ~60€ | Baja |
| RPi Cam v2 | 640x480 | 90 FPS | Rolling | ~30€ | Media/Alta |
| Industrial Cam | 1280x720 | 120 FPS | Global Shutter | >300€ | Descartada |

> **Nota Técnica:** A 187 FPS (intervalo de 5.3ms), un coche a 5 m/s solo se desplaza 2.5 cm entre capturas, permitiendo precisión de centésimas de segundo.

### 2.2. Teoría de Marcadores Fiduciales: Selección de la Familia AprilTag
Se comparan las familias **36h11** (estándar robótica) y **16h5**.

* **36h11:** Matriz 6x6. Requiere alta resolución.
* **16h5:** Matriz 4x4. Píxeles físicos más grandes.

**Decisión:** Se selecciona **Tag16h5**. Su menor complejidad geométrica permite detección robusta a 320x240 píxeles y ofrece mayor resistencia al *motion blur*.

### 2.3. Iluminación y Control de Exposición
Para congelar el movimiento (exposición < 1/500s), se requiere:
* **Luz:** LED 5000K-6000K, CRI > 80.
* **Intensidad:** > 2000 lúmenes en zona de meta.
* **Flicker-Free:** Esencial para evitar bandas negras a 187 FPS.

### 2.4. Integración Mecánica
* **Rig Cenital:** Cámara estrictamente perpendicular (nadiral).
* **Montaje en Coches:**
    * *1:28:* Adhesión directa al techo.
    * *1:64:* Clip impreso en 3D que eleve el tag 5-10mm para evitar oclusiones por otros coches.

## 3. Arquitectura de Software

### 3.1. Stack Tecnológico
* **Lenguaje:** Python 3.9+.
* **Visión:** OpenCV + `pupil-apriltags` (binding C optimizado).
* **Web/Realtime:** Flask + Flask-SocketIO (Eventlet/Gevent).
* **Base de Datos:** SQLAlchemy (SQLite).

### 3.2. Estructura Modular del Código
```text
/visionlap_rc
├── /hardware
│   ├── /stl                # Archivos para impresión 3D
│   └── /tags_pdf           # Generados para familia 16h5
├── /src
│   ├── app.py              # Punto de entrada y SocketIO
│   ├── detector.py         # Lógica de visión (Thread dedicado)
│   ├── models.py           # Esquema DB
│   ├── routes.py           # API REST
│   ├── events.py           # Eventos SocketIO
│   └── /static             # JS/CSS Frontend
├── config.py
└── requirements.txt
```

## 4. Algoritmos de Visión y Lógica de Carrera

### 4.1. Pipeline de Procesamiento
1.  **Adquisición:** Buffer RAW.
2.  **Conversión:** BGR a Grayscale.
3.  **Detección:** `pupil_apriltags` (Decimate=1.0 para precisión).
4.  **Extracción de Pose:** Centroide y esquinas.

### 4.2. Algoritmo de Cruce de Línea: Intersección Vectorial
Se utiliza el producto cruz vectorial para detectar si el segmento de movimiento del coche ($P_1 \to P_2$) cruza el segmento de meta ($P_3 \to P_4$).

La función de orientación basada en el producto cruz es:

$$Orientacion(p, q, r) = (q.y - p.y) \cdot (r.x - q.x) - (q.x - p.x) \cdot (r.y - q.y)$$

Si la orientación de los tripletes indica intersección, se interpola el tiempo exacto sub-frame.

### 4.3. Filtrado
* **Debouncing:** Se ignora el mismo ID durante $X$ segundos (Min Lap Time) para evitar dobles conteos.

## 5. Protocolo de Implementación y Solución de Problemas

### 5.1. Instalación
1.  **Hardware:** Montaje de cámara cenital y luces LED.
2.  **Software:** `pip install flask flask-socketio flask-sqlalchemy opencv-python pupil-apriltags eventlet`.
3.  **Calibración:** Ajuste de enfoque manual en la PS3 Eye.

### 5.2. Diagnóstico de Problemas Comunes

| Síntoma | Causa Probable | Solución Técnica |
| :--- | :--- | :--- |
| **No detecta vueltas** | Imagen oscura / borrosa | Aumentar luz, bajar exposición, `decimate=1.0`. |
| **Vueltas fantasma** | Reflejos / Ruido | Aumentar parámetro `quad_sigma`. Pista mate. |
| **Latencia video** | Buffer saturado / WiFi | Usar Ethernet. Bajar resolución a 320x240. |
| **Detección intermitente** | Tag pequeño / Ángulo | Usar familia **16h5**. Corregir ángulo de cámara. |

### 5.3. Expansión Futura
* **Machine Learning:** YOLO-Nano para detección sin tags (requiere TPU).
* **Sectores:** Sincronización de múltiples cámaras para parciales.