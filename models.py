from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='operador')


class Alumno(db.Model):
    __tablename__ = 'alumno'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni_fin = db.Column(db.String(3), nullable=False)
    email = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    contacto_emergencia = db.Column(db.String(100))
    telefono_emergencia = db.Column(db.String(20))
    deuda = db.Column(db.Boolean, default=False)
    clase = db.Column(db.String(50))
    ultima_asistencia = db.Column(db.DateTime)
    
    # Campos para sistema de cuotas
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.Date)
    estado = db.Column(db.String(20), default='activo')
    plan = db.Column(db.String(20), default='mensual')
    valor_cuota = db.Column(db.Float, default=15000)
    
    def calcular_vencimiento(self):
        """Calcula próxima fecha de vencimiento basado en fecha de inscripción"""
        if self.fecha_inscripcion:
            if self.plan == 'mensual':
                return (self.fecha_inscripcion + relativedelta(months=1)).date()
            elif self.plan == 'trimestral':
                return (self.fecha_inscripcion + relativedelta(months=3)).date()
            elif self.plan == 'anual':
                return (self.fecha_inscripcion + relativedelta(years=1)).date()
        return date.today() + relativedelta(days=30)
    
    def esta_activo(self):
        """Verifica si el alumno está activo (no vencido y no suspendido)"""
        if self.estado == 'suspendido':
            return False
        if self.fecha_vencimiento:
            return date.today() <= self.fecha_vencimiento
        return True
    
    def dias_restantes(self):
        """Días restantes hasta vencimiento"""
        if self.fecha_vencimiento and self.esta_activo():
            dias = (self.fecha_vencimiento - date.today()).days
            return max(0, dias)
        return 0


class Pago(db.Model):
    __tablename__ = 'pagos'
    
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumno.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    periodo_desde = db.Column(db.Date)
    periodo_hasta = db.Column(db.Date)
    metodo_pago = db.Column(db.String(20))
    comprobante = db.Column(db.String(100))
    
    alumno = db.relationship('Alumno', backref=db.backref('pagos', lazy=True))


class Transaccion(db.Model):
    __tablename__ = 'transaccion'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20))
    item = db.Column(db.String(100))
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumno.id'), nullable=True)


class Asistencia(db.Model):
    __tablename__ = 'asistencias'
    
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumno.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    alumno = db.relationship('Alumno', backref=db.backref('asistencias', lazy=True))


class Config(db.Model):
    __tablename__ = 'config'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True)
    valor = db.Column(db.String(200))