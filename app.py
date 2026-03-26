import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Alumno, Clase, AsistenciaClase, Producto, Venta
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc

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

# ====================== RUTAS PRINCIPALES ======================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Estadísticas
    total_alumnos = Alumno.query.filter_by(activo=True).count()
    total_alumnos_inactivos = Alumno.query.filter_by(activo=False).count()
    total_ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == date.today()).count()
    monto_ventas_hoy = db.session.query(func.sum(Venta.monto)).filter(func.date(Venta.fecha) == date.today()).scalar() or 0
    
    # Últimas ventas con datos de alumno
    ultimas_ventas = Venta.query.order_by(Venta.fecha.desc()).limit(5).all()
    
    # Últimos alumnos
    ultimos_alumnos = Alumno.query.order_by(Alumno.fecha_inscripcion.desc()).limit(5).all()
    
    # Productos para venta rápida
    productos = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).all()
    
    # Alumnos para venta rápida
    alumnos = Alumno.query.filter_by(activo=True).order_by(Alumno.nombre).all()
    
    stats = {
        'total_alumnos': total_alumnos,
        'total_alumnos_inactivos': total_alumnos_inactivos,
        'total_ventas_hoy': total_ventas_hoy,
        'monto_ventas_hoy': monto_ventas_hoy,
        'ultimas_ventas': ultimas_ventas,
        'ultimos_alumnos': ultimos_alumnos,
        'productos': productos,
        'alumnos': alumnos,
    }
    
    return render_template('dashboard.html', stats=stats, now=datetime.now())

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

# ====================== CLASES ======================

@app.route('/clases')
@login_required
def clases():
    clases_lista = Clase.query.order_by(Clase.dia, Clase.hora).all()
    
    # Contar asistentes por clase
    for clase in clases_lista:
        clase.asistentes_count = AsistenciaClase.query.filter_by(clase_id=clase.id, fecha=date.today()).count()
    
    return render_template('clases.html', clases=clases_lista)

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
    
    # Verificar si ya registró asistencia hoy
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
        
        alumno_nombre = Alumno.query.get(alumno_id).nombre if alumno_id else 'Sin alumno'
        flash(f'Venta registrada: {producto.nombre} x{cantidad} - ${monto} - {alumno_nombre}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('ventas'))

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

# ====================== REPORTES ======================

@app.route('/reportes')
@login_required
def reportes():
    hoy = date.today()
    
    # Ventas por día (últimos 30 días)
    ventas_dias = []
    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        total = db.session.query(func.sum(Venta.monto)).filter(func.date(Venta.fecha) == dia).scalar() or 0
        ventas_dias.append({
            'fecha': dia.strftime('%d/%m'),
            'total': total
        })
    
    # Ventas por categoría
    ventas_categoria = db.session.query(
        Producto.categoria,
        func.sum(Venta.monto).label('total')
    ).join(Venta, Venta.producto_id == Producto.id).group_by(Producto.categoria).order_by(func.sum(Venta.monto).desc()).all()
    
    # Top productos más vendidos
    top_productos = db.session.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label('total_cantidad'),
        func.sum(Venta.monto).label('total_monto')
    ).group_by(Venta.producto_nombre).order_by(func.sum(Venta.monto).desc()).limit(10).all()
    
    # Alumnos por clase
    alumnos_clase = db.session.query(
        Alumno.clase,
        func.count(Alumno.id).label('total')
    ).filter_by(activo=True).group_by(Alumno.clase).all()
    
    # Ventas por mes (últimos 6 meses)
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
        
        ventas_meses.append({
            'mes': mes.strftime('%B'),
            'total': total
        })
    
    # Alumnos con más compras
    top_clientes = db.session.query(
        Alumno.nombre,
        func.sum(Venta.monto).label('total_gastado'),
        func.count(Venta.id).label('total_compras')
    ).join(Venta, Venta.alumno_id == Alumno.id).group_by(Alumno.id).order_by(func.sum(Venta.monto).desc()).limit(10).all()
    
    return render_template('reportes.html', 
                          ventas_dias=ventas_dias,
                          ventas_categoria=ventas_categoria,
                          top_productos=top_productos,
                          alumnos_clase=alumnos_clase,
                          ventas_meses=ventas_meses,
                          top_clientes=top_clientes)

# ====================== INICIALIZACIÓN ======================

