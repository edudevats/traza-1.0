from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from ..extensions import db
from ..models import Factura, ConfiguracionTasas, HistorialFactura, Notificacion
from ..forms import FacturaForm, BusquedaFacturasForm

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

@bp.route("/dashboard")
@login_required
def dashboard():
    """Dashboard principal para usuarios"""
    # Obtener estadísticas del usuario
    facturas_totales = Factura.query.filter_by(usuario_id=current_user.id).count()
    facturas_pendientes = Factura.query.filter_by(
        usuario_id=current_user.id,
        estado="pendiente_supervisor"
    ).count()
    facturas_aprobadas = Factura.query.filter_by(
        usuario_id=current_user.id,
        estado="aprobada"
    ).count()

    # Facturas recientes
    facturas_recientes = Factura.query.filter_by(usuario_id=current_user.id)\
        .order_by(Factura.creado_en.desc()).limit(5).all()

    # Notificaciones no leídas
    notificaciones = Notificacion.query.filter_by(
        usuario_id=current_user.id,
        leida=False
    ).order_by(Notificacion.creado_en.desc()).limit(5).all()

    return render_template("usuarios/dashboard.html",
                         facturas_totales=facturas_totales,
                         facturas_pendientes=facturas_pendientes,
                         facturas_aprobadas=facturas_aprobadas,
                         facturas_recientes=facturas_recientes,
                         notificaciones=notificaciones)


@bp.route("/crear_factura", methods=["GET", "POST"])
@login_required
def crear_factura():
    """Crear nueva factura"""
    if current_user.creditos <= 0:
        flash("No tienes créditos suficientes para crear facturas. Contacta al administrador.", "warning")
        return redirect(url_for("usuarios.dashboard"))

    form = FacturaForm()
    if form.validate_on_submit():
        # Obtener tasas actuales
        tasas = ConfiguracionTasas.query.order_by(ConfiguracionTasas.id.desc()).first()
        if not tasas:
            flash("No se han configurado las tasas. Contacta al administrador.", "error")
            return redirect(url_for("usuarios.dashboard"))

        # Crear nueva factura
        factura = Factura(
            usuario_id=current_user.id,
            importador=form.importador.data,
            rfc=form.rfc.data,
            numero_pedimento=form.numero_pedimento.data,
            numero_aduana=form.numero_aduana.data,
            patente_aduanal=form.patente_aduanal.data,
            tipo=form.tipo.data,
            litros_rem1=form.litros_rem1.data or 0,
            litros_rem2=form.litros_rem2.data or 0,
            litros_carrotanque=form.litros_carrotanque.data or 0,
            litros_barcaza=form.litros_barcaza.data or 0,
            precio_molecula_galon=form.precio_molecula_galon.data,
            densidad=form.densidad.data or 0,
            peso_bruto=form.peso_bruto.data or 0,
            tipo_cambio=form.tipo_cambio.data or 0,
            estado="pendiente_supervisor"
        )

        # Calcular totales
        factura.calcular_totales(tasas)

        # Descontar crédito
        current_user.creditos -= 1

        # Guardar en base de datos
        db.session.add(factura)
        db.session.flush()  # To get the factura.id

        # Registrar en historial
        historial = HistorialFactura(
            factura_id=factura.id,
            usuario_id=current_user.id,
            accion="creacion",
            estado_anterior="",
            estado_nuevo="pendiente_supervisor"
        )
        db.session.add(historial)

        # Crear notificación para supervisores
        from ..models import User
        supervisores = User.query.filter_by(rol="supervisor", activo=True).all()
        for supervisor in supervisores:
            notificacion = Notificacion(
                usuario_id=supervisor.id,
                factura_id=factura.id,
                titulo="Nueva factura para revisar",
                mensaje=f"El usuario {current_user.nombre} ha creado una nueva factura (#{factura.id}) que requiere revisión.",
                tipo="info"
            )
            db.session.add(notificacion)

        db.session.commit()

        flash(f"Factura #{factura.id} creada exitosamente y enviada para revisión.", "success")
        return redirect(url_for("usuarios.ver_factura", id=factura.id))

    # Obtener tasas actuales para mostrar en el formulario
    tasas = ConfiguracionTasas.query.order_by(ConfiguracionTasas.id.desc()).first()

    return render_template("usuarios/crear_factura.html", form=form, tasas=tasas)


