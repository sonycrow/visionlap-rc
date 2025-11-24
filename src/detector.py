import cv2
import time
import numpy as np
from pupil_apriltags import Detector
from threading import Thread, Lock
import socket
import config
import os
import logging

# Logger para este módulo
logger = logging.getLogger(__name__)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(ch)
logger.setLevel(logging.INFO)

# Sistema simple de categorías de debug. Permite activar por separado:
# - detection: mensajes de detección por frame
# - filter: por qué se ignora una detección (decision_margin, area, hamming)
# - intersection: logs de comprobación de intersección de la línea
# - debounce: logs sobre debounce / lap timing
# - callback: logs al invocar callback de vuelta
GLOBAL_DEBUG_CATEGORIES = set()

def set_global_debug_categories(categories):
    """Establecer categorías de debug globales (lista o coma-separated string)."""
    if categories is None:
        GLOBAL_DEBUG_CATEGORIES.clear()
        return
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(',') if c.strip()]
    GLOBAL_DEBUG_CATEGORIES.clear()
    for c in categories:
        GLOBAL_DEBUG_CATEGORIES.add(c)
    # Ajustar el nivel del logger para que los mensajes DEBUG se muestren cuando hay categorías activas
    if GLOBAL_DEBUG_CATEGORIES:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

# Inicializar desde variable de entorno VISION_DEBUG (opcional)
env_debug = os.environ.get('VISION_DEBUG')
if env_debug:
    set_global_debug_categories(env_debug)

