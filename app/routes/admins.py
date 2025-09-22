from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import or_, func
from datetime import datetime, timedelta
from ..extensions import db
from ..models import Factura, ConfiguracionTasas, User, HistorialFactura, Notificacion
from ..forms import TasasForm, UserManagementForm, RevisionForm, BusquedaFacturasForm

bp = Blueprint("admins", __name__, url_prefix="/admin")

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("No tienes permisos para acceder a esta sección.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated_function


@bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """Dashboard principal para administradores"""
    # Estadísticas generales
    total_usuarios = User.query.filter_by(activo=True).count()
    total_facturas = Factura.query.count()
    facturas_pendientes = Factura.query.filter_by(estado="pendiente_admin").count()
    facturas_aprobadas_hoy = Factura.query.filter(
        Factura.estado == "aprobada",
        Factura.aprobado_en >= datetime.now().date()
    ).count()

    # Facturas recientes pendientes de aprobación
    facturas_recientes = Factura.query.filter_by(estado="pendiente_admin")\
        .order_by(Factura.actualizado_en.desc()).limit(5).all()

    # Usuarios recientes
    usuarios_recientes = User.query.order_by(User.creado_en.desc()).limit(5).all()

    # Revenue del mes actual
    mes_actual = datetime.now().replace(day=1)
    revenue_mes = db.session.query(func.sum(Factura.total_pagar))\
        .filter(Factura.estado == "aprobada", Factura.aprobado_en >= mes_actual).scalar() or 0

    return render_template("admins/dashboard.html",
                         total_usuarios=total_usuarios,
                         total_facturas=total_facturas,
                         facturas_pendientes=facturas_pendientes,
                         facturas_aprobadas_hoy=facturas_aprobadas_hoy,
                         facturas_recientes=facturas_recientes,
                         usuarios_recientes=usuarios_recientes,
                         revenue_mes=revenue_mes)


@bp.route("/tasas", methods=["GET", "POST"])
@login_required
@admin_required
def configurar_tasas():
    """Configurar tasas de impuestos"""
    # Obtener configuración actual
    tasas_actual = ConfiguracionTasas.query.order_by(ConfiguracionTasas.id.desc()).first()

    form = TasasForm()
    if tasas_actual:
        form = TasasForm(obj=tasas_actual)

    if form.validate_on_submit():
        # Crear nueva configuración
        nueva_config = ConfiguracionTasas(
            ieps=form.ieps.data,
            iva=form.iva.data,
            pvr=form.pvr.data,
            iva_pvr=form.iva_pvr.data,
            factor_conversion=form.factor_conversion.data,
            actualizado_por=current_user.id
        )

        db.session.add(nueva_config)
        db.session.commit()

        flash("Configuración de tasas actualizada exitosamente.", "success")
        return redirect(url_for("admins.configurar_tasas"))

    # Historial de cambios
    historial_tasas = ConfiguracionTasas.query.order_by(ConfiguracionTasas.actualizado_en.desc()).limit(10).all()

    return render_template("admins/configurar_tasas.html",
                         form=form,
                         tasas_actual=tasas_actual,
                         historial_tasas=historial_tasas)


@bp.route("/usuarios")
@login_required
@admin_required
def gestionar_usuarios():
    """Gestionar usuarios del sistema"""
    page = request.args.get('page', 1, type=int)

    # Búsqueda
    search = request.args.get('search', '')
    rol_filtro = request.args.get('rol', '')

    query = User.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.nombre.like(search_term),
                User.email.like(search_term)
            )
        )

    if rol_filtro:
        query = query.filter_by(rol=rol_filtro)

    query = query.order_by(User.creado_en.desc())

    usuarios = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template("admins/gestionar_usuarios.html",
                         usuarios=usuarios,
                         search=search,
                         rol_filtro=rol_filtro)


