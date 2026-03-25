import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Transaccion
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
# Railway inyecta DATABASE_URL automáticamente
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS ---

@app.route('/')
@login_required
def index():
    # El dashboard que te pasé antes lo guardás como dashboard.html en /templates
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

@app.route('/asistencia', methods=['POST'])
@login_required
def asistencia():
    dni_3 = request.form.get('dni')
    alumno = Alumno.query.filter_by(dni_fin=dni_3).first()
    if alumno:
        if alumno.deuda:
            return {"status": "error", "msg": f"Alumno {alumno.nombre} tiene DEUDA PENDIENTE"}, 403
        alumno.ultima_asistencia = datetime.utcnow()
        db.session.commit()
        return {"status": "success", "msg": f"Bienvenido {alumno.nombre}"}, 200
    return {"status": "error", "msg": "Alumno no encontrado"}, 404

@app.route('/venta', methods=['POST'])
@login_required
def venta():
    nueva_venta = Transaccion(
        tipo='venta',
        item=request.form['producto'],
        monto=float(request.form['precio'])
    )
    db.session.add(nueva_venta)
    db.session.commit()
    return redirect(url_for('index'))

# --- COMANDO PARA CREAR DB Y ADMIN ---
@app.cli.command("init-db")
def init_db():
    db.create_all()
    # Crear admin por defecto
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
        print("Base de datos y usuario admin creados.")

if __name__ == '__main__':
    app.run()