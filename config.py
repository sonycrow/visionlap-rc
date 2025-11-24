import os

# Configuración básica de la aplicación
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///visionlap.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Clave secreta para sesiones/CSRF
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-to-a-secure-value')

# Parámetros de cámara por defecto
CAMERA_IDX = int(os.environ.get('CAMERA_IDX', 0))
CAMERA_RESOLUTION = (int(os.environ.get('CAMERA_WIDTH', 640)), int(os.environ.get('CAMERA_HEIGHT', 480)))

# --- Parámetros avanzados de cámara ---
# NOTA: Estos parámetros dependen del driver y de la cámara. No todos los valores
# son soportados en todos los dispositivos. Un valor de -1 significa "no cambiar".

# Fotogramas por segundo (FPS)
CAMERA_FPS = int(os.environ.get('CAMERA_FPS', 30))

# Autoenfoque (1 para activar, 0 para desactivar y usar enfoque manual)
CAMERA_AUTOFOCUS = int(os.environ.get('CAMERA_AUTOFOCUS', -1))
# Enfoque manual (valores típicos 0-255). Solo funciona si el autoenfoque está desactivado.
CAMERA_FOCUS = int(os.environ.get('CAMERA_FOCUS', -1))

# Exposición automática (1 para modo manual, 3 para modo automático)
CAMERA_AUTO_EXPOSURE = int(os.environ.get('CAMERA_AUTO_EXPOSURE', -1))
# Valor de exposición (valores más bajos son más rápidos/oscuros). Solo si el modo es manual.
CAMERA_EXPOSURE = int(os.environ.get('CAMERA_EXPOSURE', -1))

# Ganancia de la imagen (puede ayudar en condiciones de poca luz)
CAMERA_GAIN = int(os.environ.get('CAMERA_GAIN', -1))
# Brillo de la imagen
CAMERA_BRIGHTNESS = int(os.environ.get('CAMERA_BRIGHTNESS', -1))
# Contraste de la imagen
CAMERA_CONTRAST = int(os.environ.get('CAMERA_CONTRAST', -1))

# Línea de meta (x1,y1),(x2,y2)
# Se define como una línea horizontal o vertical en la imagen de la cámara.
# Los valores por defecto definen una línea horizontal en el centro de una imagen de 640x480.
FINISH_LINE_X1 = int(os.environ.get('FINISH_LINE_X1', 100))
FINISH_LINE_Y1 = int(os.environ.get('FINISH_LINE_Y1', 240))
FINISH_LINE_X2 = int(os.environ.get('FINISH_LINE_X2', 540))
FINISH_LINE_Y2 = int(os.environ.get('FINISH_LINE_Y2', 240))
FINISH_LINE = ((FINISH_LINE_X1, FINISH_LINE_Y1), (FINISH_LINE_X2, FINISH_LINE_Y2))

# Puerto local usado como candado para evitar que múltiples procesos
# inicien la cámara simultáneamente. Si el bind falla, otro proceso
# ya tiene la cámara abierta.
DETECTOR_LOCK_PORT = int(os.environ.get('DETECTOR_LOCK_PORT', 57001))
