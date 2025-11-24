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

# Línea de meta por defecto (x1,y1),(x2,y2)
FINISH_LINE = ((100, 240), (540, 240))

# Puerto local usado como candado para evitar que múltiples procesos
# inicien la cámara simultáneamente. Si el bind falla, otro proceso
# ya tiene la cámara abierta.
DETECTOR_LOCK_PORT = int(os.environ.get('DETECTOR_LOCK_PORT', 57001))