@bp.route("/usuario/<int:id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_usuario(id):
    """Editar un usuario"""
    usuario = User.query.get_or_404(id)
    form = UserManagementForm(obj=usuario)

    if form.validate_on_submit():
        usuario.nombre = form.nombre.data
        usuario.email = form.email.data
        usuario.rol = form.rol.data
        usuario.creditos = form.creditos.data
        usuario.activo = form.activo.data

        db.session.commit()
        flash(f"Usuario {usuario.nombre} actualizado exitosamente.", "success")
        return redirect(url_for("admins.gestionar_usuarios"))

    return render_template("admins/editar_usuario.html", form=form, usuario=usuario)


@bp.route("/facturas")
@login_required
@admin_required
def gestionar_facturas():
    """Gestionar todas las facturas del sistema"""
    page = request.args.get('page', 1, type=int)
    form = BusquedaFacturasForm()

    # Query base
    query = Factura.query

    # Aplicar filtros
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

    # Ordenar por fecha de actualización
    query = query.order_by(Factura.actualizado_en.desc())

    # Paginación
    facturas = query.paginate(
        page=page,
        per_page=current_app.config['INVOICES_PER_PAGE'],
        error_out=False
    )

    return render_template("admins/gestionar_facturas.html", facturas=facturas, form=form)


@bp.route("/facturas/pendientes")
@login_required
@admin_required
def facturas_pendientes():
    """Facturas pendientes de aprobación final"""
    page = request.args.get('page', 1, type=int)

    facturas = Factura.query.filter_by(estado="pendiente_admin")\
        .order_by(Factura.actualizado_en.asc())\
        .paginate(page=page, per_page=current_app.config['INVOICES_PER_PAGE'], error_out=False)

    return render_template("admins/facturas_pendientes.html", facturas=facturas)


@bp.route("/aprobar_factura/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def aprobar_factura(id):
    """Aprobar o rechazar una factura"""
    factura = Factura.query.get_or_404(id)

    if factura.estado != "pendiente_admin":
        flash("Esta factura no está disponible para aprobación.", "warning")
        return redirect(url_for("admins.facturas_pendientes"))

    form = RevisionForm()

    if form.validate_on_submit():
        estado_anterior = factura.estado
        accion = ""
        mensaje_notificacion = ""

        if form.aprobar.data:
            factura.estado = "aprobada"
            factura.admin_id = current_user.id
            factura.aprobado_en = datetime.utcnow()
            accion = "aprobacion_final"
            mensaje_notificacion = f"¡Felicidades! Tu factura #{factura.id} ha sido aprobada y está lista para el proceso de pago."

        elif form.suspender.data:
            factura.estado = "suspendida"
            factura.admin_id = current_user.id
            factura.mensaje_suspension = form.comentario.data
            accion = "suspension_admin"
            mensaje_notificacion = f"Tu factura #{factura.id} ha sido suspendida por el administrador. Revisa los comentarios."

        elif form.rechazar.data:
            factura.estado = "cancelada"
            factura.admin_id = current_user.id
            factura.mensaje_suspension = form.comentario.data
            accion = "rechazo_admin"
            mensaje_notificacion = f"Tu factura #{factura.id} ha sido rechazada por el administrador."

            # Devolver crédito al usuario
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
            titulo=f"Decisión final sobre factura #{factura.id}",
            mensaje=mensaje_notificacion,
            tipo="success" if accion == "aprobacion_final" else "warning"
        )
        db.session.add(notificacion)

        db.session.commit()

        flash(f"Factura #{factura.id} {accion.replace('_', ' ').title()} exitosamente.", "success")
        return redirect(url_for("admins.facturas_pendientes"))

    # Obtener historial
    historial = HistorialFactura.query.filter_by(factura_id=id)\
        .order_by(HistorialFactura.timestamp.desc()).all()

    return render_template("admins/aprobar_factura.html",
                         factura=factura,
                         form=form,
                         historial=historial)


@bp.route("/factura/<int:id>")
@login_required
@admin_required
def ver_factura(id):
    """Ver detalles completos de una factura"""
    factura = Factura.query.get_or_404(id)

    # Obtener historial completo
    historial = HistorialFactura.query.filter_by(factura_id=id)\
        .order_by(HistorialFactura.timestamp.desc()).all()

    return render_template("admins/ver_factura.html", factura=factura, historial=historial)


@bp.route("/estadisticas")
@login_required
@admin_required
def estadisticas():
    """Panel de estadísticas y reportes"""
    # Estadísticas de los últimos 12 meses
    doce_meses_atras = datetime.now() - timedelta(days=365)

    # Facturas por mes
    facturas_por_mes = db.session.query(
        func.date_trunc('month', Factura.creado_en),
        func.count(Factura.id)
    ).filter(Factura.creado_en >= doce_meses_atras)\
     .group_by(func.date_trunc('month', Factura.creado_en)).all()

    # Revenue por mes
    revenue_por_mes = db.session.query(
        func.date_trunc('month', Factura.aprobado_en),
        func.sum(Factura.total_pagar)
    ).filter(
        Factura.estado == "aprobada",
        Factura.aprobado_en >= doce_meses_atras
    ).group_by(func.date_trunc('month', Factura.aprobado_en)).all()

    # Distribución por estado
    estados_distribution = db.session.query(
        Factura.estado,
        func.count(Factura.id)
    ).group_by(Factura.estado).all()

    # Top usuarios por facturas
    top_usuarios = db.session.query(
        User.nombre,
        func.count(Factura.id)
    ).join(Factura).group_by(User.nombre)\
     .order_by(func.count(Factura.id).desc()).limit(10).all()

    return render_template("admins/estadisticas.html",
                         facturas_por_mes=facturas_por_mes,
                         revenue_por_mes=revenue_por_mes,
                         estados_distribution=estados_distribution,
                         top_usuarios=top_usuarios)


@bp.route("/crear_factura", methods=["GET", "POST"])
@login_required
@admin_required
def crear_factura():
    """Permite al admin crear facturas"""
    from ..forms import CrearFacturaForm
    from ..models import User

    form = CrearFacturaForm()

    # Poblar choices para usuario
    usuarios = User.query.filter_by(activo=True, rol='usuario').all()
    form.usuario_id.choices = [(u.id, f"{u.nombre} ({u.email})") for u in usuarios]

    if form.validate_on_submit():
        try:
            # Buscar usuario seleccionado
            usuario_seleccionado = User.query.get(form.usuario_id.data)
            if not usuario_seleccionado:
                flash("Usuario no válido.", "error")
                return render_template("admins/crear_factura.html", form=form)

            # Obtener tasas actuales
            tasas_actual = ConfiguracionTasas.query.order_by(ConfiguracionTasas.actualizado_en.desc()).first()
            if not tasas_actual:
                flash("No se han configurado las tasas. Configure primero las tasas.", "error")
                return redirect(url_for('admins.configurar_tasas'))

            # Calcular valor CIF
            valor_cif = form.valor_fob.data + form.flete.data

            # Calcular impuestos
            ieps = valor_cif * (tasas_actual.ieps / 100)
            base_iva = valor_cif + ieps
            iva = base_iva * tasas_actual.iva
            pvr = valor_cif * tasas_actual.pvr
            iva_pvr = pvr * tasas_actual.iva_pvr
            total_pagar = valor_cif + ieps + iva + pvr + iva_pvr

            # Crear nueva factura
            nueva_factura = Factura(
                usuario_id=usuario_seleccionado.id,
                importador=form.importador.data,
                descripcion_producto=form.descripcion_producto.data,
                cantidad=form.cantidad.data,
                unidad_medida=form.unidad_medida.data,
                valor_fob=form.valor_fob.data,
                flete=form.flete.data,
                valor_cif=valor_cif,
                ieps=ieps,
                iva=iva,
                pvr=pvr,
                iva_pvr=iva_pvr,
                total_pagar=total_pagar,
                estado='aprobada',  # Admin puede crear facturas pre-aprobadas
                creado_por_admin=True,
                aprobado_en=datetime.now(),
                aprobado_por=current_user.id
            )

            db.session.add(nueva_factura)
            db.session.commit()

            flash(f"Factura #{nueva_factura.id} creada exitosamente para {usuario_seleccionado.nombre}.", "success")
            return redirect(url_for('admins.ver_factura', id=nueva_factura.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear la factura: {str(e)}", "error")

    return render_template("admins/crear_factura.html", form=form)


@bp.route("/api/stats")
@login_required
@admin_required
def api_stats():
    """API endpoint para obtener estadísticas en tiempo real"""
    stats = {
        'total_usuarios': User.query.filter_by(activo=True).count(),
        'total_facturas': Factura.query.count(),
        'facturas_pendientes': Factura.query.filter_by(estado="pendiente_admin").count(),
        'facturas_aprobadas_mes': Factura.query.filter(
            Factura.estado == "aprobada",
            Factura.aprobado_en >= datetime.now().replace(day=1)
        ).count(),
        'revenue_mes': float(db.session.query(func.sum(Factura.total_pagar))
                           .filter(Factura.estado == "aprobada",
                                 Factura.aprobado_en >= datetime.now().replace(day=1))
                           .scalar() or 0)
    }
    return jsonify(stats)