class RaceSystem:
    def __init__(self, camera_idx=None, resolution=None, finish_line=None):
        # Inicialización de cámara
        # En Windows, cv2.CAP_DSHOW suele ser más rápido para inicializar
        # Leer configuración por defecto desde config si no se pasan
        try:
            import config
        except Exception:
            config = None

        if camera_idx is None:
            camera_idx = getattr(config, 'CAMERA_IDX', 0) if config else 0

        if resolution is None:
            resolution = getattr(config, 'CAMERA_RESOLUTION', (640, 480)) if config else (640, 480)

        if finish_line is None:
            finish_line = getattr(config, 'FINISH_LINE', ((100, 240), (540, 240))) if config else ((100, 240), (540, 240))

        # Guardar parámetros para poder reinicializar la cámara al start()/stop()
        self.camera_idx = camera_idx
        self.resolution = resolution

        # No abrir la cámara aquí: la abriremos al llamar a start(),
        # así la cámara permanece apagada hasta que el detector se active.
        self.cap = None
        
        # Detector AprilTag (Familia 16h5 para velocidad/distancia)
        self.at_detector = Detector(
            families='tag16h5',
            nthreads=4,
            # Ajustes por defecto más permisivos para detección en movimiento.
            # "quad_decimate" más bajo procesa a mayor resolución (más lento,
            # pero detecta tags pequeños y en movimiento mejor).
            quad_decimate=0.7,
            # Algo de blur previo puede ayudar en condiciones con ruido/motion-blur
            quad_sigma=0.8,
            refine_edges=1,
            # Aumentar ligeramente el sharpening para ayudar al decodificado
            decode_sharpening=0.5,
            debug=0
        )

        self.running = False
        self.lock = Lock()
        self.frame_out = None
        # FPS tracking (EMA)
        self._last_frame_time = None
        self.fps_ema = None
        self._fps_alpha = 0.2
        # Cuando `enabled` es False se evita llamar al callback de vueltas
        self.enabled = True
        # Hilo que procesa frames
        self._thread = None
        # Socket usado como lock (bind a localhost:DETECTOR_LOCK_PORT)
        self._lock_sock = None
        
        # Línea de meta (Coordenadas X1, Y1, X2, Y2)
        # Se debería poder configurar desde la UI
        self.finish_line = finish_line
        
        # Estado de seguimiento
        # última posición confirmada (usada para comparar prev->current en cruces)
        self.last_confirmed = {}  # {tag_id: (center_tuple, timestamp)}
        # última posición vista (no necesariamente confirmada)
        self.last_seen = {}
        self.lap_timers = {}     # {tag_id: last_crossing_time}
        self.min_lap_time = 2.0  # Segundos de debounce
        # Conjunto opcional de tags permitidos (solo estos se procesan)
        # Si es None -> se procesan todos los tags detectados
        self.allowed_tags = None
        # Contadores y umbrales para reducir falsos positivos
        self.detection_counts = {}  # {tag_id: consecutive_frames_seen}
        self.min_detection_frames = 1  # cuántos frames consecutivos requiere confirmar
        # Reducir area mínima para que tags levemente borrosos/más pequeños sigan detectándose
        self.min_tag_area = 150  # área mínima en píxels para considerar un tag real
        # Umbral de decision_margin: la escala depende del detector; valores pequeños (ej 0-5)
        # parecen comunes en tu cámara; usar un umbral modesto para filtrar lo más débil.
        # Permitir decision_margin más bajo para no filtrar detecciones en movimiento
        self.min_decision_margin = 1.0  # umbral mínimo de decision_margin del detector
        self.max_hamming = 1  # máximo hamming aceptable
        # Parámetros para detectar pases rápidos (fallback)
        # Si un tag aparece solo en 1 frame pero existe una posición confirmada
        # inmediatamente anterior, permitimos comprobar cruce entre la confirmada
        # y la vista actual para capturar pases rápidos.
        self.allow_quick_pass = True
        self.quick_pass_time = 0.35  # segundos: ventana máxima entre prev confirmada y vista actual
        
        # Callbacks para notificar a la app principal
        self.on_lap_callback = None
        # Debug categories a nivel de instancia (complementan las globales)
        # Si no está vacío, su presencia habilita logs de la categoría además de las globales
        self.debug_categories = set()
        # CLAHE para mejorar contraste adaptativo antes de detección (útil en movimiento)
        try:
            # clipLimit y tileGridSize son conservadores para no introducir artefactos
            self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        except Exception:
            self._clahe = None
        # Valor devuelto por el último autotune (informativo)
        self._last_autotune = None

    def set_debug_categories(self, categories):
        """Establecer categorías de debug para esta instancia (lista o comma string).

        Para desactivar: pasar None o lista vacía.
        """
        if categories is None:
            self.debug_categories.clear()
            # si no hay categorías globales activas, dejar logger en INFO
            if not GLOBAL_DEBUG_CATEGORIES:
                logger.setLevel(logging.INFO)
            return
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(',') if c.strip()]
        self.debug_categories = set(categories)
        # si hay categorías a nivel de instancia, habilitar DEBUG para ver los mensajes
        if self.debug_categories:
            logger.setLevel(logging.DEBUG)
        else:
            if not GLOBAL_DEBUG_CATEGORIES:
                logger.setLevel(logging.INFO)

    def _dbg_on(self, category):
        return (category in self.debug_categories) or (category in GLOBAL_DEBUG_CATEGORIES)

    def _dbg(self, category, msg, *args, **kwargs):
        if self._dbg_on(category):
            logger.debug(msg, *args, **kwargs)

    def _set_cam_prop(self, prop, value, name):
        """Intenta establecer una propiedad de la cámara y notifica si falla."""
        if value != -1:
            try:
                self.cap.set(prop, value)
                print(f"Cámara: {name} establecido a {value}.")
            except Exception as e:
                print(f"Cámara: No se pudo establecer {name} a {value}. Error: {e}")

    def start(self):
        if self.running:
            return
        # Intentar adquirir lock local para evitar duplicados entre procesos
        try:
            port = getattr(config, 'DETECTOR_LOCK_PORT', 57001)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', int(port)))
            s.listen(1)
            self._lock_sock = s
        except OSError as e:
            # Si el bind falla, otro proceso ya tiene la cámara/lock
            print(f"No se inicia detector: puerto lock en uso ({e})")
            return
            
        # Si la cámara no está abierta, (re)abrirla
        try:
            if not (self.cap and getattr(self.cap, 'isOpened', lambda: False)()):
                self.cap = cv2.VideoCapture(self.camera_idx, cv2.CAP_DSHOW)

                # --- Configuración de la Cámara ---
                # Básica
                self._set_cam_prop(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0], "Ancho")
                self._set_cam_prop(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1], "Alto")
                self._set_cam_prop(cv2.CAP_PROP_FPS, config.CAMERA_FPS, "FPS")
                
                # Avanzada (depende de la cámara/driver)
                self._set_cam_prop(cv2.CAP_PROP_AUTOFOCUS, config.CAMERA_AUTOFOCUS, "Autoenfoque")
                self._set_cam_prop(cv2.CAP_PROP_FOCUS, config.CAMERA_FOCUS, "Enfoque")
                self._set_cam_prop(cv2.CAP_PROP_AUTO_EXPOSURE, config.CAMERA_AUTO_EXPOSURE, "Exposición Automática")
                self._set_cam_prop(cv2.CAP_PROP_EXPOSURE, config.CAMERA_EXPOSURE, "Exposición")
                self._set_cam_prop(cv2.CAP_PROP_GAIN, config.CAMERA_GAIN, "Ganancia")
                self._set_cam_prop(cv2.CAP_PROP_BRIGHTNESS, config.CAMERA_BRIGHTNESS, "Brillo")
                self._set_cam_prop(cv2.CAP_PROP_CONTRAST, config.CAMERA_CONTRAST, "Contraste")
                logger.info(f"Camara abierta idx={self.camera_idx} res={self.resolution} FPS={config.CAMERA_FPS}")

        except Exception as e:
            print(f"Error fatal al abrir o configurar la cámara: {e}")
            # Liberar el lock si la cámara falla
            if self._lock_sock:
                self._lock_sock.close()
                self._lock_sock = None
            return

        self.running = True
        t = Thread(target=self._process_loop)
        t.daemon = True
        t.start()
        self._thread = t
        logger.info(f"Detector thread iniciado en PID {os.getpid()}")

    def _intersect(self, p1, p2, p3, p4):
        """
        Comprobar si los segmentos p1-p2 y p3-p4 se intersectan.
        p* son tuplas (x, y).
        """
        def orientation(a, b, c):
            # Orientación de tripleta (a,b,c)
            # Devuelve >0 si c está a la izquierda de ab, <0 si a la derecha, 0 colineal
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on_segment(a, b, c):
            # Comprueba si punto b está en el segmento ac
            return (min(a[0], c[0]) <= b[0] <= max(a[0], c[0]) and
                    min(a[1], c[1]) <= b[1] <= max(a[1], c[1]))

        o1 = orientation(p1, p2, p3)
        o2 = orientation(p1, p2, p4)
        o3 = orientation(p3, p4, p1)
        o4 = orientation(p3, p4, p2)

        # Casos generales
        if (o1 > 0 and o2 < 0 or o1 < 0 and o2 > 0) and (o3 > 0 and o4 < 0 or o3 < 0 and o4 > 0):
            return True

        # Casos colineales: comprobar si un punto está sobre el segmento
        if o1 == 0 and on_segment(p1, p3, p2):
            return True
        if o2 == 0 and on_segment(p1, p4, p2):
            return True
        if o3 == 0 and on_segment(p3, p1, p4):
            return True
        if o4 == 0 and on_segment(p3, p2, p4):
            return True

        return False

    def _process_loop(self):
        while self.running:
            if not (self.cap and getattr(self.cap, 'isOpened', lambda: False)()):
                # Si la cámara no está abierta, esperar un poco
                time.sleep(0.05)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Conversión a gris para detección
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Aplicar CLAHE (si está disponible) para mejorar contraste y ayudar
            # a detectar tags en movimiento/condiciones de bajo contraste.
            if getattr(self, '_clahe', None) is not None:
                try:
                    gray = self._clahe.apply(gray)
                except Exception:
                    # Si CLAHE falla, continuar con la imagen en gris
                    pass
            
            # Detección de tags
            tags = self.at_detector.detect(gray)
            if tags:
                self._dbg('detection', f"Detected {len(tags)} tags")
            
            current_time = time.time()
            
            # Visualización: Dibujar línea de meta
            try:
                cv2.line(frame, self.finish_line[0], self.finish_line[1], (0, 255, 0), 2)
            except Exception as e:
                logger.exception(f"Error dibujando línea de meta con finish_line={self.finish_line}: {e}")

            detected_this_frame = set()
            for tag in tags:
                tag_id = tag.tag_id
                detected_this_frame.add(tag_id)
                # filtros básicos: decision_margin, hamming, área del polígono
                try:
                    dm = getattr(tag, 'decision_margin', None)
                    ham = getattr(tag, 'hamming', None)
                    corners = getattr(tag, 'corners', None)
                except Exception:
                    dm = None; ham = None; corners = None

                # Calcular área si tenemos corners
                area = 0
                if corners is not None:
                    try:
                        pts = [(float(p[0]), float(p[1])) for p in corners]
                        # shoelace
                        a = 0.0
                        for i in range(len(pts)):
                            x1, y1 = pts[i]
                            x2, y2 = pts[(i+1) % len(pts)]
                            a += x1*y2 - x2*y1
                        area = abs(a) / 2.0
                    except Exception:
                        area = 0

                if dm is not None and dm < self.min_decision_margin:
                    self._dbg('filter', f"Tag {tag_id} ignorado por baja decision_margin={dm}")
                    self.detection_counts[int(tag_id)] = 0
                    continue
                if ham is not None and ham > self.max_hamming:
                    self._dbg('filter', f"Tag {tag_id} ignorado por hamming={ham}")
                    self.detection_counts[int(tag_id)] = 0
                    continue
                if area and area < self.min_tag_area:
                    self._dbg('filter', f"Tag {tag_id} ignorado por area pequeña={area}")
                    self.detection_counts[int(tag_id)] = 0
                    continue
                # Filtrar tags no permitidos si se ha provisto una lista
                try:
                    if self.allowed_tags is not None and int(tag_id) not in self.allowed_tags:
                        self._dbg('filter', f"Tag {tag_id} ignorado: no está en allowed_tags")
                        # Actualizar última vista para evitar ruido repetido
                        self.last_seen[tag_id] = ((int(tag.center[0]), int(tag.center[1])), current_time)
                        continue
                except Exception:
                    # En caso de problemas al castear/comprobar, seguir procesando normalmente
                    logger.exception(f"Error comprobando allowed_tags para tag {tag_id}")
                    pass
                center = (int(tag.center[0]), int(tag.center[1]))

                # Contador de frames consecutivos para confirmar detección
                self.detection_counts[tag_id] = self.detection_counts.get(tag_id, 0) + 1
                if self.detection_counts.get(tag_id, 0) < self.min_detection_frames:
                    self._dbg('detection', f"Tag {tag_id} visto {self.detection_counts.get(tag_id)} / {self.min_detection_frames} frames, esperando confirmación")
                    # Actualizar última posición vista pero no la confirmada
                    self.last_seen[tag_id] = (center, current_time)
                    # Intento fallback para pases rápidos: si existe una posición confirmada
                    # reciente y la ventana de tiempo es pequeña, comprobar intersección
                    if self.allow_quick_pass:
                        prev = self.last_confirmed.get(tag_id)
                        if prev is not None:
                            prev_center, prev_time = prev
                            # Si la confirmada fue reciente (no hace mucho desde prev_time)
                            if (current_time - prev_time) <= self.quick_pass_time:
                                try:
                                    crossed_quick = self._intersect(prev_center, center, self.finish_line[0], self.finish_line[1])
                                    self._dbg('intersection', f"Quick-pass intersection for tag {tag_id}: prev={prev_center}, now={center}, crossed={crossed_quick}")
                                except Exception as e:
                                    logger.exception(f"Error quick-pass intersection for tag {tag_id}: {e}")
                                    crossed_quick = False

                                if crossed_quick:
                                    last_lap = self.lap_timers.get(tag_id, 0)
                                    # Debounce check
                                    if (current_time - last_lap) > self.min_lap_time:
                                        lap_duration = current_time - last_lap
                                        self.lap_timers[tag_id] = current_time
                                        logger.info(f"Tag {tag_id} quick-pass lap detected. duration={lap_duration:.3f}s")
                                        if last_lap > 0 and self.on_lap_callback and self.enabled:
                                            try:
                                                self._dbg('callback', f"Invocando callback (quick-pass) para tag {tag_id}")
                                                self.on_lap_callback(tag_id, lap_duration)
                                            except Exception as e:
                                                logger.exception(f"Error en on_lap_callback quick-pass para tag {tag_id}: {e}")
                                    # Actualizar confirmada y continuar
                                    self.last_confirmed[tag_id] = (center, current_time)
                                    # reset contador
                                    self.detection_counts[tag_id] = 0
                                    continue

                    # No dibujar nada hasta estar confirmado para evitar falsos positivos visibles
                    continue

                # Ahora el tag está confirmado: dibujar contorno usando corners si están disponibles
                try:
                    corners = getattr(tag, 'corners', None)
                    if corners is not None:
                        pts = np.array([[int(p[0]), int(p[1])] for p in corners], dtype=np.int32)
                        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                except Exception:
                    # fallback: dibujar centro
                    cv2.circle(frame, center, 4, (0, 0, 255), -1)

                # Etiqueta del ID
                try:
                    cv2.putText(frame, f"ID:{tag_id}", (center[0] + 6, center[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                except Exception:
                    pass

                # Lógica de Vuelta: usar la última posición confirmada como 'prev'
                prev = self.last_confirmed.get(tag_id)
                if prev is None:
                    # No hay posición previa confirmada: establecer la confirmada actual y continuar
                    self.last_confirmed[tag_id] = (center, current_time)
                    continue

                prev_center, prev_time = prev

                # Verificar si cruzó la línea virtual
                try:
                    crossed = self._intersect(prev_center, center, self.finish_line[0], self.finish_line[1])
                    self._dbg('intersection', f"Intersección check for tag {tag_id}: prev={prev_center}, now={center}, line={self.finish_line}, crossed={crossed}")
                except Exception as e:
                    logger.exception(f"Error comprobando intersección para tag {tag_id}: {e}")
                    crossed = False

                if crossed:
                    last_lap = self.lap_timers.get(tag_id, 0)
                    logger.info(f"Tag {tag_id} cruzó la línea. prev={prev_center} now={center} last_lap={last_lap}")

                    # Debounce check
                    if (current_time - last_lap) > self.min_lap_time:
                        lap_duration = current_time - last_lap
                        self.lap_timers[tag_id] = current_time
                        logger.info(f"Tag {tag_id} lap detected. duration={lap_duration:.3f}s")

                        # Si no es la primera detección (salida), registrar vuelta
                        if last_lap > 0 and self.on_lap_callback and self.enabled:
                            try:
                                self._dbg('callback', f"Invocando callback de vuelta para tag {tag_id}")
                                self.on_lap_callback(tag_id, lap_duration)
                                # Feedback visual en el frame
                                cv2.circle(frame, center, 15, (255, 255, 0), -1)
                            except Exception as e:
                                logger.exception(f"Error en on_lap_callback para tag {tag_id}: {e}")
                    else:
                        # Caso: debounce (muy próxima a la última vuelta)
                        if last_lap == 0:
                            # Primera detección (Start)
                            self.lap_timers[tag_id] = current_time
                            logger.info(f"Tag {tag_id} primer cruce detectado (inicio), timestamp registrado")
                        else:
                            logger.debug(f"Tag {tag_id} cruce ignorado por debounce: {current_time - last_lap:.3f}s desde última")

                # Actualizar posición confirmada para el siguiente frame
                self.last_confirmed[tag_id] = (center, current_time)

            # Reseteo de counters para tags que no aparecieron este frame
            try:
                for tid in list(self.detection_counts.keys()):
                    if tid not in detected_this_frame:
                        self.detection_counts[tid] = 0
            except Exception:
                pass

            # Comprimir frame para streaming MJPEG
            # Dibujar contador de FPS en la esquina superior izquierda
            try:
                if self.fps_ema is not None:
                    cv2.putText(frame, f"FPS:{self.fps_ema:.1f}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            except Exception:
                pass

            with self.lock:
                _, buffer = cv2.imencode('.jpg', frame)
                self.frame_out = buffer.tobytes()
            # Actualizar FPS EMA (después de procesar/encoder)
            try:
                if self._last_frame_time is None:
                    self._last_frame_time = current_time
                else:
                    dt = max(1e-6, current_time - self._last_frame_time)
                    inst_fps = 1.0 / dt
                    if self.fps_ema is None:
                        self.fps_ema = inst_fps
                    else:
                        self.fps_ema = (1.0 - self._fps_alpha) * self.fps_ema + self._fps_alpha * inst_fps
                    self._last_frame_time = current_time
            except Exception:
                pass
            # Pequeña pausa para no saturar la CPU
            time.sleep(0.005)

    def stop(self):
        """Detener el hilo y liberar la cámara."""
        # Desactivar notificaciones de vuelta inmediatamente
        self.enabled = False
        # Marcar para que el hilo termine
        self.running = False
        # Liberar la cámara lo antes posible para desbloquear read()
        try:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                try:
                    # En algunos sistemas hay que cerrar el descriptor
                    del self.cap
                except Exception:
                    pass
                self.cap = None
        except Exception:
            pass
        # Liberar el socket-lock si lo tenemos
        try:
            if self._lock_sock:
                try:
                    self._lock_sock.close()
                except Exception:
                    pass
                self._lock_sock = None
        except Exception:
            pass

        # Esperar al hilo (con timeout corto)
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
        except Exception:
            pass

    def set_allowed_tags(self, tags):
        """Establecer el conjunto de tag IDs permitidos.

        Pasar `None` para desactivar el filtrado y permitir todos los tags.
        """
        try:
            if tags is None:
                self.allowed_tags = None
            else:
                # Normalizar a set de ints
                self.allowed_tags = set(int(t) for t in tags)
            logger.info(f"allowed_tags actualizado: {self.allowed_tags}")
        except Exception as e:
            logger.exception(f"Error estableciendo allowed_tags: {e}")

    def get_detector_config(self):
        """Devolver la configuración relevante del detector para mostrar/editar en UI."""
        try:
            return {
                'quad_decimate': getattr(self.at_detector, 'quad_decimate', None) if hasattr(self.at_detector, 'quad_decimate') else None,
                'quad_sigma': getattr(self.at_detector, 'quad_sigma', None) if hasattr(self.at_detector, 'quad_sigma') else None,
                'decode_sharpening': getattr(self.at_detector, 'decode_sharpening', None) if hasattr(self.at_detector, 'decode_sharpening') else None,
                'min_tag_area': self.min_tag_area,
                'min_decision_margin': self.min_decision_margin,
                'min_detection_frames': self.min_detection_frames,
                'allow_quick_pass': bool(self.allow_quick_pass),
                'quick_pass_time': float(self.quick_pass_time)
            }
        except Exception as e:
            logger.exception(f"Error obteniendo detector config: {e}")
            return {}

    def update_detector_config(self, cfg: dict):
        """Aplicar configuración al detector en caliente.

        cfg puede contener: quad_decimate, quad_sigma, decode_sharpening,
        min_tag_area, min_decision_margin, min_detection_frames,
        allow_quick_pass, quick_pass_time
        """
        try:
            # Normalizar y aplicar umbrales locales
            changed_detector = False
            qd = cfg.get('quad_decimate')
            qs = cfg.get('quad_sigma')
            ds = cfg.get('decode_sharpening')

            # Intentar parsear numéricos si vienen como strings
            def _f(v):
                try:
                    return float(v) if v is not None else None
                except Exception:
                    return None

            def _i(v):
                try:
                    return int(v) if v is not None else None
                except Exception:
                    return None

            qd_v = _f(qd)
            qs_v = _f(qs)
            ds_v = _f(ds)

            # Revisar si hay que recrear el detector (parámetros de construcción cambiaron)
            if qd_v is not None and qd_v != getattr(self.at_detector, 'quad_decimate', None):
                changed_detector = True
            if qs_v is not None and qs_v != getattr(self.at_detector, 'quad_sigma', None):
                changed_detector = True
            if ds_v is not None and ds_v != getattr(self.at_detector, 'decode_sharpening', None):
                changed_detector = True

            # Aplicar ajustes no relacionados con la instancia del detector
            mta = _i(cfg.get('min_tag_area'))
            if mta is not None:
                self.min_tag_area = mta
            mdm = _f(cfg.get('min_decision_margin'))
            if mdm is not None:
                self.min_decision_margin = mdm
            mdf = _i(cfg.get('min_detection_frames'))
            if mdf is not None:
                self.min_detection_frames = max(1, mdf)
            aqp = cfg.get('allow_quick_pass')
            if aqp is not None:
                # aceptar bool o 'true'/'false' strings
                if isinstance(aqp, str):
                    self.allow_quick_pass = aqp.lower() in ('1', 'true', 'yes', 'on')
                else:
                    self.allow_quick_pass = bool(aqp)
            qpt = _f(cfg.get('quick_pass_time'))
            if qpt is not None:
                self.quick_pass_time = float(qpt)

            # Si hay cambios que requieren recrear el Detector, hacerlo ahora
            if changed_detector:
                # Construir parámetros basados en actuales y valores nuevos
                new_qd = qd_v if qd_v is not None else getattr(self.at_detector, 'quad_decimate', 1)
                new_qs = qs_v if qs_v is not None else getattr(self.at_detector, 'quad_sigma', 0.0)
                new_ds = ds_v if ds_v is not None else getattr(self.at_detector, 'decode_sharpening', 0.25)

                try:
                    new_detector = Detector(
                        families='tag16h5',
                        nthreads=4,
                        quad_decimate=new_qd,
                        quad_sigma=new_qs,
                        refine_edges=1,
                        decode_sharpening=new_ds,
                        debug=0
                    )
                    # Asignar de forma atómica; detect() en curso puede terminar sin problemas
                    self.at_detector = new_detector
                    logger.info(f"Detector recreado con quad_decimate={new_qd} quad_sigma={new_qs} decode_sharpening={new_ds}")
                except Exception as e:
                    logger.exception(f"Error recreando detector con nuevos parámetros: {e}")

            return self.get_detector_config()
        except Exception as e:
            logger.exception(f"Error aplicando detector config: {e}")
            return {}

    def auto_tune_camera(self, mode='focus'):
        """Intento simple de autotune para nitidez.

        mode 'focus': si la cámara soporta `CAP_PROP_FOCUS`, barrido rápido
        y búsqueda por máxima varianza de Laplaciano para estimar el enfoque óptimo.
        Si no hay soporte, se intenta activar AutoFocus brevemente.

        Devuelve dict con el resultado y el valor de foco aplicado (si procede).
        """
        result = {'ok': False, 'reason': None, 'focus': None}
        try:
            if not (self.cap and getattr(self.cap, 'isOpened', lambda: False)()):
                result['reason'] = 'camera_not_open'
                return result

            # Intentar usar enfoque manual si está soportado
            # Rango asumido 0-255; haremos un barrido grosero y luego refinado.
            try:
                # Probar si set/get focus funciona
                got = self.cap.get(cv2.CAP_PROP_FOCUS)
                # Algunos drivers devuelven -1 si no soportado
                if got is None:
                    got = -1
            except Exception:
                got = -1

            if got >= 0:
                # Barrido grosero
                best_focus = int(got)
                best_score = -1.0
                # coarse sweep
                coarse = list(range(0, 256, 25))
                for v in coarse:
                    try:
                        self.cap.set(cv2.CAP_PROP_FOCUS, float(v))
                        # leer algunos frames para estabilizar
                        time.sleep(0.06)
                        ret, f = self.cap.read()
                        if not ret:
                            continue
                        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                        score = cv2.Laplacian(gray, cv2.CV_64F).var()
                        if score > best_score:
                            best_score = score
                            best_focus = v
                    except Exception:
                        continue

                # refine around best
                start = max(0, best_focus - 25)
                end = min(255, best_focus + 25)
                for v in range(start, end + 1, 5):
                    try:
                        self.cap.set(cv2.CAP_PROP_FOCUS, float(v))
                        time.sleep(0.04)
                        ret, f = self.cap.read()
                        if not ret:
                            continue
                        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                        score = cv2.Laplacian(gray, cv2.CV_64F).var()
                        if score > best_score:
                            best_score = score
                            best_focus = v
                    except Exception:
                        continue

                # Aplicar mejor foco encontrado
                try:
                    self.cap.set(cv2.CAP_PROP_FOCUS, float(best_focus))
                except Exception:
                    pass
                result.update({'ok': True, 'reason': 'focus_applied', 'focus': int(best_focus), 'score': float(best_score)})
                self._last_autotune = result
                logger.info(f"Autotune focus applied: {result}")
                return result
            else:
                # fallback: intentar activar autofocus brevemente
                try:
                    self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                    time.sleep(1.0)
                    self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                    result.update({'ok': True, 'reason': 'autofocus_toggled'})
                    self._last_autotune = result
                    return result
                except Exception as e:
                    result['reason'] = 'autofocus_failed'
                    result['error'] = str(e)
                    return result
        except Exception as e:
            logger.exception(f"Error en auto_tune_camera: {e}")
            result['reason'] = 'exception'
            result['error'] = str(e)
            return result

    def get_frame(self):
        with self.lock:
            return self.frame_out