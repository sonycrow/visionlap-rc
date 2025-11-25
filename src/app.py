from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO
from src.models import (db, Driver, Session, Lap,
                        Championship, Season, RaceEvent,
                        SeasonRegistration, RaceRegistration, Track)
from src.detector import RaceSystem
from datetime import datetime
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


@app.route('/drivers')
def drivers_list():
    # Página central de gestión de pilotos
    # Proporcionamos la lista para renderizado inicial (paginación ligera en frontend)
    drivers = Driver.query.order_by(Driver.nickname).all()
    return render_template('drivers.html', drivers=drivers)


@app.route('/drivers/<int:driver_id>')
def driver_detail(driver_id):
    d = Driver.query.get_or_404(driver_id)
    return render_template('driver_detail.html', driver=d)


@app.route('/championships')
def championships_list():
    champs = Championship.query.order_by(Championship.created_at.desc()).all()
    return render_template('championships.html', championships=champs)


@app.route('/championships/<int:champ_id>')
def championship_detail(champ_id):
    champ = Championship.query.get_or_404(champ_id)
    seasons = champ.seasons.order_by(Season.start_date.desc()).all()
    return render_template('championship_detail.html', championship=champ, seasons=seasons)


@app.route('/seasons/<int:season_id>')
def season_detail(season_id):
    season = Season.query.get_or_404(season_id)
    races = season.races.order_by(RaceEvent.order).all()
    # drivers eligible to register
    drivers = Driver.query.order_by(Driver.nickname).all()
    registrations = season.registrations.all()
    return render_template('season_detail.html', season=season, races=races, drivers=drivers, registrations=registrations)


@app.route('/races/<int:race_id>')
def race_detail(race_id):
    race = RaceEvent.query.get_or_404(race_id)
    sessions = Session.query.filter_by(race_id=race.id).order_by(Session.start_time).all()
    regs = race.registrations.all()
    drivers = [r.driver for r in regs]
    return render_template('race_detail.html', race=race, sessions=sessions, registrations=regs, drivers=drivers)

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


@app.route('/api/drivers/<int:driver_id>/stats', methods=['GET'])
def api_driver_stats(driver_id):
    try:
        driver = Driver.query.get_or_404(driver_id)

        # número de vueltas registradas en Lap
        laps_count = Lap.query.filter_by(driver_id=driver_id).count()

        # mejor tiempo de vuelta
        best_lap_row = Lap.query.filter_by(driver_id=driver_id).order_by(Lap.lap_time.asc()).first()
        best_lap = best_lap_row.lap_time if best_lap_row else None

        # resumen adicional: promedio y total
        from sqlalchemy import func
        agg = db.session.query(func.count(Lap.id), func.avg(Lap.lap_time), func.sum(Lap.lap_time)).filter(Lap.driver_id==driver_id).first()
        total_laps = int(agg[0]) if agg and agg[0] is not None else 0
        avg_lap = float(agg[1]) if agg and agg[1] is not None else None
        sum_lap = float(agg[2]) if agg and agg[2] is not None else None

        # sesiones distintas donde ha marcado vueltas
        sessions_count = db.session.query(func.count(func.distinct(Lap.session_id))).filter(Lap.driver_id==driver_id).scalar() or 0

        # número de carreras (RaceRegistration) en las que figura
        races_count = RaceRegistration.query.filter_by(driver_id=driver_id).count()

        # número de carreras iniciadas
        races_started = RaceRegistration.query.filter_by(driver_id=driver_id, did_start=True).count()

        # número de podios (finish_position <= 3 y no null)
        podiums_count = RaceRegistration.query.filter(RaceRegistration.driver_id==driver_id, RaceRegistration.finish_position.isnot(None), RaceRegistration.finish_position <= 3).count()

        # campeonatos donde ha participado (a partir de SeasonRegistration & RaceRegistration -> season->championship)
        # 1) temporadas inscritas
        season_ids = [r.season_id for r in SeasonRegistration.query.filter_by(driver_id=driver_id).all()]
        champs_from_seasons = Championship.query.join(Season).filter(Season.id.in_(season_ids)).with_entities(Championship.id).distinct().all()
        champs_ids = {c[0] for c in champs_from_seasons}

        # 2) carreras donde participó (RaceRegistration -> race -> season -> championship)
        race_regs = RaceRegistration.query.filter_by(driver_id=driver_id).all()
        for rr in race_regs:
            if rr.race and rr.race.season and rr.race.season.championship:
                champs_ids.add(rr.race.season.championship.id)

        championships_count = len(champs_ids)

        # Opcional: lista de campeonatos (id,name)
        championships = []
        if champs_ids:
            chs = Championship.query.filter(Championship.id.in_(list(champs_ids))).all()
            championships = [{'id':c.id, 'name': c.name} for c in chs]

        return jsonify({'driver_id': driver_id, 'laps': laps_count, 'total_laps': total_laps, 'avg_lap': avg_lap, 'sum_lap': sum_lap, 'best_lap': best_lap, 'sessions_count': sessions_count, 'races': races_count, 'races_started': races_started, 'podiums': podiums_count, 'championships_count': championships_count, 'championships': championships})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers/<int:driver_id>/laps', methods=['GET'])
