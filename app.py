import os
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Clase, AsistenciaClase, Producto, Venta, CajaDiaria, Configuracion, ConfiguracionSitio, Gasto, Alquiler, PagoAlquiler, DashboardWidget, PreferenciaDashboard
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc
from io import BytesIO

app = Flask(__name__)

# Configuración
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'boxfit_secret_key_2024')

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor iniciá sesión'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ====================== HELPERS ======================

def get_ventas_semanales():
    hoy = date.today()
    ventas = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        total = db.session.query(func.sum(Venta.monto)).filter(
            func.date(Venta.fecha) == dia
        ).scalar() or 0
        ventas.append({'dia': dia.strftime('%a'), 'total': total})
    return ventas

def get_top_productos(limit=5):
    resultados = db.session.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label('cantidad')
    ).group_by(Venta.producto_nombre).order_by(func.sum(Venta.cantidad).desc()).limit(limit).all()
    return [{'nombre': r[0], 'cantidad': r[1]} for r in resultados]

# ====================== CONTEXTO GLOBAL ======================

@app.context_processor
def inject_config():
    return {
        'configuracion_sitio': ConfiguracionSitio
    }

# ====================== RUTAS PRINCIPALES ======================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    total_alumnos = Alumno.query.filter_by(activo=True).count()
    total_alumnos_inactivos = Alumno.query.filter_by(activo=False).count()
    total_ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == date.today()).count()
    monto_ventas_hoy = db.session.query(func.sum(Venta.monto)).filter(func.date(Venta.fecha) == date.today()).scalar() or 0
    
    ultimas_ventas = Venta.query.order_by(Venta.fecha.desc()).limit(5).all()
    ultimos_alumnos = Alumno.query.order_by(Alumno.fecha_inscripcion.desc()).limit(5).all()
    
    productos_destacados = Configuracion.get('productos_destacados', [])
    productos = []
    otros_productos = []
    
    if productos_destacados:
        for p_data in productos_destacados:
            prod = Producto.query.get(p_data.get('id'))
            if prod and prod.stock > 0:
                productos.append(prod)
        otros = Producto.query.filter(Producto.stock > 0).filter(Producto.id.notin_([p.id for p in productos])).order_by(Producto.nombre).limit(10).all()
        otros_productos = otros
    else:
        productos = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).limit(10).all()
    
    alumnos = Alumno.query.filter_by(activo=True).order_by(Alumno.nombre).all()
    
    ventas_semanales = get_ventas_semanales()
    top_productos = get_top_productos()
    
    hoy = date.today()
    gastos_mes = db.session.query(func.sum(Gasto.monto)).filter(
        func.extract('month', Gasto.fecha) == hoy.month,
        func.extract('year', Gasto.fecha) == hoy.year
    ).scalar() or 0
    
    stats = {
        'total_alumnos': total_alumnos,
        'total_alumnos_inactivos': total_alumnos_inactivos,
        'total_ventas_hoy': total_ventas_hoy,
        'monto_ventas_hoy': monto_ventas_hoy,
        'ultimas_ventas': ultimas_ventas,
        'ultimos_alumnos': ultimos_alumnos,
        'productos': productos,
        'otros_productos': otros_productos,
        'alumnos': alumnos,
        'gastos_mes': gastos_mes
    }
    
    return render_template('dashboard.html', 
                          stats=stats, 
                          now=datetime.now(),
                          ventas_semanales=ventas_semanales,
                          top_productos_json=top_productos)

# ====================== AUTENTICACIÓN ======================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Bienvenido {user.username}', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# ====================== VENTA RÁPIDA ======================

