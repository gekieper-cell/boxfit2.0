import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Transaccion
from datetime import datetime, timedelta
from sqlalchemy import func

app = Flask(__name__)

# ====================== CONFIGURACIÓN ======================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor iniciá sesión para continuar'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ====================== HELPERS ======================

def get_rango(periodo):
    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == 'hoy':
        return hoy, ahora
    elif periodo == 'semana':
        return hoy - timedelta(days=7), ahora
    elif periodo == 'mes':
        return hoy.replace(day=1), ahora
    return datetime.min, ahora


def sum_transacciones(tipo, desde, hasta):
    result = db.session.query(func.sum(Transaccion.monto)).filter(
        Transaccion.tipo == tipo,
        Transaccion.fecha >= desde,
        Transaccion.fecha <= hasta
    ).scalar()
    return result or 0.0


def count_transacciones(tipo, desde, hasta):
    return Transaccion.query.filter(
        Transaccion.tipo == tipo,
        Transaccion.fecha >= desde,
        Transaccion.fecha <= hasta
    ).count()


# ====================== AUTENTICACIÓN ======================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = hoy.replace(day=1)

    # Ingresos hoy = alumnos con ultima_asistencia de hoy
    ingresos_hoy = Alumno.query.filter(
        Alumno.ultima_asistencia >= hoy
    ).count()

    # Ventas
    ventas_hoy = sum_transacciones('venta', hoy, ahora)
    cant_ventas_hoy = count_transacciones('venta', hoy, ahora)
    ventas_mes = sum_transacciones('venta', inicio_mes, ahora)

    # Alumnos
    total_alumnos = Alumno.query.count()
    alumnos_deuda = Alumno.query.filter_by(deuda=True).count()
    alumnos_deuda_lista = Alumno.query.filter_by(deuda=True).limit(10).all()

    # Últimas asistencias hoy
    ultimas_asistencias = Alumno.query.filter(
        Alumno.ultima_asistencia >= hoy
    ).order_by(Alumno.ultima_asistencia.desc()).limit(6).all()

    # Últimas ventas hoy
    ultimas_ventas = Transaccion.query.filter(
        Transaccion.tipo == 'venta',
        Transaccion.fecha >= hoy
    ).order_by(Transaccion.fecha.desc()).limit(5).all()

    stats = {
        'total_alumnos': total_alumnos,
        'alumnos_deuda': alumnos_deuda,
        'alumnos_deuda_lista': alumnos_deuda_lista,
        'ingresos_hoy': ingresos_hoy,
        'ventas_hoy': ventas_hoy,
        'cant_ventas_hoy': cant_ventas_hoy,
        'ventas_mes': ventas_mes,
        'ultimas_asistencias': ultimas_asistencias,
        'ultimas_ventas': ultimas_ventas,
    }

    return render_template('dashboard.html', stats=stats)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash(f'¡Bienvenido, {user.username.title()}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))


# ====================== ASISTENCIA ======================

@app.route('/asistencia', methods=['POST'])
@login_required
def asistencia():
    dni_3 = request.form.get('dni', '').strip()
    alumno = Alumno.query.filter_by(dni_fin=dni_3).first()

    if alumno:
        if alumno.deuda:
            return {"status": "error", "msg": f"⚠ DEUDA PENDIENTE: {alumno.nombre}"}, 403

        alumno.ultima_asistencia = datetime.utcnow()
        db.session.commit()
        return {"status": "success", "msg": f"Ingreso OK: {alumno.nombre}"}, 200

    return {"status": "error", "msg": "DNI no encontrado en el sistema"}, 404


@app.route('/asistencia/historial')
@login_required
def asistencia_page():
    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoy - timedelta(days=7)

    historial = Alumno.query.filter(
        Alumno.ultima_asistencia.isnot(None)
    ).order_by(Alumno.ultima_asistencia.desc()).limit(50).all()

    ingresos_hoy = Alumno.query.filter(Alumno.ultima_asistencia >= hoy).count()
    ingresos_semana = Alumno.query.filter(Alumno.ultima_asistencia >= inicio_semana).count()

    # Distribución por clase HOY
    por_clase = {}
    alumnos_hoy = Alumno.query.filter(Alumno.ultima_asistencia >= hoy).all()
    for a in alumnos_hoy:
        clase = a.clase or 'Sin clase'
        por_clase[clase] = por_clase.get(clase, 0) + 1

    return render_template('asistencia.html',
                           historial=historial,
                           ingresos_hoy=ingresos_hoy,
                           ingresos_semana=ingresos_semana,
                           por_clase=por_clase,
                           hoy=ahora)


# ====================== VENTAS ======================

@app.route('/ventas')
@login_required
def ventas_page():
    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoy - timedelta(days=7)
    inicio_mes = hoy.replace(day=1)

    ventas = Transaccion.query.filter_by(tipo='venta').order_by(Transaccion.fecha.desc()).limit(100).all()

    totales = {
        'hoy': sum_transacciones('venta', hoy, ahora),
        'semana': sum_transacciones('venta', inicio_semana, ahora),
        'mes': sum_transacciones('venta', inicio_mes, ahora),
        'total': sum_transacciones('venta', datetime.min, ahora),
    }

    cant = {
        'hoy': count_transacciones('venta', hoy, ahora),
        'semana': count_transacciones('venta', inicio_semana, ahora),
        'mes': count_transacciones('venta', inicio_mes, ahora),
        'total': count_transacciones('venta', datetime.min, ahora),
    }

    return render_template('ventas.html', ventas=ventas, totales=totales, cant=cant)


@app.route('/venta', methods=['POST'])
@login_required
def venta():
    try:
        nueva_venta = Transaccion(
            tipo='venta',
            item=request.form.get('producto', '').strip(),
            monto=float(request.form.get('precio', 0))
        )
        db.session.add(nueva_venta)
        db.session.commit()
        flash('Venta registrada con éxito', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al registrar la venta', 'error')

    # Redirect según dónde venga
    next_url = request.form.get('next') or request.referrer or url_for('index')
    return redirect(next_url)


# ====================== GASTOS ======================

@app.route('/gastos')
@login_required
def gastos_page():
    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoy - timedelta(days=7)
    inicio_mes = hoy.replace(day=1)

    gastos = Transaccion.query.filter_by(tipo='gasto').order_by(Transaccion.fecha.desc()).limit(100).all()

    totales = {
        'hoy': sum_transacciones('gasto', hoy, ahora),
        'semana': sum_transacciones('gasto', inicio_semana, ahora),
        'mes': sum_transacciones('gasto', inicio_mes, ahora),
    }

    ventas_mes = sum_transacciones('venta', inicio_mes, ahora)
    balance = ventas_mes - totales['mes']

    return render_template('gastos.html', gastos=gastos, totales=totales, balance=balance)


@app.route('/gasto', methods=['POST'])
@login_required
def gasto():
    try:
        nuevo_gasto = Transaccion(
            tipo='gasto',
            item=request.form.get('producto', '').strip(),
            monto=float(request.form.get('precio', 0))
        )
        db.session.add(nuevo_gasto)
        db.session.commit()
        flash('Gasto registrado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al registrar el gasto', 'error')

    return redirect(url_for('gastos_page'))


@app.route('/transaccion/eliminar/<int:id>')
@login_required
def eliminar_transaccion(id):
    t = Transaccion.query.get_or_404(id)
    tipo = t.tipo
    db.session.delete(t)
    db.session.commit()
    flash(f'{"Venta" if tipo == "venta" else "Gasto"} eliminado/a correctamente', 'success')
    return redirect(request.referrer or url_for('ventas_page'))


# ====================== ALUMNOS ======================

@app.route('/alumnos')
@login_required
def alumnos():
    todos = Alumno.query.order_by(Alumno.nombre).all()
    return render_template('alumnos.html', alumnos=todos)


@app.route('/alumnos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    if request.method == 'POST':
        try:
            nuevo = Alumno(
                nombre=request.form['nombre'].strip(),
                dni_fin=request.form['dni_fin'].strip(),
                email=request.form.get('email', '').strip() or None,
                clase=request.form.get('clase') or None,
                deuda=request.form.get('deuda') == 'on'
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(f'Alumno "{nuevo.nombre}" agregado correctamente', 'success')
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash('Error al agregar el alumno. Verificá que el DNI no esté duplicado.', 'error')

    return render_template('nuevo_alumno.html')


@app.route('/alumnos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_alumno(id):
    alumno = Alumno.query.get_or_404(id)

    if request.method == 'POST':
        try:
            alumno.nombre = request.form['nombre'].strip()
            alumno.dni_fin = request.form['dni_fin'].strip()
            alumno.email = request.form.get('email', '').strip() or None
            alumno.clase = request.form.get('clase') or None
            alumno.deuda = request.form.get('deuda') == 'on'
            db.session.commit()
            flash('Alumno actualizado correctamente', 'success')
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el alumno', 'error')

    return render_template('editar_alumno.html', alumno=alumno)


@app.route('/alumnos/eliminar/<int:id>')
@login_required
def eliminar_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    nombre = alumno.nombre
    db.session.delete(alumno)
    db.session.commit()
    flash(f'Alumno "{nombre}" eliminado correctamente', 'success')
    return redirect(url_for('alumnos'))


# ====================== REPORTES ======================

@app.route('/reportes')
@login_required
def reportes_page():
    ahora = datetime.utcnow()
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = hoy.replace(day=1)
    inicio_mes_ant = (inicio_mes - timedelta(days=1)).replace(day=1)
    fin_mes_ant = inicio_mes - timedelta(seconds=1)

    ventas_mes = sum_transacciones('venta', inicio_mes, ahora)
    gastos_mes = sum_transacciones('gasto', inicio_mes, ahora)
    ventas_mes_ant = sum_transacciones('venta', inicio_mes_ant, fin_mes_ant)

    variacion = 0
    if ventas_mes_ant > 0:
        variacion = round(((ventas_mes - ventas_mes_ant) / ventas_mes_ant) * 100, 1)

    # Asistencias del mes
    asistencias_mes = Alumno.query.filter(Alumno.ultima_asistencia >= inicio_mes).count()
    dias_mes = (ahora - inicio_mes).days + 1
    promedio_diario = round(asistencias_mes / dias_mes, 1) if dias_mes > 0 else 0

    # Por clase
    por_clase_raw = db.session.query(
        Alumno.clase, func.count(Alumno.id)
    ).group_by(Alumno.clase).all()
    por_clase = [{'clase': c or 'Sin clase', 'cantidad': n} for c, n in por_clase_raw]

    # Top productos
    top_productos_raw = db.session.query(
        Transaccion.item,
        func.count(Transaccion.id).label('cantidad'),
        func.sum(Transaccion.monto).label('total')
    ).filter(
        Transaccion.tipo == 'venta',
        Transaccion.fecha >= inicio_mes
    ).group_by(Transaccion.item).order_by(func.sum(Transaccion.monto).desc()).limit(8).all()

    top_productos = [{'item': r.item, 'cantidad': r.cantidad, 'total': r.total or 0} for r in top_productos_raw]

    # Deudores
    deudores = Alumno.query.filter_by(deuda=True).order_by(Alumno.nombre).all()

    # Últimos 7 días para chart
    labels = []
    ventas_vals = []
    gastos_vals = []

    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        siguiente = dia + timedelta(days=1)
        labels.append(dia.strftime('%d/%m'))
        ventas_vals.append(round(sum_transacciones('venta', dia, siguiente), 2))
        gastos_vals.append(round(sum_transacciones('gasto', dia, siguiente), 2))

    # Resumen últimos 30 días
    resumen_dias = []
    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        siguiente = dia + timedelta(days=1)
        v = sum_transacciones('venta', dia, siguiente)
        g = sum_transacciones('gasto', dia, siguiente)
        asist = Alumno.query.filter(
            Alumno.ultima_asistencia >= dia,
            Alumno.ultima_asistencia < siguiente
        ).count()
        if v > 0 or g > 0 or asist > 0:
            resumen_dias.append({
                'fecha': dia.strftime('%d/%m/%Y'),
                'ventas': v,
                'gastos': g,
                'balance': v - g,
                'asistencias': asist
            })

    kpis = {
        'ventas_mes': ventas_mes,
        'gastos_mes': gastos_mes,
        'balance_mes': ventas_mes - gastos_mes,
        'variacion_ventas': variacion,
        'asistencias_mes': asistencias_mes,
        'promedio_diario': promedio_diario,
        'por_clase': por_clase,
        'top_productos': top_productos,
        'deudores': deudores,
        'chart_ventas_labels': labels,
        'chart_ventas_values': ventas_vals,
        'chart_gastos_values': gastos_vals,
        'chart_clases_labels': [p['clase'] for p in por_clase],
        'chart_clases_values': [p['cantidad'] for p in por_clase],
        'resumen_dias': resumen_dias,
    }

    return render_template('reportes.html', kpis=kpis)


# ====================== INIT DB ======================

@app.cli.command("init-db")
def init_db():
    """Inicializar base de datos y crear usuario admin"""
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> Base de datos inicializada. Usuario 'admin' creado con clave 'admin123'.")
    else:
        print(">>> La base de datos ya está inicializada.")


# ====================== ARRANQUE ======================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