def api_driver_laps(driver_id):
    try:
        # Paginado simple
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=50, type=int)

        query = Lap.query.filter_by(driver_id=driver_id).order_by(Lap.timestamp.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        items = []
        for lap in pagination.items:
            session = lap.session
            race = None
            season = None
            championship = None
            if session and getattr(session, 'race_event', None):
                race = session.race_event
                season = getattr(race, 'season', None)
                championship = getattr(season, 'championship', None) if season else None

            items.append({
                'id': lap.id,
                'session_id': lap.session_id,
                'session_type': session.type if session else None,
                'race_id': race.id if race else None,
                'race_name': race.name if race else None,
                'season_id': season.id if season else None,
                'season_name': season.name if season else None,
                'championship_id': championship.id if championship else None,
                'championship_name': championship.name if championship else None,
                'lap_number': lap.lap_number,
                'lap_time': lap.lap_time,
                'timestamp': lap.timestamp.isoformat() if lap.timestamp else None,
                'is_valid': lap.is_valid
            })

        return jsonify({'items': items, 'page': pagination.page, 'per_page': pagination.per_page, 'pages': pagination.pages, 'total': pagination.total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers/<int:driver_id>/participations', methods=['GET'])
def api_driver_participations(driver_id):
    try:
        # devuelve RaceRegistration rows con info de race/season/championship
        regs = RaceRegistration.query.filter_by(driver_id=driver_id).all()
        items = []
        for r in regs:
            race = r.race
            season = getattr(race, 'season', None) if race else None
            championship = getattr(season, 'championship', None) if season else None
            items.append({
                'id': r.id,
                'race_id': r.race_id,
                'race_name': race.name if race else None,
                'season_id': season.id if season else None,
                'season_name': season.name if season else None,
                'championship_id': championship.id if championship else None,
                'championship_name': championship.name if championship else None,
                'confirmed': r.confirmed,
                'did_start': r.did_start,
                'finish_position': r.finish_position,
                'points': r.points
            })

        return jsonify({'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers/<int:driver_id>/history', methods=['GET'])
def api_driver_history(driver_id):
    try:
        # Una vista agregada con laps y participations
        laps = Lap.query.filter_by(driver_id=driver_id).order_by(Lap.timestamp.desc()).limit(200).all()
        regs = RaceRegistration.query.filter_by(driver_id=driver_id).all()

        lap_items = [{'id': l.id, 'lap_number': l.lap_number, 'lap_time': l.lap_time, 'timestamp': l.timestamp.isoformat(), 'session_id': l.session_id} for l in laps]
        regs_items = [{'id': r.id, 'race_id': r.race_id, 'confirmed': r.confirmed, 'did_start': r.did_start, 'finish_position': r.finish_position, 'points': r.points} for r in regs]

        return jsonify({'laps': lap_items, 'participations': regs_items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


@app.route('/api/detector-config', methods=['GET'])
def api_get_detector_config():
    try:
        cfg = vision_system.get_detector_config() or {}
        return jsonify(cfg)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/detector-config', methods=['POST'])
def api_set_detector_config():
    try:
        data = request.get_json(force=True) or {}
        updated = vision_system.update_detector_config(data)
        return jsonify({'ok': True, 'detector_config': updated})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/camera-autotune', methods=['POST'])
def api_camera_autotune():
    try:
        # Ejecutar autotune (bloqueante, pero rápido)
        result = vision_system.auto_tune_camera()
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/start', methods=['POST'])
def start_session():
    # Cerrar sesiones anteriores
    old_sessions = Session.query.filter_by(is_active=True).all()
    for s in old_sessions:
        s.is_active = False
    
    # Nueva sesión
    # Opcional: si se especifica race_id y type en POST JSON, se asignan
    payload = request.get_json(silent=True) or {}
    s_type = payload.get('type', 'race')
    race_id = payload.get('race_id')
    new_session = Session(type=s_type, race_id=race_id)
    db.session.add(new_session)
    db.session.commit()
    
    # Resetear timers del detector
    vision_system.lap_timers = {}
    
    socketio.emit('session_status', {'state': 'started'})
    return jsonify({'status': 'started', 'session_id': new_session.id})


@app.route('/api/championships', methods=['GET', 'POST'])
def api_championships():
    if request.method == 'GET':
        items = Championship.query.order_by(Championship.created_at.desc()).all()
        return jsonify([{'id': c.id, 'name': c.name, 'description': c.description} for c in items])

    data = request.json or {}
    try:
        c = Championship(name=data['name'], description=data.get('description'))
        db.session.add(c)
        db.session.commit()
        return jsonify({'ok': True, 'id': c.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/seasons', methods=['POST'])
def api_create_season():
    data = request.json or {}
    try:
        season = Season(
            championship_id = data.get('championship_id'),
            name = data.get('name'),
            year = data.get('year'),
            settings = data.get('settings')
        )
        db.session.add(season)
        db.session.commit()
        return jsonify({'ok': True, 'id': season.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/races', methods=['POST'])
def api_create_race():
    data = request.json or {}
    try:
        race = RaceEvent(
            season_id = data.get('season_id'),
            name = data.get('name'),
            track_id = data.get('track_id'),
            scheduled_date = data.get('scheduled_date'),
            order = data.get('order', 0),
            settings = data.get('settings')
        )
        db.session.add(race)
        db.session.commit()
        return jsonify({'ok': True, 'id': race.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/seasons/<int:season_id>/register', methods=['POST'])
def api_register_season(season_id):
    data = request.json or {}
    try:
        driver_id = data['driver_id']
        number = data.get('number')
        existing = SeasonRegistration.query.filter_by(season_id=season_id, driver_id=driver_id).first()
        if existing:
            existing.active = True
            db.session.commit()
            return jsonify({'ok': True, 'id': existing.id})

        reg = SeasonRegistration(season_id=season_id, driver_id=driver_id, number=number)
        db.session.add(reg)
        db.session.commit()
        return jsonify({'ok': True, 'id': reg.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/races/<int:race_id>/sessions', methods=['POST'])
def api_create_race_session(race_id):
    data = request.json or {}
    try:
        s_type = data.get('type') or 'practice'
        start_time = data.get('start_time')
        max_laps = data.get('max_laps')
        duration = data.get('duration')
        new_s = Session(type=s_type, race_id=race_id)
        if start_time:
            try:
                new_s.start_time = datetime.fromisoformat(start_time)
            except Exception:
                pass
        if max_laps is not None:
            new_s.max_laps = int(max_laps)
        if duration is not None:
            new_s.duration = int(duration)

        db.session.add(new_s)
        db.session.commit()
        return jsonify({'ok': True, 'id': new_s.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/sessions/<int:session_id>/stop', methods=['POST'])
def api_stop_session(session_id):
    try:
        s = Session.query.get_or_404(session_id)
        s.is_active = False
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/races/<int:race_id>/register', methods=['POST'])
def api_register_race(race_id):
    data = request.json or {}
    try:
        driver_id = data['driver_id']
        confirmed = bool(data.get('confirmed', True))
        existing = RaceRegistration.query.filter_by(race_id=race_id, driver_id=driver_id).first()
        if existing:
            existing.confirmed = confirmed
            db.session.commit()
            return jsonify({'ok': True, 'id': existing.id})

        reg = RaceRegistration(race_id=race_id, driver_id=driver_id, confirmed=confirmed)
        db.session.add(reg)
        db.session.commit()
        return jsonify({'ok': True, 'id': reg.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

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