from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

# =====================
# USUARIOS
# =====================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="usuario")  # admin, supervisor, usuario
    creditos = db.Column(db.Integer, default=5)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    facturas = db.relationship("Factura", foreign_keys="Factura.usuario_id", backref="usuario", lazy=True)
    facturas_supervisadas = db.relationship("Factura", foreign_keys="Factura.supervisor_id", backref="supervisor", lazy=True)
    facturas_administradas = db.relationship("Factura", foreign_keys="Factura.admin_id", backref="admin", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.rol == "admin"

    def is_supervisor(self):
        return self.rol == "supervisor"

    def is_usuario(self):
        return self.rol == "usuario"

    def __repr__(self):
        return f"<User {self.email} ({self.rol})>"


# =====================
# CONFIGURACIÓN DE TASAS
# =====================
class ConfiguracionTasas(db.Model):
    __tablename__ = "configuracion_tasas"

    id = db.Column(db.Integer, primary_key=True)
    ieps = db.Column(db.Float, default=4.59)   # por galón
    iva = db.Column(db.Float, default=0.16)    # %
    pvr = db.Column(db.Float, default=0.20)    # por galón
    iva_pvr = db.Column(db.Float, default=0.16) # %

    # Conversion factor (can be updated)
    factor_conversion = db.Column(db.Float, default=0.264172)  # litros → galones

    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    actualizado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def __repr__(self):
        return f"<Tasas IEPS={self.ieps}, IVA={self.iva}, PVR={self.pvr}, IVA_PVR={self.iva_pvr}>"


# =====================
# FACTURAS
# =====================
class Factura(db.Model):
    __tablename__ = "facturas"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    estado = db.Column(db.String(30), default="borrador", nullable=False)
    # Estados: borrador, pendiente_supervisor, pendiente_admin, aprobada, suspendida, cancelada
    mensaje_suspension = db.Column(db.Text, nullable=True)

    # Datos de identificación
    importador = db.Column(db.String(150), nullable=False)
    rfc = db.Column(db.String(50), nullable=False)
    numero_pedimento = db.Column(db.String(50), nullable=False)
    numero_aduana = db.Column(db.String(50), nullable=False)
    patente_aduanal = db.Column(db.String(50), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)

    # Payment tracking
    linea_captura = db.Column(db.String(100), nullable=True)
    estado_pago = db.Column(db.String(20), default="no_pagado")
    # Estados de pago: no_pagado, en_proceso, pagado, rechazado

    tipo = db.Column(db.String(20), nullable=False)  # full, carrotanque, barcaza

    # Volúmenes en litros
    litros_rem1 = db.Column(db.Float, default=0.0)
    litros_rem2 = db.Column(db.Float, default=0.0)
    litros_carrotanque = db.Column(db.Float, default=0.0)
    litros_barcaza = db.Column(db.Float, default=0.0)

    # Volúmenes en galones (calculados)
    galones_rem1 = db.Column(db.Float, default=0.0)
    galones_rem2 = db.Column(db.Float, default=0.0)
    galones_carrotanque = db.Column(db.Float, default=0.0)
    galones_barcaza = db.Column(db.Float, default=0.0)

    # Datos financieros
    precio_molecula_galon = db.Column(db.Float, default=0.0)
    galones_totales = db.Column(db.Float, default=0.0)
    importe_invoice = db.Column(db.Float, default=0.0)

    densidad = db.Column(db.Float, default=0.0)
    peso_bruto = db.Column(db.Float, default=0.0)

    tipo_cambio = db.Column(db.Float, default=0.0)
    valor_aduana_pago = db.Column(db.Float, default=0.0)

    # Impuestos calculados
    ieps = db.Column(db.Float, default=0.0)
    iva = db.Column(db.Float, default=0.0)
    pvr = db.Column(db.Float, default=0.0)
    iva_pvr = db.Column(db.Float, default=0.0)

    # Total a pagar
    total_impuestos = db.Column(db.Float, default=0.0)
    total_pagar = db.Column(db.Float, default=0.0)

    # Timestamps
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    aprobado_en = db.Column(db.DateTime, nullable=True)

    # Relationships
    historial = db.relationship("HistorialFactura", backref="factura", lazy=True, cascade="all, delete-orphan")

    def calcular_totales(self, tasas: ConfiguracionTasas):
        """Calcula todos los totales usando las tasas configuradas"""
        factor = tasas.factor_conversion

        # Convertir litros a galones
        self.galones_rem1 = self.litros_rem1 * factor
        self.galones_rem2 = self.litros_rem2 * factor
        self.galones_carrotanque = self.litros_carrotanque * factor
        self.galones_barcaza = self.litros_barcaza * factor

        # Calcular galones totales
        self.galones_totales = (
            (self.galones_rem1 or 0) +
            (self.galones_rem2 or 0) +
            (self.galones_carrotanque or 0) +
            (self.galones_barcaza or 0)
        )

        # Calcular importe invoice
        self.importe_invoice = self.galones_totales * (self.precio_molecula_galon or 0)

        # Calcular impuestos con tasas configuradas
        monto_ieps = self.galones_totales * tasas.ieps
        monto_iva = (self.importe_invoice + monto_ieps) * tasas.iva
        monto_pvr = self.galones_totales * tasas.pvr
        monto_iva_pvr = monto_pvr * tasas.iva_pvr

        # Guardar resultados
        self.ieps = round(monto_ieps, 2)
        self.iva = round(monto_iva, 2)
        self.pvr = round(monto_pvr, 2)
        self.iva_pvr = round(monto_iva_pvr, 2)

        # Calcular totales
        self.total_impuestos = round(self.ieps + self.iva + self.pvr + self.iva_pvr, 2)
        self.total_pagar = round(self.importe_invoice + self.total_impuestos, 2)

        return {
            "galones_totales": self.galones_totales,
            "importe_invoice": self.importe_invoice,
            "ieps": self.ieps,
            "iva": self.iva,
            "pvr": self.pvr,
            "iva_pvr": self.iva_pvr,
            "total_impuestos": self.total_impuestos,
            "total_pagar": self.total_pagar,
        }

    def get_estado_display(self):
        """Returns a user-friendly display of the current state"""
        estados = {
            "borrador": "Borrador",
            "pendiente_supervisor": "Pendiente de Revisión",
            "pendiente_admin": "Pendiente de Aprobación",
            "aprobada": "Aprobada",
            "suspendida": "Suspendida",
            "cancelada": "Cancelada"
        }
        return estados.get(self.estado, self.estado)

    def get_estado_pago_display(self):
        """Returns a user-friendly display of the payment state"""
        estados = {
            "no_pagado": "No Pagado",
            "en_proceso": "En Proceso",
            "pagado": "Pagado",
            "rechazado": "Rechazado"
        }
        return estados.get(self.estado_pago, self.estado_pago)

    def can_edit(self, user):
        """Check if user can edit this invoice"""
        if user.is_admin():
            return True
        if self.usuario_id == user.id and self.estado in ["borrador", "suspendida"]:
            return True
        return False

    def can_review(self, user):
        """Check if user can review this invoice"""
        if user.is_supervisor() and self.estado == "pendiente_supervisor":
            return True
        if user.is_admin() and self.estado == "pendiente_admin":
            return True
        return False

    def __repr__(self):
        return f"<Factura {self.id} - {self.importador} ({self.estado})>"


# =====================
# HISTORIAL DE FACTURAS
# =====================
class HistorialFactura(db.Model):
    __tablename__ = "historial_facturas"

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    accion = db.Column(db.String(50), nullable=False)  # creacion, revision, aprobacion, suspension, cancelacion
    comentario = db.Column(db.Text, nullable=True)
    estado_anterior = db.Column(db.String(30), nullable=True)
    estado_nuevo = db.Column(db.String(30), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    usuario = db.relationship("User", backref="acciones_historial")

    def __repr__(self):
        return f"<HistorialFactura {self.accion} - Factura {self.factura_id}>"


# =====================
# NOTIFICACIONES
# =====================
class Notificacion(db.Model):
    __tablename__ = "notificaciones"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    factura_id = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=True)

    titulo = db.Column(db.String(200), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20), default="info")  # info, success, warning, error
    leida = db.Column(db.Boolean, default=False)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    usuario = db.relationship("User", backref="notificaciones")
    factura = db.relationship("Factura", backref="notificaciones")

    def __repr__(self):
        return f"<Notificacion {self.titulo} - Usuario {self.usuario_id}>"