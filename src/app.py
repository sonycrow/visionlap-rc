from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO
from src.models import db, Driver, Session, Lap
from src.detector import RaceSystem
from src import camera_config_store as camcfg
from flask_migrate import Migrate
import eventlet
import os

# Inicializar Flask y SocketIO
app = Flask(__name__)
# Cargar configuración desde `config.py` o variables de entorno
app.config.from_object('config')

db.init_app(app)

# Inicializar migraciones (Flask-Migrate)
migrate = Migrate(app, db)

# Usar eventlet para concurrencia asíncrona compatible con WebSockets
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

# Cargar o crear configuración persistente de cámara (desde .env -> config.py la primera vez)
camcfg.load_or_create_from_module_config(app.config)
camera_cfg = camcfg.get_current() or {}

# Instanciar el sistema de visión usando la configuración persistente
camera_idx = int(camera_cfg.get('CAMERA_IDX', app.config.get('CAMERA_IDX', 0)))
res = camera_cfg.get('CAMERA_RESOLUTION', app.config.get('CAMERA_RESOLUTION', (640, 480)))
if isinstance(res, list):
    camera_resolution = (int(res[0]), int(res[1]))
else:
    camera_resolution = res

finish_line = camera_cfg.get('FINISH_LINE', app.config.get('FINISH_LINE', ((100, 240), (540, 240))))
vision_system = RaceSystem(camera_idx=camera_idx, resolution=camera_resolution, finish_line=finish_line)

# Callback que se ejecuta cuando el detector ve una vuelta
def handle_new_lap(tag_id, lap_time):
    # Ignorar notificaciones si el detector está deshabilitado
    try:
        if not getattr(vision_system, 'enabled', True):
            return
    except Exception:
        pass

    with app.app_context():
        # Buscar conductor
        driver = Driver.query.filter_by(tag_id=tag_id).first()
        if not driver:
            print(f"Tag desconocido: {tag_id}")
            return

        # Buscar sesión activa
        active_session = Session.query.filter_by(is_active=True).first()
        if active_session:
            # Determinar número de vuelta
            lap_count = Lap.query.filter_by(session_id=active_session.id, driver_id=driver.id).count()
            new_lap = Lap(
                session_id=active_session.id,
                driver_id=driver.id,
                lap_number=lap_count + 1,
                lap_time=lap_time
            )
            db.session.add(new_lap)
            db.session.commit()

            # Enviar evento en tiempo real al frontend
            socketio.emit('lap_update', {
                'driver_name': driver.name,
                'nickname': driver.nickname,
                'lap_time': round(lap_time, 3),
                'lap_number': lap_count + 1,
                'tag_id': tag_id
            })

# Conectar callback
vision_system.on_lap_callback = handle_new_lap


def refresh_allowed_tags():
    """Leer los tags de la base de datos y actualizar el filtro del detector."""
    try:
        with app.app_context():
            tags = [d.tag_id for d in Driver.query.all() if d.tag_id is not None]
            # Normalizar int
            tags = [int(t) for t in tags]
            vision_system.set_allowed_tags(tags)
    except Exception as e:
        print(f"Error actualizando allowed_tags: {e}")

# Inicializar allowed_tags con los pilotos actuales
refresh_allowed_tags()

# Rutas Flask
@app.route('/')
def index():
    drivers = Driver.query.all()
    return render_template('index.html', drivers=drivers)

@app.route('/api/drivers', methods=['POST'])
def add_driver():
    data = request.json or {}
    try:
        new_driver = Driver(name=data['name'], nickname=data['nickname'], tag_id=data['tag_id'])
        db.session.add(new_driver)
        db.session.commit()
        # Refrescar tags permitidos en el detector
        try:
            refresh_allowed_tags()
        except Exception:
            pass
        return jsonify({'status': 'ok'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/drivers', methods=['GET'])
def get_drivers():
    try:
        # Parámetros opcionales: q (search), page, per_page
        q = request.args.get('q', type=str)
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)

        query = Driver.query
        if q:
            like = f"%{q}%"
            query = query.filter((Driver.name.ilike(like)) | (Driver.nickname.ilike(like)))

        query = query.order_by(Driver.nickname)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        result = {
            'items': [d.to_dict() for d in pagination.items],
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers/<int:driver_id>', methods=['PUT'])
def update_driver(driver_id):
    data = request.json or {}
    try:
        driver = Driver.query.get_or_404(driver_id)
        if 'name' in data:
            driver.name = data['name']
        if 'nickname' in data:
            driver.nickname = data['nickname']
        if 'tag_id' in data:
            driver.tag_id = data['tag_id']
        db.session.commit()
        # Refrescar tags permitidos
        try:
            refresh_allowed_tags()
        except Exception:
            pass
        return jsonify({'status': 'ok', 'driver': driver.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/drivers/<int:driver_id>', methods=['DELETE'])
def delete_driver(driver_id):
    try:
        driver = Driver.query.get_or_404(driver_id)
        db.session.delete(driver)
        db.session.commit()
        # Refrescar tags permitidos
        try:
            refresh_allowed_tags()
        except Exception:
            pass
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/detector/start', methods=['POST'])
def detector_start():
    try:
        print('Endpoint detector_start called (PID:', os.getpid(), ')')
        # Iniciar el hilo del detector si no está corriendo
        if not getattr(vision_system, 'running', False):
            vision_system.start()
        # Asegurar que el callback está asignado
        vision_system.on_lap_callback = handle_new_lap
        # Habilitar notificaciones
        vision_system.enabled = True
        return jsonify({'status': 'started', 'running': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/detector/stop', methods=['POST'])
def detector_stop():
    try:
        print('Endpoint detector_stop called (PID:', os.getpid(), ')')
        # Desasignar callback y desactivar notificaciones antes de parar
        try:
            vision_system.on_lap_callback = None
            vision_system.enabled = False
        except Exception:
            pass

        if getattr(vision_system, 'running', False):
            try:
                vision_system.stop()
            except Exception:
                # asegurar que se marque como detenido
                vision_system.running = False

        return jsonify({'status': 'stopped', 'running': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/detector/status', methods=['GET'])
def detector_status():
    try:
        running = bool(getattr(vision_system, 'running', False))
        return jsonify({'running': running})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/camera-config', methods=['GET'])
def api_get_camera_config():
    try:
        cfg = camcfg.get_current() or {}
        return jsonify(cfg)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/camera-config', methods=['POST'])
def api_set_camera_config():
    try:
        data = request.get_json(force=True) or {}
        # Guardar y aplicar. camcfg.save_and_apply reiniciará el detector si está en marcha
        updated = camcfg.save_and_apply(data, vision_system=vision_system)
        return jsonify({'ok': True, 'camera_config': updated})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/start', methods=['POST'])
def start_session():
    # Cerrar sesiones anteriores
    old_sessions = Session.query.filter_by(is_active=True).all()
    for s in old_sessions:
        s.is_active = False
    
    # Nueva sesión
    new_session = Session(type='race')
    db.session.add(new_session)
    db.session.commit()
    
    # Resetear timers del detector
    vision_system.lap_timers = {}
    
    socketio.emit('session_status', {'state': 'started'})
    return jsonify({'status': 'started', 'session_id': new_session.id})

# Streaming de Video (MJPEG)
def gen_frames():
    while True:
        frame = vision_system.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        eventlet.sleep(0.02)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    if not os.path.exists('visionlap.db'):
        with app.app_context():
            db.create_all()
            print("Base de datos creada.")
    
    vision_system.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)