@app.route('/venta-rapida', methods=['POST'])
@login_required
def venta_rapida():
    try:
        alumno_id = request.form.get('alumno_id')
        producto_id = request.form.get('producto_id')
        cantidad = int(request.form.get('cantidad', 1))
        talle = request.form.get('talle', '')
        
        producto = Producto.query.get(producto_id)
        if not producto:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('index'))
        
        if producto.stock < cantidad:
            flash(f'Stock insuficiente. Solo hay {producto.stock} unidades', 'error')
            return redirect(url_for('index'))
        
        monto = producto.precio * cantidad
        
        venta = Venta(
            alumno_id=alumno_id if alumno_id else None,
            producto_id=producto.id,
            producto_nombre=producto.nombre,
            cantidad=cantidad,
            talle=talle,
            monto=monto,
            usuario_id=current_user.id
        )
        
        producto.stock -= cantidad
        db.session.add(venta)
        db.session.commit()
        
        caja = CajaDiaria.query.filter_by(fecha=date.today()).first()
        if caja and caja.estado == 'abierta':
            caja.ventas_totales = (caja.ventas_totales or 0) + monto
            db.session.commit()
        
        alumno_nombre = Alumno.query.get(alumno_id).nombre if alumno_id else 'Sin alumno asignado'
        flash(f'Venta registrada: {producto.nombre} x{cantidad} - ${monto} - {alumno_nombre}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# ====================== ALUMNOS ======================

@app.route('/alumnos')
@login_required
def alumnos():
    alumnos_lista = Alumno.query.order_by(Alumno.fecha_inscripcion.desc()).all()
    return render_template('alumnos.html', alumnos=alumnos_lista)

@app.route('/alumnos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    if request.method == 'POST':
        try:
            nuevo = Alumno(
                nombre=request.form['nombre'],
                dni=request.form['dni'],
                telefono=request.form.get('telefono', ''),
                email=request.form.get('email', ''),
                clase=request.form.get('clase'),
                horario=request.form.get('horario'),
                activo=True
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(f'Alumno {nuevo.nombre} agregado', 'success')
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    clases = Clase.query.all()
    return render_template('nuevo_alumno.html', clases=clases)

@app.route('/alumnos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            alumno.nombre = request.form['nombre']
            alumno.dni = request.form['dni']
            alumno.telefono = request.form.get('telefono', '')
            alumno.email = request.form.get('email', '')
            alumno.clase = request.form.get('clase')
            alumno.horario = request.form.get('horario')
            alumno.activo = 'activo' in request.form
            db.session.commit()
            flash('Alumno actualizado', 'success')
            return redirect(url_for('alumnos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    clases = Clase.query.all()
    return render_template('editar_alumno.html', alumno=alumno, clases=clases)

@app.route('/alumnos/eliminar/<int:id>')
@login_required
def eliminar_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    nombre = alumno.nombre
    db.session.delete(alumno)
    db.session.commit()
    flash(f'Alumno {nombre} eliminado', 'success')
    return redirect(url_for('alumnos'))

@app.route('/alumnos/<int:id>/compras')
@login_required
def alumno_compras(id):
    alumno = Alumno.query.get_or_404(id)
    ventas = Venta.query.filter_by(alumno_id=id).order_by(Venta.fecha.desc()).all()
    return render_template('alumno_compras.html', alumno=alumno, ventas=ventas)

# ====================== IMPORTACIÓN MASIVA ======================

@app.route('/alumnos/importar', methods=['POST'])
@login_required
def importar_alumnos_excel():
    if current_user.role != 'admin':
        flash('Solo administradores pueden importar alumnos', 'error')
        return redirect(url_for('alumnos'))
    
    if 'archivo' not in request.files:
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('alumnos'))
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('alumnos'))
    
    if not archivo.filename.endswith(('.xlsx', '.xls')):
        flash('Formato de archivo no válido. Use .xlsx o .xls', 'error')
        return redirect(url_for('alumnos'))
    
    try:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.strip().str.lower()
        
        columnas_requeridas = ['nombre', 'dni']
        for col in columnas_requeridas:
            if col not in df.columns:
                flash(f'Falta la columna requerida: {col}', 'error')
                return redirect(url_for('alumnos'))
        
        importados = 0
        errores = []
        
        for idx, row in df.iterrows():
            try:
                nombre = str(row.get('nombre', '')).strip()
                dni = str(row.get('dni', '')).strip()
                
                if not nombre or not dni:
                    errores.append(f"Fila {idx+2}: Nombre o DNI vacío")
                    continue
                
                existe = Alumno.query.filter_by(dni=dni).first()
                if existe:
                    errores.append(f"Fila {idx+2}: DNI {dni} ya existe como {existe.nombre}")
                    continue
                
                nuevo_alumno = Alumno(
                    nombre=nombre,
                    dni=dni,
                    telefono=str(row.get('telefono', '')) if pd.notna(row.get('telefono')) else '',
                    email=str(row.get('email', '')) if pd.notna(row.get('email')) else '',
                    clase=str(row.get('clase', '')) if pd.notna(row.get('clase')) else None,
                    horario=str(row.get('horario', '')) if pd.notna(row.get('horario')) else None,
                    activo=True
                )
                db.session.add(nuevo_alumno)
                importados += 1
                
            except Exception as e:
                errores.append(f"Fila {idx+2}: {str(e)}")
        
        db.session.commit()
        
        mensaje = f'✅ Se importaron {importados} alumnos correctamente.'
        if errores:
            mensaje += f' ❌ {len(errores)} errores: ' + '; '.join(errores[:5])
            if len(errores) > 5:
                mensaje += f' y {len(errores)-5} más...'
        
        flash(mensaje, 'success' if importados > 0 else 'warning')
        
    except Exception as e:
        flash(f'Error al procesar el archivo: {str(e)}', 'error')
    
    return redirect(url_for('alumnos'))

@app.route('/alumnos/plantilla')
@login_required
def descargar_plantilla_alumnos():
    datos = {
        'nombre': ['Juan Pérez', 'María García'],
        'dni': ['12345678', '87654321'],
        'telefono': ['5491112345678', '5491123456789'],
        'email': ['juan@ejemplo.com', 'maria@ejemplo.com'],
        'clase': ['Boxeo Principiantes', 'Funcional'],
        'horario': ['18:00-19:00', '19:00-20:00']
    }
    
    df = pd.DataFrame(datos)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name='Alumnos')
    output.seek(0)
    
    return send_file(
        output,
        download_name='plantilla_alumnos.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ====================== CLASES ======================

@app.route('/clases')
@login_required
def clases():
    clases_lista = Clase.query.order_by(Clase.dia, Clase.hora).all()
    
    for clase in clases_lista:
        clase.asistentes_count = AsistenciaClase.query.filter_by(
            clase_id=clase.id, 
            fecha=date.today()
        ).count()
    
    alumnos_activos = Alumno.query.filter_by(activo=True).all()
    return render_template('clases.html', clases=clases_lista, alumnos_activos=alumnos_activos)

@app.route('/clases/nueva', methods=['POST'])
@login_required
def nueva_clase():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('clases'))
    
    try:
        nueva = Clase(
            nombre=request.form['nombre'],
            dia=request.form['dia'],
            hora=request.form['hora'],
            profesor=request.form.get('profesor', ''),
            capacidad=int(request.form.get('capacidad', 20))
        )
        db.session.add(nueva)
        db.session.commit()
        flash('Clase creada', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('clases'))

@app.route('/clases/eliminar/<int:id>')
@login_required
def eliminar_clase(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('clases'))
    
    clase = Clase.query.get_or_404(id)
    db.session.delete(clase)
    db.session.commit()
    flash('Clase eliminada', 'success')
    return redirect(url_for('clases'))

@app.route('/clases/<int:id>/asistencia', methods=['POST'])
@login_required
def registrar_asistencia_clase(id):
    clase = Clase.query.get_or_404(id)
    alumno_id = request.form.get('alumno_id')
    
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        flash('Alumno no encontrado', 'error')
        return redirect(url_for('clases'))
    
    ya_asistio = AsistenciaClase.query.filter_by(
        alumno_id=alumno_id, 
        clase_id=id,
        fecha=date.today()
    ).first()
    
    if ya_asistio:
        flash(f'{alumno.nombre} ya registró asistencia hoy', 'warning')
    else:
        nueva_asistencia = AsistenciaClase(
            alumno_id=alumno_id,
            clase_id=id
        )
        db.session.add(nueva_asistencia)
        db.session.commit()
        flash(f'Asistencia registrada: {alumno.nombre} - {clase.nombre}', 'success')
    
    return redirect(url_for('clases'))

@app.route('/api/calendario')
@login_required
def api_calendario():
    offset = int(request.args.get('offset', 0))
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(days=offset*7)
    
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    resultado = []
    
    for i, dia in enumerate(dias):
        fecha = inicio_semana + timedelta(days=i)
        clases_dia = Clase.query.filter_by(dia=dia).all()
        resultado.append({
            'nombre': dia,
            'fecha': fecha.strftime('%d/%m'),
            'clases': [{'nombre': c.nombre, 'hora': c.hora, 'profesor': c.profesor} for c in clases_dia]
        })
    
    return jsonify({'dias': resultado})

# ====================== PRODUCTOS ======================

@app.route('/productos')
@login_required
def productos():
    productos_lista = Producto.query.order_by(Producto.categoria, Producto.nombre).all()
    categorias = ['Remeras', 'Sudaderas', 'Buzos', 'Pantalones', 'Accesorios', 'Bebidas', 'Suplementos']
    return render_template('productos.html', productos=productos_lista, categorias=categorias)

@app.route('/productos/nuevo', methods=['POST'])
@login_required
def nuevo_producto():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('productos'))
    
    try:
        nuevo = Producto(
            nombre=request.form['nombre'],
            categoria=request.form.get('categoria'),
            subcategoria=request.form.get('subcategoria'),
            precio=float(request.form['precio']),
            stock=int(request.form.get('stock', 0)),
            talles=request.form.get('talles', ''),
            colores=request.form.get('colores', '')
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Producto agregado', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('productos'))

@app.route('/productos/editar/<int:id>', methods=['POST'])
@login_required
def editar_producto(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('productos'))
    
    producto = Producto.query.get_or_404(id)
    try:
        producto.nombre = request.form['nombre']
        producto.precio = float(request.form['precio'])
        producto.stock = int(request.form.get('stock', 0))
        producto.talles = request.form.get('talles', '')
        producto.colores = request.form.get('colores', '')
        db.session.commit()
        flash('Producto actualizado', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('productos'))

@app.route('/productos/eliminar/<int:id>')
@login_required
def eliminar_producto(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('productos'))
    
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado', 'success')
    return redirect(url_for('productos'))

# ====================== VENTAS ======================

@app.route('/ventas')
@login_required
def ventas():
    productos = Producto.query.order_by(Producto.nombre).all()
    ventas_lista = Venta.query.order_by(Venta.fecha.desc()).limit(100).all()
    alumnos = Alumno.query.filter_by(activo=True).order_by(Alumno.nombre).all()
    return render_template('ventas.html', productos=productos, ventas=ventas_lista, alumnos=alumnos)

@app.route('/venta/registrar', methods=['POST'])
@login_required
def registrar_venta():
    try:
        alumno_id = request.form.get('alumno_id')
        producto_id = int(request.form['producto_id'])
        cantidad = int(request.form.get('cantidad', 1))
        talle = request.form.get('talle', '')
        
        producto = Producto.query.get(producto_id)
        if not producto:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('ventas'))
        
        if producto.stock < cantidad:
            flash(f'Stock insuficiente. Solo hay {producto.stock} unidades', 'error')
            return redirect(url_for('ventas'))
        
        monto = producto.precio * cantidad
        
        venta = Venta(
            alumno_id=alumno_id if alumno_id else None,
            producto_id=producto.id,
            producto_nombre=producto.nombre,
            cantidad=cantidad,
            talle=talle,
            monto=monto,
            usuario_id=current_user.id
        )
        
        producto.stock -= cantidad
        db.session.add(venta)
        db.session.commit()
        
        caja = CajaDiaria.query.filter_by(fecha=date.today()).first()
        if caja and caja.estado == 'abierta':
            caja.ventas_totales = (caja.ventas_totales or 0) + monto
            db.session.commit()
        
        alumno_nombre = Alumno.query.get(alumno_id).nombre if alumno_id else 'Sin alumno'
        flash(f'Venta registrada: {producto.nombre} x{cantidad} - ${monto} - {alumno_nombre}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('ventas'))

@app.route('/ticket/<int:id>')
@login_required
def ticket(id):
    venta = Venta.query.get_or_404(id)
    venta.precio_unitario = venta.monto / venta.cantidad if venta.cantidad > 0 else venta.monto
    return render_template('ticket.html', venta=venta)

# ====================== WHATSAPP ======================

@app.route('/whatsapp/alumno/<int:id>')
@login_required
def whatsapp_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    if alumno.telefono:
        mensaje = f"Hola {alumno.nombre}, te contactamos desde BoxFit Gym. ¿Cómo estás?"
        return redirect(f"https://wa.me/{alumno.telefono}?text={mensaje.replace(' ', '%20')}")
    flash('El alumno no tiene número de teléfono registrado', 'error')
    return redirect(request.referrer or url_for('alumnos'))

@app.route('/whatsapp/recordatorio/<int:id>')
@login_required
def whatsapp_recordatorio(id):
    alumno = Alumno.query.get_or_404(id)
    if alumno.telefono:
        mensaje = f"Hola {alumno.nombre}, te recordamos tu clase de {alumno.clase or 'boxeo'} hoy a las {alumno.horario or '18:00'}. ¡Te esperamos! 🥊"
        return redirect(f"https://wa.me/{alumno.telefono}?text={mensaje.replace(' ', '%20')}")
    flash('El alumno no tiene número de teléfono registrado', 'error')
    return redirect(request.referrer or url_for('alumnos'))

# ====================== USUARIOS ======================

@app.route('/usuarios')
@login_required
def usuarios():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    usuarios_lista = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios_lista)

@app.route('/usuarios/nuevo', methods=['POST'])
@login_required
def nuevo_usuario():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    try:
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'operador')
        
        if User.query.filter_by(username=username).first():
            flash('Usuario ya existe', 'error')
            return redirect(url_for('usuarios'))
        
        nuevo = User(
            username=username,
            password=generate_password_hash(password),
            role=role
        )
        db.session.add(nuevo)
        db.session.commit()
        flash(f'Usuario {username} creado', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('usuarios'))

@app.route('/usuarios/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    if id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'error')
        return redirect(url_for('usuarios'))
    
    usuario = User.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado', 'success')
    return redirect(url_for('usuarios'))

# ====================== CAJA DIARIA ======================

@app.route('/caja')
@login_required
def caja():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    caja_hoy = CajaDiaria.query.filter_by(fecha=date.today()).first()
    cajas_anteriores = CajaDiaria.query.order_by(CajaDiaria.fecha.desc()).limit(30).all()
    return render_template('caja.html', caja_hoy=caja_hoy, cajas=cajas_anteriores, now=datetime.now())

@app.route('/caja/apertura', methods=['POST'])
@login_required
def apertura_caja():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    if CajaDiaria.query.filter_by(fecha=date.today()).first():
        flash('La caja de hoy ya está abierta', 'error')
        return redirect(url_for('caja'))
    
    monto_inicial = float(request.form.get('monto_inicial', 0))
    nueva_caja = CajaDiaria(
        fecha=date.today(),
        monto_inicial=monto_inicial,
        usuario_apertura_id=current_user.id
    )
    db.session.add(nueva_caja)
    db.session.commit()
    flash(f'Caja abierta con ${monto_inicial}', 'success')
    return redirect(url_for('caja'))

@app.route('/caja/cierre', methods=['POST'])
@login_required
def cierre_caja():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    caja = CajaDiaria.query.filter_by(fecha=date.today()).first()
    if not caja:
        flash('La caja no está abierta', 'error')
        return redirect(url_for('caja'))
    
    if caja.estado == 'cerrada':
        flash('La caja ya está cerrada', 'error')
        return redirect(url_for('caja'))
    
    ventas_hoy = db.session.query(func.sum(Venta.monto)).filter(
        func.date(Venta.fecha) == date.today()
    ).scalar() or 0
    
    monto_final = caja.monto_inicial + ventas_hoy
    
    caja.ventas_totales = ventas_hoy
    caja.monto_final = monto_final
    caja.cierre = datetime.utcnow()
    caja.estado = 'cerrada'
    caja.usuario_cierre_id = current_user.id
    db.session.commit()
    
    flash(f'Caja cerrada. Ventas: ${ventas_hoy} - Total: ${monto_final}', 'success')
    return redirect(url_for('caja'))

# ====================== GASTOS ======================

@app.route('/gastos')
@login_required
def gastos():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    gastos_lista = Gasto.query.order_by(Gasto.fecha.desc()).all()
    categorias = ['Alquiler', 'Sueldos', 'Servicios', 'Mantenimiento', 'Insumos', 'Publicidad', 'Otros']
    
    hoy = date.today()
    gastos_mes = db.session.query(func.sum(Gasto.monto)).filter(
        func.extract('month', Gasto.fecha) == hoy.month,
        func.extract('year', Gasto.fecha) == hoy.year
    ).scalar() or 0
    
    return render_template('gastos_gym.html', gastos=gastos_lista, categorias=categorias, total_mes=gastos_mes, now=datetime.now())

@app.route('/gastos/nuevo', methods=['POST'])
@login_required
def nuevo_gasto():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('gastos'))
    
    try:
        nuevo = Gasto(
            categoria=request.form['categoria'],
            descripcion=request.form['descripcion'],
            monto=float(request.form['monto']),
            fecha=datetime.strptime(request.form['fecha'], '%Y-%m-%d').date() if request.form.get('fecha') else date.today(),
            comprobante=request.form.get('comprobante', ''),
            proveedor=request.form.get('proveedor', ''),
            usuario_id=current_user.id
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Gasto registrado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('gastos'))

@app.route('/gastos/eliminar/<int:id>')
@login_required
def eliminar_gasto(id):
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('gastos'))
    
    gasto = Gasto.query.get_or_404(id)
    db.session.delete(gasto)
    db.session.commit()
    flash('Gasto eliminado', 'success')
    return redirect(url_for('gastos'))

