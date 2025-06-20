from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

# Create extension instances here (global)
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'devkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fs25.db'

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Import blueprints here (to avoid circular imports)
    from app.main.routes import bp as main_bp
    from app.supervisor.routes import bp as supervisor_bp
    from app.admin.routes import bp as admin_bp
    from app.auth.routes import bp as auth_bp
    from app.dot.routes import bp as dot_bp
    from app.tickets.routes import bp as tickets_bp

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dot_bp)
    app.register_blueprint(tickets_bp)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/')
    def home():
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            elif current_user.role == 'supervisor':
                return redirect(url_for('supervisor.supervisor_home'))
            elif current_user.role == 'dot_officer':
                return redirect(url_for('dot.dot_home'))
            else:
                return redirect(url_for('main.player_home'))
        else:
            return redirect(url_for('auth.login'))

    return app
