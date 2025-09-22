from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, FloatField, IntegerField, SelectField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError
from .models import User

# =====================
# Login / Registro
# =====================
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()],
                       render_kw={"class": "form-control", "placeholder": "Ingresa tu email"})
    password = PasswordField("Contraseña", validators=[DataRequired()],
                           render_kw={"class": "form-control", "placeholder": "Ingresa tu contraseña"})
    submit = SubmitField("Iniciar sesión", render_kw={"class": "btn btn-primary w-100"})


class RegisterForm(FlaskForm):
    nombre = StringField("Nombre completo", validators=[DataRequired(), Length(min=2, max=100)],
                        render_kw={"class": "form-control", "placeholder": "Ingresa tu nombre completo"})
    email = StringField("Email", validators=[DataRequired(), Email()],
                       render_kw={"class": "form-control", "placeholder": "Ingresa tu email"})
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=6, max=50)],
                           render_kw={"class": "form-control", "placeholder": "Mínimo 6 caracteres"})
    submit = SubmitField("Registrarse", render_kw={"class": "btn btn-success w-100"})

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email ya está registrado. Por favor usa otro.')


# =====================
# Factura
# =====================
class FacturaForm(FlaskForm):
    # Datos de identificación
    importador = StringField("Importador", validators=[DataRequired(), Length(max=150)],
                           render_kw={"class": "form-control", "placeholder": "Nombre del importador"})
    rfc = StringField("RFC", validators=[DataRequired(), Length(max=50)],
                     render_kw={"class": "form-control", "placeholder": "RFC del importador"})
    numero_pedimento = StringField("Número de pedimento", validators=[DataRequired(), Length(max=50)],
                                 render_kw={"class": "form-control", "placeholder": "Número de pedimento"})
    numero_aduana = StringField("Número de aduana", validators=[DataRequired(), Length(max=50)],
                              render_kw={"class": "form-control", "placeholder": "Número de aduana"})
    patente_aduanal = StringField("Patente aduanal", validators=[DataRequired(), Length(max=50)],
                                render_kw={"class": "form-control", "placeholder": "Patente aduanal"})

    # Tipo de carga
    tipo = SelectField("Tipo de carga", validators=[DataRequired()],
                      choices=[("full", "Full"), ("carrotanque", "Carrotanque"), ("barcaza", "Barcaza")],
                      render_kw={"class": "form-select"})

    # Volúmenes en litros
    litros_rem1 = FloatField("Litros Remolque 1", validators=[Optional(), NumberRange(min=0)],
                           render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})
    litros_rem2 = FloatField("Litros Remolque 2", validators=[Optional(), NumberRange(min=0)],
                           render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})
    litros_carrotanque = FloatField("Litros Carrotanque", validators=[Optional(), NumberRange(min=0)],
                                  render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})
    litros_barcaza = FloatField("Litros Barcaza", validators=[Optional(), NumberRange(min=0)],
                              render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})

    # Datos financieros
    precio_molecula_galon = FloatField("Precio por galón (USD)", validators=[DataRequired(), NumberRange(min=0)],
                                     render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.001"})

    densidad = FloatField("Densidad", validators=[Optional(), NumberRange(min=0)],
                         render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.001"})
    peso_bruto = FloatField("Peso bruto (kg)", validators=[Optional(), NumberRange(min=0)],
                          render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})
    tipo_cambio = FloatField("Tipo de cambio (MXN/USD)", validators=[Optional(), NumberRange(min=0)],
                           render_kw={"class": "form-control", "placeholder": "0.00", "step": "0.01"})

    submit = SubmitField("Generar factura", render_kw={"class": "btn btn-primary"})

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False

        # Validar que al menos un volumen sea mayor a 0
        volumen_total = (self.litros_rem1.data or 0) + (self.litros_rem2.data or 0) + \
                       (self.litros_carrotanque.data or 0) + (self.litros_barcaza.data or 0)

        if volumen_total <= 0:
            self.litros_rem1.errors.append("Debe ingresar al menos un volumen mayor a 0")
            return False

        return True


# =====================
# Configuración de tasas (solo admin)
# =====================
class TasasForm(FlaskForm):
    ieps = FloatField("IEPS por galón (MXN)", validators=[DataRequired(), NumberRange(min=0)],
                     render_kw={"class": "form-control", "placeholder": "4.59", "step": "0.01"})
    iva = FloatField("IVA (%)", validators=[DataRequired(), NumberRange(min=0, max=1)],
                    render_kw={"class": "form-control", "placeholder": "0.16", "step": "0.01"})
    pvr = FloatField("PVR por galón (MXN)", validators=[DataRequired(), NumberRange(min=0)],
                    render_kw={"class": "form-control", "placeholder": "0.20", "step": "0.01"})
    iva_pvr = FloatField("IVA sobre PVR (%)", validators=[DataRequired(), NumberRange(min=0, max=1)],
                        render_kw={"class": "form-control", "placeholder": "0.16", "step": "0.01"})
    factor_conversion = FloatField("Factor de conversión (L→Gal)", validators=[DataRequired(), NumberRange(min=0)],
                                 render_kw={"class": "form-control", "placeholder": "0.264172", "step": "0.000001"})
    submit = SubmitField("Guardar configuración", render_kw={"class": "btn btn-success"})


# =====================
# Gestión de usuarios (admin)
# =====================
class UserManagementForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=100)],
                        render_kw={"class": "form-control"})
    email = StringField("Email", validators=[DataRequired(), Email()],
                       render_kw={"class": "form-control"})
    rol = SelectField("Rol", validators=[DataRequired()],
                     choices=[("usuario", "Usuario"), ("supervisor", "Supervisor"), ("admin", "Administrador")],
                     render_kw={"class": "form-select"})
    creditos = IntegerField("Créditos", validators=[DataRequired(), NumberRange(min=0)],
                          render_kw={"class": "form-control"})
    activo = SelectField("Estado", validators=[DataRequired()],
                        choices=[(True, "Activo"), (False, "Inactivo")],
                        coerce=lambda x: x == 'True',
                        render_kw={"class": "form-select"})
    submit = SubmitField("Guardar", render_kw={"class": "btn btn-primary"})


