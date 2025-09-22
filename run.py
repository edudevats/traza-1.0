#!/usr/bin/env python3
"""
Sistema de Gestión de Facturas
==============================

Punto de entrada principal para la aplicación Flask.
"""

import os
from app import create_app
from app.extensions import db
from app.models import User, ConfiguracionTasas
from app.utils import register_template_filters

# Create Flask application
app = create_app()

# Register template filters
register_template_filters(app)

def create_tables():
    """Create database tables and default data"""
    with app.app_context():
        db.create_all()

        # Create default admin user if it doesn't exist
        admin = User.query.filter_by(email="admin@facturas.com").first()
        if not admin:
            admin = User(
                nombre="Administrador del Sistema",
                email="admin@facturas.com",
                rol="admin",
                creditos=999,
                activo=True
            )
            admin.set_password("admin123")
            db.session.add(admin)

        # Create default supervisor user
        supervisor = User.query.filter_by(email="supervisor@facturas.com").first()
        if not supervisor:
            supervisor = User(
                nombre="Supervisor de Facturas",
                email="supervisor@facturas.com",
                rol="supervisor",
                creditos=50,
                activo=True
            )
            supervisor.set_password("super123")
            db.session.add(supervisor)

        # Create default tax configuration
        tasas = ConfiguracionTasas.query.first()
        if not tasas:
            tasas = ConfiguracionTasas(
                ieps=4.59,
                iva=0.16,
                pvr=0.20,
                iva_pvr=0.16,
                factor_conversion=0.264172
            )
            db.session.add(tasas)

        try:
            db.session.commit()
            print("[OK] Default data created successfully!")
            print("[INFO] Admin: admin@facturas.com / admin123")
            print("[INFO] Supervisor: supervisor@facturas.com / super123")
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error creating default data: {e}")

# Initialize database on startup
create_tables()

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell"""
    from app.models import User, Factura, ConfiguracionTasas, HistorialFactura, Notificacion
    return {
        'db': db,
        'User': User,
        'Factura': Factura,
        'ConfiguracionTasas': ConfiguracionTasas,
        'HistorialFactura': HistorialFactura,
        'Notificacion': Notificacion
    }

@app.cli.command()
def init_db():
    """Initialize the database with default data"""
    db.create_all()
    print("[OK] Database tables created!")

@app.cli.command()
def create_admin():
    """Create an admin user"""
    email = input("Admin email: ")
    password = input("Admin password: ")
    name = input("Admin name: ")

    admin = User(
        nombre=name,
        email=email,
        rol="admin",
        creditos=999,
        activo=True
    )
    admin.set_password(password)

    db.session.add(admin)
    db.session.commit()
    print(f"[OK] Admin user {email} created successfully!")

@app.cli.command()
def reset_db():
    """Reset the database (WARNING: This will delete all data!)"""
    confirm = input("This will delete ALL data. Type 'CONFIRM' to proceed: ")
    if confirm == 'CONFIRM':
        db.drop_all()
        db.create_all()
        print("[OK] Database reset completed!")
    else:
        print("[CANCELLED] Database reset cancelled.")

if __name__ == '__main__':
    # Development server configuration
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    print("[START] Starting Facturas App...")
    print(f"[URL] Running on: http://{host}:{port}")
    print(f"[DEBUG] Debug mode: {debug}")
    print("=" * 50)

    app.run(host=host, port=port, debug=debug)