# BoxFit Gym - Sistema de Gestión para Gimnasio de Boxeo

Sistema completo para administrar un gimnasio de boxeo con gestión de alumnos, clases, ventas y usuarios.

## 🚀 Funcionalidades

- **Dashboard** con estadísticas en tiempo real
- **Gestión de Alumnos**: alta, baja, modificación
- **Clases**: horarios, profesores, capacidad
- **Ventas**: productos, stock, registro de ventas
- **Usuarios**: administradores y operadores
- **Reportes**: ventas diarias, top productos, alumnos por clase

## 📋 Requisitos

- Python 3.9+
- PostgreSQL (o SQLite para desarrollo)

## 🛠️ Instalación Local

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/boxfit-gym.git
cd boxfit-gym

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
flask init-db

# Ejecutar
python app.py