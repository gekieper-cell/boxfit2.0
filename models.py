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

# ==================== CONFIGURACIÓN PRODUCTOS DESTACADOS ====================

class Configuracion(db.Model):
    __tablename__ = 'configuracion'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.String(20), default='text')
    descripcion = db.Column(db.String(200))
    
    @staticmethod
    def get(clave, default=None):
        import json
        config = Configuracion.query.filter_by(clave=clave).first()
        if config:
            if config.tipo == 'json':
                return json.loads(config.valor) if config.valor else default
            return config.valor
        return default
    
    @staticmethod
    def set(clave, valor, tipo='text', descripcion=''):
        import json
        config = Configuracion.query.filter_by(clave=clave).first()
        if config:
            config.valor = str(valor) if tipo != 'json' else json.dumps(valor)
            config.tipo = tipo
            config.descripcion = descripcion or config.descripcion
        else:
            config = Configuracion(
                clave=clave,
                valor=str(valor) if tipo != 'json' else json.dumps(valor),
                tipo=tipo,
                descripcion=descripcion
            )
            db.session.add(config)
        db.session.commit()

# ==================== CONFIGURACIÓN DEL SITIO ====================

class ConfiguracionSitio(db.Model):
    __tablename__ = 'configuracion_sitio'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.String(20), default='text')
    
    @staticmethod
    def get(clave, default=''):
        config = ConfiguracionSitio.query.filter_by(clave=clave).first()
        if config:
            return config.valor
        return default
    
    @staticmethod
    def set(clave, valor):
        config = ConfiguracionSitio.query.filter_by(clave=clave).first()
        if config:
            config.valor = valor
        else:
            config = ConfiguracionSitio(clave=clave, valor=valor)
            db.session.add(config)
        db.session.commit()

# ==================== GASTOS ====================

class Gasto(db.Model):
    __tablename__ = 'gastos'
    
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)
    comprobante = db.Column(db.String(100))
    proveedor = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    usuario = db.relationship('User')

# ==================== ALQUILER ====================

class Alquiler(db.Model):
    __tablename__ = 'alquileres'
    
    id = db.Column(db.Integer, primary_key=True)
    propietario = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    monto_mensual = db.Column(db.Float, nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    dia_vencimiento = db.Column(db.Integer, default=5)
    activo = db.Column(db.Boolean, default=True)
    observaciones = db.Column(db.Text)

class PagoAlquiler(db.Model):
    __tablename__ = 'pagos_alquiler'
    
    id = db.Column(db.Integer, primary_key=True)
    alquiler_id = db.Column(db.Integer, db.ForeignKey('alquileres.id'), nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.Date, default=date.today)
    comprobante = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='pagado')
    
    alquiler = db.relationship('Alquiler', backref='pagos')

# ==================== DASHBOARD PERSONALIZABLE ====================

class DashboardWidget(db.Model):
    __tablename__ = 'dashboard_widgets'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    icono = db.Column(db.String(50), default='fas fa-chart-line')
    visible_por_defecto = db.Column(db.Boolean, default=True)
    orden_por_defecto = db.Column(db.Integer, default=0)

class PreferenciaDashboard(db.Model):
    __tablename__ = 'preferencias_dashboard'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    widget_id = db.Column(db.Integer, db.ForeignKey('dashboard_widgets.id'), nullable=False)
    visible = db.Column(db.Boolean, default=True)
    orden = db.Column(db.Integer, default=0)
    
    usuario = db.relationship('User')
    widget = db.relationship('DashboardWidget')