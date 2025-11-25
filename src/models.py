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
    
class Championship(db.Model):
    """Un campeonato (p. ej. Season 2025 de una categoría)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seasons = db.relationship('Season', backref='championship', lazy='dynamic')

class Season(db.Model):
    """Una temporada dentro de un campeonato."""
    id = db.Column(db.Integer, primary_key=True)
    championship_id = db.Column(db.Integer, db.ForeignKey('championship.id'))
    name = db.Column(db.String(120), nullable=False)  # e.g. '2025' o 'Summer Series'
    year = db.Column(db.Integer, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    settings = db.Column(db.JSON, nullable=True)
    races = db.relationship('RaceEvent', backref='season', lazy='dynamic')
    registrations = db.relationship('SeasonRegistration', backref='season', lazy='dynamic')
class Session(db.Model):
    """Sesión de carrera (Práctica, Qualy, Carrera)."""
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))
    # Opcional: relacionar esta sesión con una carrera concreta (RaceEvent)
    race_id = db.Column(db.Integer, db.ForeignKey('race_event.id'), nullable=True)
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


class RaceEvent(db.Model):
    """Una carrera dentro de una temporada (por ejemplo: Round 1 - Circuito X)."""
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'))
    name = db.Column(db.String(120), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=True)
    scheduled_date = db.Column(db.DateTime, nullable=True)
    order = db.Column(db.Integer, default=0)  # orden dentro de la temporada
    settings = db.Column(db.JSON, nullable=True)
    sessions = db.relationship('Session', backref='race_event', lazy='dynamic')
    registrations = db.relationship('RaceRegistration', backref='race', lazy='dynamic')


class SeasonRegistration(db.Model):
    """Un piloto inscrito en una temporada (se apunta a la temporada completa)."""
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'))
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    number = db.Column(db.String(10), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    driver = db.relationship('Driver')


class RaceRegistration(db.Model):
    """Participación de un piloto en una carrera concreta (RaceEvent).
       Permite marcar inscripción confirmada, si comenzó la carrera y la posición final.
    """
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race_event.id'))
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    confirmed = db.Column(db.Boolean, default=False)
    did_start = db.Column(db.Boolean, default=False)
    finish_position = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Float, nullable=True)

    driver = db.relationship('Driver')