# ====================== ALQUILER ======================

@app.route('/alquiler')
@login_required
def alquiler():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    alquileres = Alquiler.query.filter_by(activo=True).all()
    historial_pagos = PagoAlquiler.query.order_by(PagoAlquiler.anio.desc(), PagoAlquiler.mes.desc()).limit(50).all()
    
    hoy = date.today()
    proximo_vencimiento = None
    alquiler_actual = Alquiler.query.filter_by(activo=True).first()
    
    if alquiler_actual:
        fecha_vencimiento = date(hoy.year, hoy.month, alquiler_actual.dia_vencimiento)
        if fecha_vencimiento < hoy:
            if hoy.month == 12:
                fecha_vencimiento = date(hoy.year + 1, 1, alquiler_actual.dia_vencimiento)
            else:
                fecha_vencimiento = date(hoy.year, hoy.month + 1, alquiler_actual.dia_vencimiento)
        proximo_vencimiento = fecha_vencimiento
    
    return render_template('alquiler.html', alquileres=alquileres, pagos=historial_pagos, proximo_vencimiento=proximo_vencimiento, now=datetime.now())

@app.route('/alquiler/nuevo', methods=['POST'])
@login_required
def nuevo_alquiler():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('alquiler'))
    
    try:
        nuevo = Alquiler(
            propietario=request.form['propietario'],
            direccion=request.form.get('direccion', ''),
            monto_mensual=float(request.form['monto_mensual']),
            fecha_inicio=datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d').date(),
            fecha_vencimiento=datetime.strptime(request.form['fecha_vencimiento'], '%Y-%m-%d').date(),
            dia_vencimiento=int(request.form.get('dia_vencimiento', 5)),
            observaciones=request.form.get('observaciones', '')
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Contrato de alquiler registrado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('alquiler'))

