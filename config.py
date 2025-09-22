import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///facturas.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'facturas')

    # Pagination settings
    INVOICES_PER_PAGE = 10

    # Default tax rates (will be overridden by database configuration)
    DEFAULT_IEPS = 4.59
    DEFAULT_IVA = 0.16
    DEFAULT_PVR = 0.20
    DEFAULT_IVA_PVR = 0.16

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

    # Override for production paths
    UPLOAD_FOLDER = '/home/edudracos/traza-1.0/app/static/facturas'

    @property
    def SECRET_KEY(self):
        secret = os.getenv("SECRET_KEY")
        if not secret:
            raise ValueError("No SECRET_KEY set for production!")
        return secret

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        # Use MySQL for production if available, fallback to SQLite
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # Default SQLite path for PythonAnywhere
            db_url = "sqlite:////home/edudracos/traza-1.0/instance/facturas.db"
        return db_url

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}