# =====================
# Revisión de facturas
# =====================
class RevisionForm(FlaskForm):
    accion = HiddenField()
    comentario = TextAreaField("Comentarios", validators=[Optional()],
                             render_kw={"class": "form-control", "rows": "3",
                                       "placeholder": "Ingresa comentarios adicionales (opcional)"})

    # Botones de acción
    aprobar = SubmitField("Aprobar", render_kw={"class": "btn btn-success"})
    suspender = SubmitField("Suspender", render_kw={"class": "btn btn-warning"})
    rechazar = SubmitField("Rechazar", render_kw={"class": "btn btn-danger"})


# =====================
# Búsqueda y filtros
# =====================
class BusquedaFacturasForm(FlaskForm):
    search = StringField("Buscar", validators=[Optional()],
                        render_kw={"class": "form-control", "placeholder": "Buscar por importador, RFC, pedimento..."})
    estado = SelectField("Estado", validators=[Optional()],
                        choices=[("", "Todos los estados"),
                               ("borrador", "Borrador"),
                               ("pendiente_supervisor", "Pendiente de Revisión"),
                               ("pendiente_admin", "Pendiente de Aprobación"),
                               ("aprobada", "Aprobada"),
                               ("suspendida", "Suspendida"),
                               ("cancelada", "Cancelada")],
                        render_kw={"class": "form-select"})
    usuario = SelectField("Usuario", validators=[Optional()],
                         choices=[("", "Todos los usuarios")],  # Se popula dinámicamente en la vista
                         render_kw={"class": "form-select"})
    fecha_desde = StringField("Fecha Desde", validators=[Optional()],
                             render_kw={"class": "form-control", "type": "date"})
    fecha_hasta = StringField("Fecha Hasta", validators=[Optional()],
                             render_kw={"class": "form-control", "type": "date"})
    buscar = StringField("Buscar", validators=[Optional()],
                        render_kw={"class": "form-control", "placeholder": "Importador..."})
    monto_min = FloatField("Monto Mínimo", validators=[Optional(), NumberRange(min=0)],
                          render_kw={"class": "form-control", "step": "0.01"})
    submit = SubmitField("Buscar", render_kw={"class": "btn btn-outline-primary"})