@app.route('/alquiler/pagar', methods=['POST'])
@login_required
def pagar_alquiler():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('alquiler'))
    
    try:
        alquiler_id = int(request.form['alquiler_id'])
        mes = int(request.form['mes'])
        anio = int(request.form['anio'])
        monto = float(request.form['monto'])
        comprobante = request.form.get('comprobante', '')
        
        existe = PagoAlquiler.query.filter_by(alquiler_id=alquiler_id, mes=mes, anio=anio).first()
        if existe:
            flash('Este mes ya fue pagado', 'warning')
            return redirect(url_for('alquiler'))
        
        pago = PagoAlquiler(
            alquiler_id=alquiler_id,
            mes=mes,
            anio=anio,
            monto=monto,
            comprobante=comprobante
        )
        db.session.add(pago)
        db.session.commit()
        
        gasto = Gasto(
            categoria='Alquiler',
            descripcion=f'Alquiler {mes}/{anio}',
            monto=monto,
            fecha=date.today(),
            comprobante=comprobante,
            usuario_id=current_user.id
        )
        db.session.add(gasto)
        db.session.commit()
        
        flash(f'Pago de alquiler {mes}/{anio} registrado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('alquiler'))

# ====================== DASHBOARD PERSONALIZABLE ======================

@app.route('/dashboard/configurar', methods=['GET', 'POST'])
@login_required
def configurar_dashboard():
    widgets = DashboardWidget.query.order_by(DashboardWidget.orden_por_defecto).all()
    preferencias = {p.widget_id: p for p in PreferenciaDashboard.query.filter_by(usuario_id=current_user.id).all()}
    
    if request.method == 'POST':
        for widget in widgets:
            visible = request.form.get(f'widget_{widget.id}_visible') == 'on'
            orden = int(request.form.get(f'widget_{widget.id}_orden', widget.orden_por_defecto))
            
            pref = preferencias.get(widget.id)
            if pref:
                pref.visible = visible
                pref.orden = orden
            else:
                pref = PreferenciaDashboard(
                    usuario_id=current_user.id,
                    widget_id=widget.id,
                    visible=visible,
                    orden=orden
                )
                db.session.add(pref)
        db.session.commit()
        flash('Configuración del dashboard guardada', 'success')
        return redirect(url_for('index'))
    
    return render_template('configurar_dashboard.html', widgets=widgets, preferencias=preferencias)

# ====================== REPORTES ======================

@app.route('/reportes')
@login_required
def reportes():
    hoy = date.today()
    
    ventas_dias = []
    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        total = db.session.query(func.sum(Venta.monto)).filter(func.date(Venta.fecha) == dia).scalar() or 0
        ventas_dias.append({'fecha': dia.strftime('%d/%m'), 'total': total})
    
    ventas_categoria = db.session.query(
        Producto.categoria,
        func.sum(Venta.monto).label('total')
    ).join(Venta, Venta.producto_id == Producto.id).group_by(Producto.categoria).order_by(func.sum(Venta.monto).desc()).all()
    
    top_productos = db.session.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label('total_cantidad'),
        func.sum(Venta.monto).label('total_monto')
    ).group_by(Venta.producto_nombre).order_by(func.sum(Venta.monto).desc()).limit(10).all()
    
    alumnos_clase = db.session.query(
        Alumno.clase,
        func.count(Alumno.id).label('total')
    ).filter_by(activo=True).group_by(Alumno.clase).all()
    
    ventas_meses = []
    for i in range(5, -1, -1):
        mes = hoy.replace(day=1) - timedelta(days=i*30)
        mes_inicio = mes.replace(day=1)
        if mes.month == 12:
            mes_fin = mes.replace(day=31)
        else:
            mes_fin = mes.replace(month=mes.month+1, day=1) - timedelta(days=1)
        
        total = db.session.query(func.sum(Venta.monto)).filter(
            Venta.fecha >= mes_inicio,
            Venta.fecha <= mes_fin
        ).scalar() or 0
        
        nombres_meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        ventas_meses.append({
            'mes': nombres_meses[mes.month-1],
            'total': total
        })
    
    top_clientes = db.session.query(
        Alumno.nombre,
        func.sum(Venta.monto).label('total_gastado'),
        func.count(Venta.id).label('total_compras')
    ).join(Venta, Venta.alumno_id == Alumno.id).group_by(Alumno.id).order_by(func.sum(Venta.monto).desc()).limit(10).all()
    
    gastos_por_categoria = db.session.query(
        Gasto.categoria,
        func.sum(Gasto.monto).label('total')
    ).group_by(Gasto.categoria).order_by(func.sum(Gasto.monto).desc()).all()
    
    return render_template('reportes.html', 
                          ventas_dias=ventas_dias,
                          ventas_categoria=ventas_categoria,
                          top_productos=top_productos,
                          alumnos_clase=alumnos_clase,
                          ventas_meses=ventas_meses,
                          top_clientes=top_clientes,
                          gastos_por_categoria=gastos_por_categoria)

