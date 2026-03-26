from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='operador')  # admin o operador

class Alumno(db.Model):
    __tablename__ = 'alumnos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    clase = db.Column(db.String(50))  # Boxeo, Funcional, Personalizado
    horario = db.Column(db.String(50))
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

class Clase(db.Model):
    __tablename__ = 'clases'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    dia = db.Column(db.String(20))  # Lunes, Martes, etc.
    hora = db.Column(db.String(10))  # 18:00, 19:00, etc.
    profesor = db.Column(db.String(100))
    capacidad = db.Column(db.Integer, default=20)

class Producto(db.Model):
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    categoria = db.Column(db.String(50))  # Bebidas, Equipamiento, Suplementos

class Venta(db.Model):
    __tablename__ = 'ventas'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    producto_nombre = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, default=1)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    producto = db.relationship('Producto')
    usuario = db.relationship('User')