# =====================
# Formularios adicionales
# =====================
class CrearFacturaForm(FlaskForm):
    """Formulario para crear facturas (versión simplificada)"""
    usuario_id = SelectField("Usuario", validators=[DataRequired()], coerce=int,
                            render_kw={"class": "form-select"})
    importador = StringField("Importador", validators=[DataRequired(), Length(max=200)],
                           render_kw={"class": "form-control", "placeholder": "Nombre del importador"})
    descripcion_producto = TextAreaField("Descripción del Producto", validators=[DataRequired()],
                                       render_kw={"class": "form-control", "rows": "3"})
    cantidad = FloatField("Cantidad", validators=[DataRequired(), NumberRange(min=0)],
                         render_kw={"class": "form-control", "step": "0.01"})
    unidad_medida = SelectField("Unidad de Medida", validators=[DataRequired()],
                              choices=[("kg", "Kilogramos"), ("t", "Toneladas"), ("l", "Litros"), ("pz", "Piezas")],
                              render_kw={"class": "form-select"})
    valor_fob = FloatField("Valor FOB (USD)", validators=[DataRequired(), NumberRange(min=0)],
                          render_kw={"class": "form-control", "step": "0.01"})
    flete = FloatField("Flete (USD)", validators=[DataRequired(), NumberRange(min=0)],
                      render_kw={"class": "form-control", "step": "0.01"})
    archivo_factura = FileField("Archivo de Factura",
                               validators=[Optional(), FileAllowed(['pdf'], 'Solo archivos PDF!')],
                               render_kw={"class": "form-control"})
    observaciones = TextAreaField("Observaciones", validators=[Optional()],
                                render_kw={"class": "form-control", "rows": "3"})
    submit = SubmitField("Crear Factura", render_kw={"class": "btn btn-primary"})


class AprobarFacturaForm(FlaskForm):
    """Formulario para aprobar/rechazar facturas"""
    decision = SelectField("Decisión", validators=[DataRequired()],
                          choices=[("", "Selecciona una decisión"),
                                 ("aprobar", "Aprobar"),
                                 ("rechazar", "Rechazar")],
                          render_kw={"class": "form-select"})
    comentarios = TextAreaField("Comentarios", validators=[Optional()],
                              render_kw={"class": "form-control", "rows": "4"})
    submit = SubmitField("Procesar", render_kw={"class": "btn btn-primary"})


class EditarUsuarioForm(FlaskForm):
    """Formulario para editar usuarios"""
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=100)],
                        render_kw={"class": "form-control"})
    email = StringField("Email", validators=[DataRequired(), Email()],
                       render_kw={"class": "form-control"})
    rol = SelectField("Rol", validators=[DataRequired()],
                     choices=[("usuario", "Usuario"), ("supervisor", "Supervisor"), ("admin", "Administrador")],
                     render_kw={"class": "form-select"})
    creditos = IntegerField("Créditos", validators=[Optional(), NumberRange(min=0)],
                          render_kw={"class": "form-control"})
    activo = SelectField("Estado", validators=[DataRequired()],
                        choices=[("True", "Activo"), ("False", "Inactivo")],
                        render_kw={"class": "form-select"})
    password = PasswordField("Nueva Contraseña", validators=[Optional(), Length(min=6)],
                            render_kw={"class": "form-control"})
    confirm_password = PasswordField("Confirmar Contraseña", validators=[Optional()],
                                   render_kw={"class": "form-control"})
    submit = SubmitField("Guardar Cambios", render_kw={"class": "btn btn-primary"})