import os
import uuid
from datetime import datetime
from flask import current_app
from .models import ConfiguracionTasas, Notificacion
from .extensions import db

def generate_unique_filename(original_filename):
    """Generate a unique filename for file uploads"""
    ext = os.path.splitext(original_filename)[1]
    unique_filename = str(uuid.uuid4()) + ext
    return unique_filename

def format_currency(amount, currency='USD'):
    """Format currency for display"""
    if currency == 'USD':
        return f"${amount:,.2f} USD"
    elif currency == 'MXN':
        return f"${amount:,.2f} MXN"
    else:
        return f"{amount:,.2f} {currency}"

def format_number(number, decimals=2):
    """Format numbers for display"""
    return f"{number:,.{decimals}f}"

def get_current_tax_rates():
    """Get the current tax configuration"""
    return ConfiguracionTasas.query.order_by(ConfiguracionTasas.id.desc()).first()

def create_notification(user_id, title, message, notification_type='info', factura_id=None):
    """Create a notification for a user"""
    notification = Notificacion(
        usuario_id=user_id,
        factura_id=factura_id,
        titulo=title,
        mensaje=message,
        tipo=notification_type
    )
    db.session.add(notification)
    return notification

def calculate_invoice_totals(factura, tasas=None):
    """Calculate all totals for an invoice"""
    if not tasas:
        tasas = get_current_tax_rates()

    if not tasas:
        raise ValueError("No tax configuration found")

    return factura.calcular_totales(tasas)

def get_estado_badge_class(estado):
    """Get Bootstrap badge class for invoice state"""
    estado_classes = {
        'borrador': 'secondary',
        'pendiente_supervisor': 'warning',
        'pendiente_admin': 'info',
        'aprobada': 'success',
        'suspendida': 'danger',
        'cancelada': 'dark'
    }
    return estado_classes.get(estado, 'secondary')

def get_pago_badge_class(estado_pago):
    """Get Bootstrap badge class for payment state"""
    pago_classes = {
        'no_pagado': 'secondary',
        'en_proceso': 'warning',
        'pagado': 'success',
        'rechazado': 'danger'
    }
    return pago_classes.get(estado_pago, 'secondary')

def validate_file_upload(file, allowed_extensions=None):
    """Validate uploaded files"""
    if not allowed_extensions:
        allowed_extensions = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}

    if not file or file.filename == '':
        return False, "No file selected"

    if '.' not in file.filename:
        return False, "File must have an extension"

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_extensions:
        return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"

    # Check file size (max 16MB as configured)
    if hasattr(current_app, 'config') and current_app.config.get('MAX_CONTENT_LENGTH'):
        max_size = current_app.config['MAX_CONTENT_LENGTH']
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > max_size:
            return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"

    return True, "File is valid"

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def get_user_dashboard_stats(user):
    """Get dashboard statistics for a user"""
    from .models import Factura

    stats = {
        'total_facturas': Factura.query.filter_by(usuario_id=user.id).count(),
        'facturas_pendientes': Factura.query.filter_by(
            usuario_id=user.id,
            estado='pendiente_supervisor'
        ).count(),
        'facturas_aprobadas': Factura.query.filter_by(
            usuario_id=user.id,
            estado='aprobada'
        ).count(),
        'facturas_suspendidas': Factura.query.filter_by(
            usuario_id=user.id,
            estado='suspendida'
        ).count()
    }

    return stats

def get_supervisor_dashboard_stats(user):
    """Get dashboard statistics for a supervisor"""
    from .models import Factura, HistorialFactura
    from datetime import date

    stats = {
        'facturas_pendientes': Factura.query.filter_by(estado='pendiente_supervisor').count(),
        'facturas_revisadas': Factura.query.filter_by(supervisor_id=user.id).count(),
        'revisiones_hoy': HistorialFactura.query.filter(
            HistorialFactura.usuario_id == user.id,
            HistorialFactura.accion.in_(['revision_aprobada', 'suspension', 'rechazo']),
            HistorialFactura.timestamp >= date.today()
        ).count()
    }

    return stats

def get_admin_dashboard_stats():
    """Get dashboard statistics for admin"""
    from .models import User, Factura
    from datetime import date
    from sqlalchemy import func

    stats = {
        'total_usuarios': User.query.filter_by(activo=True).count(),
        'total_facturas': Factura.query.count(),
        'facturas_pendientes': Factura.query.filter_by(estado='pendiente_admin').count(),
        'facturas_aprobadas_hoy': Factura.query.filter(
            Factura.estado == 'aprobada',
            Factura.aprobado_en >= date.today()
        ).count(),
        'revenue_mes': db.session.query(func.sum(Factura.total_pagar)).filter(
            Factura.estado == 'aprobada',
            Factura.aprobado_en >= date.today().replace(day=1)
        ).scalar() or 0
    }

    return stats

class InvoiceStatusManager:
    """Manage invoice status transitions"""

    VALID_TRANSITIONS = {
        'borrador': ['pendiente_supervisor', 'cancelada'],
        'pendiente_supervisor': ['pendiente_admin', 'suspendida', 'cancelada'],
        'pendiente_admin': ['aprobada', 'suspendida', 'cancelada'],
        'suspendida': ['pendiente_supervisor', 'cancelada'],
        'aprobada': [],  # Final state
        'cancelada': []  # Final state
    }

    @classmethod
    def can_transition(cls, from_state, to_state):
        """Check if a state transition is valid"""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def get_available_actions(cls, current_state, user_role):
        """Get available actions for a user on an invoice"""
        actions = []

        if current_state == 'pendiente_supervisor' and user_role in ['supervisor', 'admin']:
            actions.extend(['aprobar', 'suspender', 'rechazar'])
        elif current_state == 'pendiente_admin' and user_role == 'admin':
            actions.extend(['aprobar', 'suspender', 'rechazar'])
        elif current_state == 'suspendida' and user_role == 'usuario':
            actions.extend(['editar'])

        return actions

def log_invoice_action(factura_id, user_id, action, comment=None, old_state=None, new_state=None):
    """Log an action in the invoice history"""
    from .models import HistorialFactura

    history_entry = HistorialFactura(
        factura_id=factura_id,
        usuario_id=user_id,
        accion=action,
        comentario=comment,
        estado_anterior=old_state,
        estado_nuevo=new_state
    )

    db.session.add(history_entry)
    return history_entry

def send_notification_to_role(role, title, message, factura_id=None):
    """Send notification to all users with a specific role"""
    from .models import User

    users = User.query.filter_by(rol=role, activo=True).all()
    notifications = []

    for user in users:
        notification = create_notification(
            user_id=user.id,
            title=title,
            message=message,
            factura_id=factura_id
        )
        notifications.append(notification)

    return notifications

# Template filters
def register_template_filters(app):
    """Register custom template filters"""

    @app.template_filter('currency')
    def currency_filter(amount, currency='USD'):
        return format_currency(amount, currency)

    @app.template_filter('number')
    def number_filter(number, decimals=2):
        return format_number(number, decimals)

    @app.template_filter('estado_badge')
    def estado_badge_filter(estado):
        return get_estado_badge_class(estado)

    @app.template_filter('pago_badge')
    def pago_badge_filter(estado_pago):
        return get_pago_badge_class(estado_pago)

    @app.template_filter('datetime_format')
    def datetime_format_filter(dt, format='%d/%m/%Y %H:%M'):
        if dt:
            return dt.strftime(format)
        return ''