@bp.route("/facturas")
@login_required
def mis_facturas():
    """Listar todas las facturas del usuario"""
    page = request.args.get('page', 1, type=int)
    form = BusquedaFacturasForm()

    # Query base
    query = Factura.query.filter_by(usuario_id=current_user.id)

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

    if request.args.get('estado_pago'):
        query = query.filter_by(estado_pago=request.args.get('estado_pago'))

    # Ordenar por fecha de creación (más recientes primero)
    query = query.order_by(Factura.creado_en.desc())

    # Paginación
    facturas = query.paginate(
        page=page,
        per_page=current_app.config['INVOICES_PER_PAGE'],
        error_out=False
    )

    return render_template("usuarios/mis_facturas.html", facturas=facturas, form=form)


@bp.route("/factura/<int:id>")
@login_required
def ver_factura(id):
    """Ver detalles de una factura"""
    factura = Factura.query.get_or_404(id)

    # Verificar que el usuario pueda ver esta factura
    if factura.usuario_id != current_user.id and not current_user.is_admin():
        flash("No tienes permisos para ver esta factura.", "danger")
        return redirect(url_for("usuarios.dashboard"))

    # Obtener historial
    historial = HistorialFactura.query.filter_by(factura_id=id)\
        .order_by(HistorialFactura.timestamp.desc()).all()

    return render_template("usuarios/ver_factura.html", factura=factura, historial=historial)


@bp.route("/editar_factura/<int:id>", methods=["GET", "POST"])
@login_required
def editar_factura(id):
    """Editar una factura (solo si está en borrador o suspendida)"""
    factura = Factura.query.get_or_404(id)

    # Verificar permisos
    if not factura.can_edit(current_user):
        flash("No puedes editar esta factura en su estado actual.", "danger")
        return redirect(url_for("usuarios.ver_factura", id=id))

    form = FacturaForm(obj=factura)
    if form.validate_on_submit():
        # Obtener tasas actuales
        tasas = ConfiguracionTasas.query.order_by(ConfiguracionTasas.id.desc()).first()

        # Actualizar datos
        estado_anterior = factura.estado
        form.populate_obj(factura)

        # Asegurar que los valores nulos se conviertan a 0
        factura.litros_rem1 = factura.litros_rem1 or 0
        factura.litros_rem2 = factura.litros_rem2 or 0
        factura.litros_carrotanque = factura.litros_carrotanque or 0
        factura.litros_barcaza = factura.litros_barcaza or 0
        factura.densidad = factura.densidad or 0
        factura.peso_bruto = factura.peso_bruto or 0
        factura.tipo_cambio = factura.tipo_cambio or 0

        # Recalcular totales
        factura.calcular_totales(tasas)

        # Si estaba suspendida, cambiar a pendiente_supervisor
        if estado_anterior == "suspendida":
            factura.estado = "pendiente_supervisor"

        # Registrar en historial
        historial = HistorialFactura(
            factura_id=factura.id,
            usuario_id=current_user.id,
            accion="edicion",
            estado_anterior=estado_anterior,
            estado_nuevo=factura.estado
        )
        db.session.add(historial)

        db.session.commit()

        flash("Factura actualizada exitosamente.", "success")
        return redirect(url_for("usuarios.ver_factura", id=id))

    return render_template("usuarios/editar_factura.html", form=form, factura=factura)


@bp.route("/notificaciones")
@login_required
def notificaciones():
    """Ver todas las notificaciones del usuario"""
    page = request.args.get('page', 1, type=int)

    notificaciones = Notificacion.query.filter_by(usuario_id=current_user.id)\
        .order_by(Notificacion.creado_en.desc())\
        .paginate(page=page, per_page=20, error_out=False)

    return render_template("usuarios/notificaciones.html", notificaciones=notificaciones)


@bp.route("/marcar_notificacion_leida/<int:id>")
@login_required
def marcar_notificacion_leida(id):
    """Marcar una notificación como leída"""
    notificacion = Notificacion.query.get_or_404(id)

    if notificacion.usuario_id != current_user.id:
        flash("No tienes permisos para esta acción.", "danger")
        return redirect(url_for("usuarios.notificaciones"))

    notificacion.leida = True
    db.session.commit()

    return redirect(url_for("usuarios.notificaciones"))