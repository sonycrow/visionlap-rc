from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Driver(db.Model):
    """Representa a un piloto y su identificador físico (Tag)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    nickname = db.Column(db.String(64), unique=True, nullable=False)
    # ID del AprilTag (familia 16h5: 0-29)
    tag_id = db.Column(db.Integer, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'nickname': self.nickname,
            'tag_id': self.tag_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Track(db.Model):
    """Configuración del circuito."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    record_lap = db.Column(db.Float, nullable=True)
    
class Session(db.Model):
    """Sesión de carrera (Práctica, Qualy, Carrera)."""
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))
    type = db.Column(db.String(20), default='practice') # practice, qualy, race
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    laps = db.relationship('Lap', backref='session', lazy='dynamic')

class Lap(db.Model):
    """Registro individual de una vuelta."""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    lap_number = db.Column(db.Integer, nullable=False)
    lap_time = db.Column(db.Float, nullable=False) # Segundos con decimales
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sector_1 = db.Column(db.Float, nullable=True) # Extensible a sectores
    is_valid = db.Column(db.Boolean, default=True)

    driver = db.relationship('Driver')