from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import or_
from ..extensions import db
from ..models import Factura, HistorialFactura, Notificacion, User
from ..forms import RevisionForm, BusquedaFacturasForm

bp = Blueprint("supervisores", __name__, url_prefix="/supervisores")

def supervisor_required(f):
    """Decorator to require supervisor role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_supervisor() or current_user.is_admin()):
            flash("No tienes permisos para acceder a esta sección.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated_function


@bp.route("/dashboard")
@login_required
@supervisor_required
def dashboard():
    """Dashboard principal para supervisores"""
    # Facturas pendientes de revisión
    facturas_pendientes = Factura.query.filter_by(estado="pendiente_supervisor").count()

    # Facturas revisadas por este supervisor
    facturas_revisadas = Factura.query.filter_by(supervisor_id=current_user.id).count()

    # Facturas revisadas hoy
    from datetime import datetime, timedelta
    hoy = datetime.now().date()
    facturas_hoy = HistorialFactura.query.filter(
        HistorialFactura.usuario_id == current_user.id,
        HistorialFactura.accion == "revision",
        HistorialFactura.timestamp >= hoy
    ).count()

    # Facturas pendientes recientes
    facturas_recientes = Factura.query.filter_by(estado="pendiente_supervisor")\
        .order_by(Factura.creado_en.desc()).limit(5).all()

    # Notificaciones no leídas
    notificaciones = Notificacion.query.filter_by(
        usuario_id=current_user.id,
        leida=False
    ).order_by(Notificacion.creado_en.desc()).limit(5).all()

    return render_template("supervisores/dashboard.html",
                         facturas_pendientes=facturas_pendientes,
                         facturas_revisadas=facturas_revisadas,
                         facturas_hoy=facturas_hoy,
                         facturas_recientes=facturas_recientes,
                         notificaciones=notificaciones)


@bp.route("/facturas")
@login_required
@supervisor_required
def facturas_por_revisar():
    """Listar facturas pendientes de revisión"""
    page = request.args.get('page', 1, type=int)
    form = BusquedaFacturasForm()

    # Query base - facturas pendientes de supervisor
    query = Factura.query.filter_by(estado="pendiente_supervisor")

    # Aplicar filtros si hay búsqueda
    if request.args.get('search'):
        search_term = f"%{request.args.get('search')}%"
        query = query.filter(
            or_(
                Factura.importador.like(search_term),
                Factura.rfc.like(search_term),
                Factura.numero_pedimento.like(search_term)
            )
        )

    # Ordenar por fecha de creación (más antiguas primero para revisar)
    query = query.order_by(Factura.creado_en.asc())

    # Paginación
    facturas = query.paginate(
        page=page,
        per_page=current_app.config['INVOICES_PER_PAGE'],
        error_out=False
    )

    return render_template("supervisores/facturas_por_revisar.html", facturas=facturas, form=form)


@bp.route("/revisar/<int:id>", methods=["GET", "POST"])
@login_required
@supervisor_required
def revisar_factura(id):
    """Revisar una factura específica"""
    factura = Factura.query.get_or_404(id)

    if factura.estado != "pendiente_supervisor":
        flash("Esta factura no está disponible para revisión.", "warning")
        return redirect(url_for("supervisores.facturas_por_revisar"))

    form = RevisionForm()

    if form.validate_on_submit():
        estado_anterior = factura.estado
        accion = ""
        mensaje_notificacion = ""

        if form.aprobar.data:
            factura.estado = "pendiente_admin"
            factura.supervisor_id = current_user.id
            accion = "revision_aprobada"
            mensaje_notificacion = f"Tu factura #{factura.id} ha sido aprobada por el supervisor y enviada al administrador."

            # Notificar a administradores
            admins = User.query.filter_by(rol="admin", activo=True).all()
            for admin in admins:
                notificacion = Notificacion(
                    usuario_id=admin.id,
                    factura_id=factura.id,
                    titulo="Factura aprobada por supervisor",
                    mensaje=f"La factura #{factura.id} ha sido aprobada por {current_user.nombre} y requiere aprobación final.",
                    tipo="info"
                )
                db.session.add(notificacion)

        elif form.suspender.data:
            factura.estado = "suspendida"
            factura.supervisor_id = current_user.id
            factura.mensaje_suspension = form.comentario.data
            accion = "suspension"
            mensaje_notificacion = f"Tu factura #{factura.id} ha sido suspendida. Revisa los comentarios y corrígela."

        elif form.rechazar.data:
            factura.estado = "cancelada"
            factura.supervisor_id = current_user.id
            factura.mensaje_suspension = form.comentario.data
            accion = "rechazo"
            mensaje_notificacion = f"Tu factura #{factura.id} ha sido rechazada."

            # Devolver crédito al usuario si se rechaza
            factura.usuario.creditos += 1

        # Registrar en historial
        historial = HistorialFactura(
            factura_id=factura.id,
            usuario_id=current_user.id,
            accion=accion,
            comentario=form.comentario.data,
            estado_anterior=estado_anterior,
            estado_nuevo=factura.estado
        )
        db.session.add(historial)

        # Notificar al usuario
        notificacion = Notificacion(
            usuario_id=factura.usuario_id,
            factura_id=factura.id,
            titulo=f"Actualización de factura #{factura.id}",
            mensaje=mensaje_notificacion,
            tipo="info" if accion == "revision_aprobada" else "warning"
        )
        db.session.add(notificacion)

        db.session.commit()

        flash(f"Factura #{factura.id} {accion.replace('_', ' ').title()} exitosamente.", "success")
        return redirect(url_for("supervisores.facturas_por_revisar"))

    # Obtener historial de la factura
    historial = HistorialFactura.query.filter_by(factura_id=id)\
        .order_by(HistorialFactura.timestamp.desc()).all()

    return render_template("supervisores/revisar_factura.html",
                         factura=factura,
                         form=form,
                         historial=historial)


@bp.route("/mis_revisiones")
@login_required
@supervisor_required
def mis_revisiones():
    """Ver facturas revisadas por este supervisor"""
    page = request.args.get('page', 1, type=int)
    form = BusquedaFacturasForm()

    # Query base - facturas revisadas por este supervisor
    query = Factura.query.filter_by(supervisor_id=current_user.id)

    # Aplicar filtros si hay búsqueda
    if request.args.get('search'):
        search_term = f"%{request.args.get('search')}%"
        query = query.filter(
            or_(
                Factura.importador.like(search_term),
                Factura.rfc.like(search_term),
                Factura.numero_pedimento.like(search_term)
            )
        )

    if request.args.get('estado'):
        query = query.filter_by(estado=request.args.get('estado'))

    # Ordenar por fecha de actualización (más recientes primero)
    query = query.order_by(Factura.actualizado_en.desc())

    # Paginación
    facturas = query.paginate(
        page=page,
        per_page=current_app.config['INVOICES_PER_PAGE'],
        error_out=False
    )

    return render_template("supervisores/mis_revisiones.html", facturas=facturas, form=form)


@bp.route("/factura/<int:id>")
@login_required
@supervisor_required
def ver_factura(id):
    """Ver detalles de una factura"""
    factura = Factura.query.get_or_404(id)

    # Obtener historial
    historial = HistorialFactura.query.filter_by(factura_id=id)\
        .order_by(HistorialFactura.timestamp.desc()).all()

    return render_template("supervisores/ver_factura.html", factura=factura, historial=historial)


@bp.route("/estadisticas")
@login_required
@supervisor_required
def estadisticas():
    """Estadísticas de revisión para supervisores"""
    from datetime import datetime, timedelta
    from sqlalchemy import func

    # Facturas revisadas por mes (últimos 6 meses)
    seis_meses_atras = datetime.now() - timedelta(days=180)

    revisiones_por_mes = db.session.query(
        func.date_trunc('month', HistorialFactura.timestamp),
        func.count(HistorialFactura.id)
    ).filter(
        HistorialFactura.usuario_id == current_user.id,
        HistorialFactura.accion.in_(['revision_aprobada', 'suspension', 'rechazo']),
        HistorialFactura.timestamp >= seis_meses_atras
    ).group_by(func.date_trunc('month', HistorialFactura.timestamp)).all()

    # Distribución de acciones
    acciones_stats = db.session.query(
        HistorialFactura.accion,
        func.count(HistorialFactura.id)
    ).filter(
        HistorialFactura.usuario_id == current_user.id,
        HistorialFactura.accion.in_(['revision_aprobada', 'suspension', 'rechazo'])
    ).group_by(HistorialFactura.accion).all()

    return render_template("supervisores/estadisticas.html",
                         revisiones_por_mes=revisiones_por_mes,
                         acciones_stats=acciones_stats)