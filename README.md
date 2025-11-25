# VisionLap RC

Sistema de cronometraje para automodelismo a escala basado en visión por computador y marcadores AprilTag.

**Objetivo:** Proveer una solución de bajo coste y alta frecuencia de muestreo para cronometrar carreras de automodelismo en escalas 1:28 y 1:64 usando cámaras de alto FPS y detección de fiduciales.

**Estado:** Prototipo / en desarrollo

**Contenido del repositorio**
- `hardware/` - modelos 3D y materiales relacionados con los tags y soportes.
- `src/` - código fuente (app, detector, modelos, templates, static).
- `config.py` - configuración por defecto.
- `run.py` - script para iniciar la aplicación.

Revisa `ANALISIS.md` para la arquitectura y decisiones de diseño.

---

## Requisitos

- Python 3.9+
- Dependencias listadas en `requirements.txt` (instálalas con pip).
- Cámara compatible con OpenCV (se recomienda PS3 Eye o cámaras que soporten 60+ FPS para mejor precisión).

En Windows se recomienda usar la backend `CAP_DSHOW` para OpenCV.

## Instalación

1. Clona el repositorio:

```powershell
git clone <repo-url> visionlap-rc
cd visionlap-rc
```

2. Crea un entorno virtual (recomendado) e instala dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Copia el archivo de ejemplo de variables de entorno y ajústalo si es necesario:

```powershell
copy .env.example .env
# Edita .env para ajustar la cámara o la clave secreta
```

## Configuración

Los parámetros principales están en `config.py` o en variables de entorno:
- `DATABASE_URL` (por defecto `sqlite:///visionlap.db`)
- `SECRET_KEY`
- `CAMERA_IDX`, `CAMERA_WIDTH`, `CAMERA_HEIGHT`
- `FINISH_LINE` (coordenadas por defecto para la línea de meta)

## Ejecución

Inicia la app desde la raíz del proyecto:

```powershell
python run.py
```

La aplicación arranca en `http://0.0.0.0:5000` por defecto. El feed de vídeo MJPEG está en `/video_feed`.

Endpoints relevantes (API REST):
- `POST /api/drivers` - Añadir conductor (JSON: `name`, `nickname`, `tag_id`).
- `POST /api/session/start` - Iniciar sesión (race).

La aplicación emite eventos en tiempo real vía WebSockets (Socket.IO): `lap_update`, `session_status`.

## Desarrollo

- `src/detector.py` contiene la lógica de adquisición y detección de tags.
- `src/models.py` define los modelos SQLAlchemy.
- `src/app.py` expone rutas y configura Socket.IO.

### Panel central de pilotos

Se ha añadido una página de gestión centralizada para pilotos en `/drivers` con:
- Listado y búsqueda de pilotos.
- Formulario inline para crear pilotos y uso del modal existente para edición.
- Estadísticas por piloto (vueltas registradas, carreras inscritas, podios, campeonatos donde participó) mediante `/api/drivers/<id>/stats`.

### Historial detallado por piloto

La nueva vista de detalle de piloto (`/drivers/<id>`) muestra:
- Resumen con mejores tiempos, número de carreras iniciadas, podios y campeonatos donde participó.
- Pestañas con tablas: historial de vueltas (`/api/drivers/<id>/laps`) y participaciones en carreras (`/api/drivers/<id>/participations`).

Estas APIs devuelven información cruzada con `RaceEvent` y `Season` cuando esté disponible, por ejemplo para identificar en qué temporada y campeonato se consiguió una vuelta o participación.

Esto facilita compartir pilotos entre temporadas / carreras desde un único sitio.

## Sistema de Campeonatos (nueva funcionalidad)

He añadido soporte básico de campeonatos/temporadas/carreras y sesiones (práctica/qualy/carrera):

- Modelos nuevos: `Championship`, `Season`, `RaceEvent`, `SeasonRegistration`, `RaceRegistration` (en `src/models.py`).
- Rutas y API básicas en `src/app.py`:
	- Páginas: `/championships`, `/championships/<id>`, `/seasons/<id>`, `/races/<id>` — páginas para gestionar campeonatos, temporadas, carreras y sesiones.
	- Endpoints API para CRUD: `/api/championships`, `/api/seasons`, `/api/races`, `/api/seasons/<id>/register`, `/api/races/<id>/register`, `/api/races/<id>/sessions`.

### Flujo esperado

1. Crear un `Championship` (p. ej. "Mini 1/28 Series").
2. Crear `Season` dentro del campeonato (p. ej. `2025`).
3. Dentro de la temporada, definir `RaceEvent` (cada GP / round) con orden y fecha.
4. Para cada `RaceEvent`, crear `Session` (practice, qualy, race). Estas sesiones pueden iniciarse con el detector (POST `/api/session/start` admite ahora payload `{type, race_id}`).
5. Inscribir pilotos a la temporada (`/api/seasons/<id>/register`) y/o a carreras individuales (`/api/races/<id>/register`).

### Notas operativas
- He añadido la relación `Session.race_id` para enlazar sesiones a `RaceEvent`. Si ya tienes una base de datos, crea una migración con Flask-Migrate antes de ejecutar.

### Migraciones

Si usas Flask-Migrate ejecuta (desde PowerShell en la raíz del repo):

```powershell
setx FLASK_APP run.py
flask db migrate -m "Add championships/season/race models"
flask db upgrade
```

Si tu base de datos local tiene datos críticos, haz backup antes de aplicar migraciones.

### Frontend / JavaScript

Los scripts del frontend están modularizados bajo `src/static/js/` — cada responsabilidad vive en su propio fichero, por ejemplo:
- `settings-modal.js` — manejo del modal de opciones y parámetros globales (prepTime, maxTime, maxLaps)
 - `camera-config.js` — manejo del modal de configuración de cámara y autotune
 - `detector-config.js` — manejo del modal de tuning del detector
- `race-control.js` — lógica de control de la sesión / secuencia de semáforo y cronometraje
- `driver-manager.js` — gestión CRUD de pilotos
- `detector-control.js`, `modal-handlers.js`, `leaderboard.js` — otros módulos UI

La plantilla principal (`src/templates/layout.html`) carga estos scripts en el orden necesario antes del archivo `main.js` que actúa como entrypoint.

Para cambiar parámetros de la cámara o la línea de meta edita `config.py` o exporta variables de entorno antes de ejecutar.

## Pruebas y migraciones

Actualmente la base de datos se crea con `db.create_all()` en arranque si no existe. Se ha añadido soporte para `Flask-Migrate`.

Comandos típicos para migraciones (desde PowerShell en la raíz del proyecto):

```powershell
setx FLASK_APP run.py
# Inicializar el repositorio de migraciones (solo la primera vez)
flask db init
# Generar una nueva migración detectando cambios en modelos
flask db migrate -m "Inicial"
# Aplicar migraciones al esquema
flask db upgrade
```

Si prefieres usar variables de entorno en la sesión actual en PowerShell, usa:

```powershell
$env:FLASK_APP = 'run.py'
```

## Contribuir

- Haz fork del repositorio y abre un PR con tus cambios.
- Añade tests y documentación clara para cambios en la API o en el pipeline de detección.

## Problemas conocidos

- La instalación de `pupil-apriltags` puede requerir compilación nativa en Windows; usa wheels si existen o ejecuta en WSL si tienes problemas.
- Ajusta la exposición/iluminación de la cámara para evitar motion blur a altas velocidades.