@app.route('/reportes/exportar')
@login_required
def exportar_reportes():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    ventas = Venta.query.order_by(Venta.fecha.desc()).limit(500).all()
    alumnos = Alumno.query.all()
    productos = Producto.query.all()
    gastos = Gasto.query.order_by(Gasto.fecha.desc()).limit(500).all()
    
    df_ventas = pd.DataFrame([{
        'Fecha': v.fecha.strftime('%d/%m/%Y %H:%M'),
        'Producto': v.producto_nombre,
        'Cantidad': v.cantidad,
        'Monto': v.monto,
        'Alumno': v.alumno.nombre if v.alumno else 'Sin alumno',
        'Vendedor': v.usuario.username if v.usuario else '-'
    } for v in ventas])
    
    df_alumnos = pd.DataFrame([{
        'Nombre': a.nombre,
        'DNI': a.dni,
        'Teléfono': a.telefono,
        'Email': a.email,
        'Clase': a.clase,
        'Horario': a.horario,
        'Fecha Inscripción': a.fecha_inscripcion.strftime('%d/%m/%Y'),
        'Estado': 'Activo' if a.activo else 'Inactivo'
    } for a in alumnos])
    
    df_productos = pd.DataFrame([{
        'Producto': p.nombre,
        'Categoría': p.categoria,
        'Subcategoría': p.subcategoria,
        'Precio': p.precio,
        'Stock': p.stock,
        'Talles': p.talles
    } for p in productos])
    
    df_gastos = pd.DataFrame([{
        'Fecha': g.fecha.strftime('%d/%m/%Y'),
        'Categoría': g.categoria,
        'Descripción': g.descripcion,
        'Monto': g.monto,
        'Proveedor': g.proveedor or '-',
        'Comprobante': g.comprobante or '-'
    } for g in gastos])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_ventas.to_excel(writer, sheet_name='Ventas', index=False)
        df_alumnos.to_excel(writer, sheet_name='Alumnos', index=False)
        df_productos.to_excel(writer, sheet_name='Productos', index=False)
        df_gastos.to_excel(writer, sheet_name='Gastos', index=False)
    
    output.seek(0)
    return send_file(output, download_name=f'reporte_boxfit_{date.today()}.xlsx', as_attachment=True)

