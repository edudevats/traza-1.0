from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for("admins.dashboard"))
        elif current_user.is_supervisor():
            return redirect(url_for("supervisores.dashboard"))
        else:
            return redirect(url_for("usuarios.dashboard"))
    return redirect(url_for("auth.login"))