import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Transaccion
from datetime import datetime

app = Flask(__name__)

# Configuración de Seguridad
# En Railway, deberías crear una variable llamada SECRET_KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')

# Configuración de Base de Datos
# Railway proporciona DATABASE_URL. Corregimos el protocolo para SQLAlchemy.
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
@login_required
def index():
    # Renderiza el dashboard principal
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuario o clave incorrecta')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- LÓGICA DE NEGOCIO ---

@app.route('/asistencia', methods=['POST'])
@login_required
def asistencia():
    dni_3 = request.form.get('dni')
    alumno = Alumno.query.filter_by(dni_fin=dni_3).first()
    if alumno:
        if alumno.deuda:
            return {"status": "error", "msg": f"ALERTA: {alumno.nombre} TIENE DEUDA"}, 403
        
        alumno.ultima_asistencia = datetime.utcnow()
        db.session.commit()
        return {"status": "success", "msg": f"Ingreso OK: {alumno.nombre}"}, 200
    
    return {"status": "error", "msg": "DNI no encontrado"}, 404

@app.route('/venta', methods=['POST'])
@login_required
def venta():
    try:
        nueva_venta = Transaccion(
            tipo='venta',
            item=request.form['producto'],
            monto=float(request.form['precio'])
        )
        db.session.add(nueva_venta)
        db.session.commit()
        flash('Venta registrada con éxito')
    except Exception as e:
        flash('Error al registrar venta')
    
    return redirect(url_for('index'))

# --- COMANDOS DE ADMINISTRADOR (Consola Railway) ---

@app.cli.command("init-db")
def init_db():
    """Ejecutar este comando en la consola de Railway para crear tablas y admin."""
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123') # Cambiar luego en el panel
        admin = User(username='admin', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> Base de datos inicializada y usuario 'admin' creado.")
    else:
        print(">>> La base de datos ya está inicializada.")

# --- ARRANQUE COMPATIBLE CON RAILWAY ---

if __name__ == '__main__':
    # Buscamos el puerto que nos asigna Railway, por defecto usamos 5000
    port = int(os.environ.get("PORT", 5000))
    # Importante: host='0.0.0.0' para que sea visible externamente
    app.run(host='0.0.0.0', port=port)