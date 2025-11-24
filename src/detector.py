import cv2
import time
import numpy as np
from pupil_apriltags import Detector
from threading import Thread, Lock
import socket
import config
import os

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
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=1,
            decode_sharpening=0.25,
            debug=0
        )

        self.running = False
        self.lock = Lock()
        self.frame_out = None
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
        self.last_positions = {} # {tag_id: (center_tuple, timestamp)}
        self.lap_timers = {}     # {tag_id: last_crossing_time}
        self.min_lap_time = 2.0  # Segundos de debounce
        
        # Callbacks para notificar a la app principal
        self.on_lap_callback = None

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
        print(f"Detector thread iniciado en PID {os.getpid()}")

    def _intersect(self, p1, p2, p3, p4):
        """
        Comprobar si los segmentos p1-p2 y p3-p4 se intersectan.
        p* son tuplas (x, y).
        """
        def orientation(a, b, c):
            # Orientación de tripleta (a,b,c)
            return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])

        def on_segment(a, b, c):
            return (min(a[0], c[0]) <= b[0] <= max(a[0], c[0]) and
                    min(a[1], c[1]) <= b[1] <= max(a[1], c[1]))

        o1 = orientation(p1, p2, p3)
        o2 = orientation(p1, p2, p4)
        o3 = orientation(p3, p4, p1)
        o4 = orientation(p3, p4, p2)

        if o1 == 0 and on_segment(p1, p3, p2):
            return True
        if o2 == 0 and on_segment(p1, p4, p2):
            return True
        if o3 == 0 and on_segment(p3, p1, p4):
            return True
        if o4 == 0 and on_segment(p3, p2, p4):
            return True

        return (o1 * o2 < 0) and (o3 * o4 < 0)

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
            
            # Detección de tags
            tags = self.at_detector.detect(gray)
            
            current_time = time.time()
            
            # Visualización: Dibujar línea de meta
            cv2.line(frame, self.finish_line[0], self.finish_line[1], (0, 255, 0), 2)

            for tag in tags:
                tag_id = tag.tag_id
                center = (int(tag.center[0]), int(tag.center[1]))
                
                # Dibujar ID y centro
                cv2.circle(frame, center, 4, (0, 0, 255), -1)
                cv2.putText(frame, f"ID:{tag_id}", (center[0] + 6, center[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Lógica de Vuelta
                if tag_id in self.last_positions:
                    prev_center, prev_time = self.last_positions[tag_id]
                    
                    # Verificar si cruzó la línea virtual
                    if self._intersect(prev_center, center, self.finish_line[0], self.finish_line[1]):
                        last_lap = self.lap_timers.get(tag_id, 0)
                        
                        # Debounce check
                        if (current_time - last_lap) > self.min_lap_time:
                            lap_duration = current_time - last_lap
                            self.lap_timers[tag_id] = current_time
                            
                            # Si no es la primera detección (salida), registrar vuelta
                            if last_lap > 0 and self.on_lap_callback and self.enabled:
                                self.on_lap_callback(tag_id, lap_duration)
                                # Feedback visual en el frame
                                cv2.circle(frame, center, 15, (255, 255, 0), -1)
                        
                        elif last_lap == 0:
                            # Primera detección (Start)
                            self.lap_timers[tag_id] = current_time

                # Actualizar posición para el siguiente frame
                self.last_positions[tag_id] = (center, current_time)

            # Comprimir frame para streaming MJPEG
            with self.lock:
                _, buffer = cv2.imencode('.jpg', frame)
                self.frame_out = buffer.tobytes()
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

    def get_frame(self):
        with self.lock:
            return self.frame_out