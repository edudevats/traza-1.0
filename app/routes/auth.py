from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models import User, ConfiguracionTasas
from ..forms import LoginForm, RegisterForm
from datetime import datetime

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if not user.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return render_template("auth/login.html", form=form)

            # Update last access
            user.ultimo_acceso = datetime.utcnow()
            db.session.commit()

            login_user(user)
            next_page = request.args.get('next')

            # Redirect based on user role
            if next_page:
                return redirect(next_page)
            elif user.is_admin():
                return redirect(url_for("admins.dashboard"))
            elif user.is_supervisor():
                return redirect(url_for("supervisores.dashboard"))
            else:
                return redirect(url_for("usuarios.dashboard"))

        flash("Email o contraseña incorrectos.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            nombre=form.nombre.data,
            email=form.email.data,
            rol="usuario",
            creditos=5,
            activo=True
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("¡Registro exitoso! Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("auth.login"))


# Removed deprecated @bp.before_app_first_request - functionality moved to run.py
def create_default_data():
    """Create default admin user and tax configuration if they don't exist"""
    # Create default admin user
    admin = User.query.filter_by(email="admin@facturas.com").first()
    if not admin:
        admin = User(
            nombre="Administrador",
            email="admin@facturas.com",
            rol="admin",
            creditos=999,
            activo=True
        )
        admin.set_password("admin123")
        db.session.add(admin)

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

    db.session.commit()