# ====================== CONFIGURACIÓN PRODUCTOS DESTACADOS ======================

@app.route('/configuracion')
@login_required
def configuracion():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    productos_destacados = Configuracion.get('productos_destacados', [])
    todos_productos = Producto.query.order_by(Producto.nombre).all()
    
    return render_template('configuracion.html', 
                          productos_destacados=productos_destacados,
                          todos_productos=todos_productos)

@app.route('/configuracion/guardar', methods=['POST'])
@login_required
def guardar_configuracion():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    productos_ids = request.form.getlist('productos_destacados')
    productos_destacados = []
    for pid in productos_ids:
        producto = Producto.query.get(pid)
        if producto:
            productos_destacados.append({
                'id': producto.id,
                'nombre': producto.nombre,
                'precio': producto.precio,
                'stock': producto.stock
            })
    
    Configuracion.set('productos_destacados', productos_destacados, 'json', 'Productos que aparecen en venta rápida')
    
    flash('Configuración guardada correctamente', 'success')
    return redirect(url_for('configuracion'))

@app.route('/configuracion/reset')
@login_required
def reset_configuracion():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    Configuracion.set('productos_destacados', [], 'json', 'Productos que aparecen en venta rápida')
    
    flash('Configuración restablecida', 'success')
    return redirect(url_for('configuracion'))

