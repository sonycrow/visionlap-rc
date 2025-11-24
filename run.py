from src.app import app, socketio, vision_system
from src.models import db
import os

if __name__ == '__main__':
    # Crear base de datos si no existe
    if not os.path.exists('visionlap.db'):
        with app.app_context():
            db.create_all()
            print('Base de datos creada.')

    # No iniciar el detector automáticamente aquí. Mantener debug=True
    # es útil durante el desarrollo, pero iniciar la cámara debe ocurrir
    # explícitamente (p. ej. pulsando el botón en la UI) para evitar que
    # procesos del reloader o del entorno lancen la cámara accidentalmente.
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
