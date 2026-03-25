from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'          # ← Esta línea es la clave

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='operador')

class Alumno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni_fin = db.Column(db.String(3), nullable=False) # Últimos 3 del DNI
    email = db.Column(db.String(100))
    deuda = db.Column(db.Boolean, default=False)
    clase = db.Column(db.String(50)) # Boxeo, Funcional, Personalizado
    ultima_asistencia = db.Column(db.DateTime)

class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20)) # 'venta' o 'gasto'
    item = db.Column(db.String(100)) # 'Bebida', 'Guantes', 'Alquiler'
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)