@app.cli.command("init-db")
def init_db():
    db.create_all()
    
    # Crear admin
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)
        db.session.commit()
        print(">>> Usuario admin creado: admin / admin123")
    
    # Crear productos de ropa de boxeo
    if Producto.query.count() == 0:
        productos_ropa = [
            # Remeras
            Producto(nombre='Remera BoxFit Premium', categoria='Ropa', subcategoria='Remeras', precio=8500, stock=30, talles='S,M,L,XL', colores='Negro,Blanco,Gris'),
            Producto(nombre='Remera Everlast Pro', categoria='Ropa', subcategoria='Remeras', precio=12000, stock=25, talles='S,M,L,XL', colores='Negro,Rojo,Azul'),
            Producto(nombre='Remera Venum Combat', categoria='Ropa', subcategoria='Remeras', precio=15000, stock=20, talles='M,L,XL', colores='Negro,Blanco'),
            # Sudaderas
            Producto(nombre='Sudadera BoxFit Hoodie', categoria='Ropa', subcategoria='Sudaderas', precio=25000, stock=20, talles='S,M,L,XL', colores='Negro,Gris,Marrón'),
            Producto(nombre='Sudadera Everlast', categoria='Ropa', subcategoria='Sudaderas', precio=32000, stock=15, talles='M,L,XL', colores='Negro,Azul'),
            # Buzos
            Producto(nombre='Buzo Deportivo BoxFit', categoria='Ropa', subcategoria='Buzos', precio=18000, stock=25, talles='S,M,L,XL', colores='Negro,Gris'),
            Producto(nombre='Buzo Training Pro', categoria='Ropa', subcategoria='Buzos', precio=22000, stock=20, talles='M,L,XL', colores='Negro,Azul Marino'),
            # Pantalones
            Producto(nombre='Pantalón BoxFit Jogger', categoria='Ropa', subcategoria='Pantalones', precio=15000, stock=30, talles='S,M,L,XL', colores='Negro,Gris'),
            Producto(nombre='Pantalón Everlast', categoria='Ropa', subcategoria='Pantalones', precio=20000, stock=25, talles='M,L,XL', colores='Negro'),
            # Accesorios
            Producto(nombre='Guantes de Boxeo', categoria='Equipamiento', subcategoria='Accesorios', precio=28000, stock=15, talles='10oz,12oz,14oz,16oz', colores='Negro,Rojo,Azul'),
            Producto(nombre='Vendas Elásticas', categoria='Equipamiento', subcategoria='Accesorios', precio=3500, stock=50, talles='4.5m', colores='Negro,Blanco,Rojo'),
            Producto(nombre='Protector Bucal', categoria='Equipamiento', subcategoria='Accesorios', precio=5000, stock=40, talles='Unisex', colores='Negro,Transparente'),
            # Bebidas
            Producto(nombre='Agua Mineral', categoria='Bebidas', subcategoria='Hidratación', precio=800, stock=100, talles='500ml', colores='-'),
            Producto(nombre='Isotónico Powerade', categoria='Bebidas', subcategoria='Hidratación', precio=1500, stock=80, talles='500ml', colores='Azul,Blanco'),
            Producto(nombre='Proteína Whey', categoria='Suplementos', subcategoria='Proteínas', precio=18000, stock=20, talles='1kg', colores='Vainilla,Chocolate'),
        ]
        for p in productos_ropa:
            db.session.add(p)
        db.session.commit()
        print(">>> Productos de ropa y accesorios creados")
    
    # Crear clases por defecto
    if Clase.query.count() == 0:
        clases_default = [
            Clase(nombre='Boxeo Principiantes', dia='Lunes', hora='18:00', profesor='Carlos', capacidad=20),
            Clase(nombre='Boxeo Intermedio', dia='Martes', hora='19:00', profesor='Laura', capacidad=15),
            Clase(nombre='Funcional', dia='Miércoles', hora='18:00', profesor='Martín', capacidad=25),
            Clase(nombre='Boxeo Avanzado', dia='Jueves', hora='19:00', profesor='Carlos', capacidad=12),
            Clase(nombre='Sparring', dia='Viernes', hora='18:00', profesor='Laura', capacidad=10),
            Clase(nombre='Boxeo Sábado', dia='Sábado', hora='10:00', profesor='Martín', capacidad=20),
        ]
        for c in clases_default:
            db.session.add(c)
        db.session.commit()
        print(">>> Clases por defecto creadas")
    
    print(">>> Base de datos inicializada")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)