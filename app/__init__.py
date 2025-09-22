import os
from flask import Flask, render_template
from .extensions import db, migrate, login_manager
from .models import User

def create_app(config_name='default'):
    app = Flask(__name__)

    # Load configuration
    if config_name == 'default':
        config_name = os.getenv('FLASK_ENV', 'development')

    from config import config
    app.config.from_object(config[config_name])

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .routes.auth import bp as auth_bp
    from .routes.usuarios import bp as usuarios_bp
    from .routes.supervisores import bp as supervisores_bp
    from .routes.admins import bp as admins_bp
    from .routes.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(supervisores_bp)
    app.register_blueprint(admins_bp)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    return app