# ====================== CONFIGURACIÓN DEL SITIO ======================

@app.route('/configuracion/sitio', methods=['GET', 'POST'])
@login_required
def configuracion_sitio():
    if current_user.role != 'admin':
        flash('Solo administradores', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        ConfiguracionSitio.set('nombre_sitio', request.form.get('nombre_sitio', 'BoxFit Gym'))
        ConfiguracionSitio.set('logo_icono', request.form.get('logo_icono', '🥊'))
        ConfiguracionSitio.set('color_principal', request.form.get('color_principal', '#3b82f6'))
        ConfiguracionSitio.set('color_secundario', request.form.get('color_secundario', '#ef4444'))
        ConfiguracionSitio.set('favicon', request.form.get('favicon', '🥊'))
        ConfiguracionSitio.set('titulo_pagina', request.form.get('titulo_pagina', 'BoxFit Gym'))
        ConfiguracionSitio.set('frase_bienvenida', request.form.get('frase_bienvenida', 'Sistema de Gestión'))
        
        flash('Configuración guardada correctamente', 'success')
        return redirect(url_for('configuracion_sitio'))
    
    config = {
        'nombre_sitio': ConfiguracionSitio.get('nombre_sitio', 'BoxFit Gym'),
        'logo_icono': ConfiguracionSitio.get('logo_icono', '🥊'),
        'color_principal': ConfiguracionSitio.get('color_principal', '#3b82f6'),
        'color_secundario': ConfiguracionSitio.get('color_secundario', '#ef4444'),
        'favicon': ConfiguracionSitio.get('favicon', '🥊'),
        'titulo_pagina': ConfiguracionSitio.get('titulo_pagina', 'BoxFit Gym'),
        'frase_bienvenida': ConfiguracionSitio.get('frase_bienvenida', 'Sistema de Gestión')
    }
    
    return render_template('configuracion_sitio.html', config=config)

# ====================== INICIALIZACIÓN ======================

def init_dashboard_widgets():
    widgets_default = [
        {'nombre': 'stats_totales', 'titulo': 'Estadísticas Principales', 'icono': 'fas fa-chart-line', 'orden': 1},
        {'nombre': 'grafico_ventas', 'titulo': 'Ventas Últimos 7 Días', 'icono': 'fas fa-chart-bar', 'orden': 2},
        {'nombre': 'top_productos', 'titulo': 'Top 5 Productos', 'icono': 'fas fa-trophy', 'orden': 3},
        {'nombre': 'venta_rapida', 'titulo': 'Venta Rápida', 'icono': 'fas fa-cart-plus', 'orden': 4},
        {'nombre': 'ultimos_alumnos', 'titulo': 'Últimos Alumnos', 'icono': 'fas fa-users', 'orden': 5},
        {'nombre': 'ultimas_ventas', 'titulo': 'Últimas Ventas', 'icono': 'fas fa-receipt', 'orden': 6},
        {'nombre': 'gastos_mes', 'titulo': 'Gastos del Mes', 'icono': 'fas fa-money-bill-wave', 'orden': 7},
    ]
    
    for w in widgets_default:
        if not DashboardWidget.query.filter_by(nombre=w['nombre']).first():
            widget = DashboardWidget(
                nombre=w['nombre'],
                titulo=w['titulo'],
                icono=w['icono'],
                visible_por_defecto=True,
                orden_por_defecto=w['orden']
            )
            db.session.add(widget)
    db.session.commit()

@app.cli.command("init-db")
def init_db():
    db.create_all()
    
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> Usuario admin creado: admin / admin123")
    
    init_dashboard_widgets()
    
    if Producto.query.count() == 0:
        productos = [
            Producto(nombre='Remera BoxFit Premium', categoria='Ropa', subcategoria='Remeras', precio=8500, stock=30, talles='S,M,L,XL', colores='Negro,Blanco,Gris'),
            Producto(nombre='Remera Everlast Pro', categoria='Ropa', subcategoria='Remeras', precio=12000, stock=25, talles='S,M,L,XL', colores='Negro,Rojo,Azul'),
            Producto(nombre='Sudadera BoxFit Hoodie', categoria='Ropa', subcategoria='Sudaderas', precio=25000, stock=20, talles='S,M,L,XL', colores='Negro,Gris'),
            Producto(nombre='Buzo Deportivo BoxFit', categoria='Ropa', subcategoria='Buzos', precio=18000, stock=25, talles='S,M,L,XL', colores='Negro,Gris'),
            Producto(nombre='Pantalón BoxFit Jogger', categoria='Ropa', subcategoria='Pantalones', precio=15000, stock=30, talles='S,M,L,XL', colores='Negro,Gris'),
            Producto(nombre='Guantes de Boxeo', categoria='Equipamiento', subcategoria='Accesorios', precio=28000, stock=15, talles='10oz,12oz,14oz,16oz', colores='Negro,Rojo'),
            Producto(nombre='Vendas Elásticas', categoria='Equipamiento', subcategoria='Accesorios', precio=3500, stock=50, talles='4.5m', colores='Negro,Blanco'),
            Producto(nombre='Agua Mineral', categoria='Bebidas', subcategoria='Hidratación', precio=800, stock=100, talles='500ml', colores='-'),
        ]
        for p in productos:
            db.session.add(p)
        db.session.commit()
        print(">>> Productos creados")
    
    if Clase.query.count() == 0:
        clases = [
            Clase(nombre='Boxeo Principiantes', dia='Lunes', hora='18:00', profesor='Carlos', capacidad=20),
            Clase(nombre='Boxeo Intermedio', dia='Martes', hora='19:00', profesor='Laura', capacidad=15),
            Clase(nombre='Funcional', dia='Miércoles', hora='18:00', profesor='Martín', capacidad=25),
            Clase(nombre='Boxeo Avanzado', dia='Jueves', hora='19:00', profesor='Carlos', capacidad=12),
            Clase(nombre='Sparring', dia='Viernes', hora='18:00', profesor='Laura', capacidad=10),
        ]
        for c in clases:
            db.session.add(c)
        db.session.commit()
        print(">>> Clases creadas")
    
    print(">>> Base de datos inicializada")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
        init_dashboard_widgets()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)