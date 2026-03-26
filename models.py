from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='operador')

class Alumno(db.Model):
    __tablename__ = 'alumnos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    clase = db.Column(db.String(50))
    horario = db.Column(db.String(50))
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    
    ventas = db.relationship('Venta', backref='alumno', lazy=True)
    asistencias = db.relationship('AsistenciaClase', backref='alumno', lazy=True)

class Clase(db.Model):
    __tablename__ = 'clases'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    dia = db.Column(db.String(20))
    hora = db.Column(db.String(10))
    profesor = db.Column(db.String(100))
    capacidad = db.Column(db.Integer, default=20)
    
    asistentes = db.relationship('AsistenciaClase', backref='clase', lazy=True)

class AsistenciaClase(db.Model):
    __tablename__ = 'asistencia_clases'
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumnos.id'), nullable=False)
    clase_id = db.Column(db.Integer, db.ForeignKey('clases.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    subcategoria = db.Column(db.String(50))
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    talles = db.Column(db.String(100))
    colores = db.Column(db.String(200))
    imagen_url = db.Column(db.String(500))

class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumnos.id'), nullable=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    producto_nombre = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, default=1)
    talle = db.Column(db.String(10))
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    producto = db.relationship('Producto')
    usuario = db.relationship('User')

class CajaDiaria(db.Model):
    __tablename__ = 'caja_diaria'
    
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=date.today, unique=True)
    apertura = db.Column(db.DateTime, default=datetime.utcnow)
    cierre = db.Column(db.DateTime)
    monto_inicial = db.Column(db.Float, default=0)
    monto_final = db.Column(db.Float)
    ventas_totales = db.Column(db.Float, default=0)
    estado = db.Column(db.String(20), default='abierta')
    usuario_apertura_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    usuario_cierre_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    usuario_apertura = db.relationship('User', foreign_keys=[usuario_apertura_id])
    usuario_cierre = db.relationship('User', foreign_keys=[usuario_cierre_id])