from flask import Flask, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user # Added logout_user
from flask_migrate import Migrate
from flask_dance.contrib.discord import make_discord_blueprint
import os
import logging
from datetime import datetime, timedelta # Added timedelta

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'devkey_super_secret_for_inactivity_logout')

    # Database Configuration (MySQL with SQLite fallback)
    mysql_user = os.environ.get('MYSQL_USER')
    mysql_password = os.environ.get('MYSQL_PASSWORD')
    mysql_host = os.environ.get('MYSQL_HOST')
    mysql_db_name = os.environ.get('MYSQL_DB_NAME')
    cloud_sql_connection_name = os.environ.get('CLOUD_SQL_CONNECTION_NAME')

    if cloud_sql_connection_name and mysql_user and mysql_password and mysql_db_name:
        # Google Cloud SQL with Cloud SQL Proxy
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"mysql+pymysql://{mysql_user}:{mysql_password}@/{mysql_db_name}"
            f"?unix_socket=/cloudsql/{cloud_sql_connection_name}"
        )
    elif mysql_user and mysql_password and mysql_host and mysql_db_name:
        # Standard MySQL server
        app.config['SQLALCHEMY_DATABASE_URI'] = \
            f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_db_name}"
    else:
        # Fallback to SQLite for local development
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fs25.db')
        app.logger.info("MySQL environment variables not fully set, falling back to SQLite.")

    # Inactivity Timeout Configuration (3 hours)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
    app.config['USER_INACTIVITY_TIMEOUT_SECONDS'] = 3 * 60 * 60 # 3 hours in seconds

    # Discord OAuth Configuration
    app.config['DISCORD_OAUTH_CLIENT_ID'] = os.environ.get('DISCORD_OAUTH_CLIENT_ID', '1388703541438185604')
    app.config['DISCORD_OAUTH_CLIENT_SECRET'] = os.environ.get('DISCORD_OAUTH_CLIENT_SECRET', 'mWakBFUT_zMH7nzTgozVmDW_8LmYuPY6')

    # Discord Webhook URLs
    app.config['DISCORD_WEBHOOK_URL_SALES'] = os.environ.get('DISCORD_WEBHOOK_URL_SALES', 'https://discord.com/api/webhooks/1388710143289593967/nrq_UJVcp-Oc6qm63UjntdNm2EThlqzjmb6UthKDiGBp47PSJlYfRodJK7uTBFBCol5i')
    app.config['DISCORD_WEBHOOK_URL_PRODUCT_UPDATES'] = os.environ.get('DISCORD_WEBHOOK_URL_PRODUCT_UPDATES', 'https://discord.com/api/webhooks/1388710156275023903/22kqpaQpXC1YqccksvUxg_xJmN-uJaXUz5sXe2VTcwBVH3qhn-u2bbylYcEs5bQW6X30')

    if not app.debug and not app.testing:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    migrate.init_app(app, db)

    from .main.routes import bp as main_bp
    from .supervisor.routes import bp as supervisor_bp
    from .admin.routes import bp as admin_bp
    from .auth.routes import bp as auth_bp
    from .dot.routes import bp as dot_bp
    from .tickets.routes import bp as tickets_bp
    from .products import bp as products_bp
    from .orders import bp as orders_bp

    discord_bp = make_discord_blueprint(
        client_id=app.config['DISCORD_OAUTH_CLIENT_ID'],
        client_secret=app.config['DISCORD_OAUTH_CLIENT_SECRET'],
        scope=["identify", "email"],
        redirect_to="auth.discord_callback",
    )

    app.register_blueprint(main_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dot_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(orders_bp, url_prefix='/order')
    app.register_blueprint(discord_bp, url_prefix="/login")

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def before_request_check_inactivity():
        if current_user.is_authenticated:
            # Make the session permanent so PERMANENT_SESSION_LIFETIME is used
            session.permanent = True

            last_activity_str = session.get('_last_activity_ts')
            # Use app.config here as current_app might not be reliably available in before_request during setup/teardown for tests
            inactivity_timeout = app.config.get('USER_INACTIVITY_TIMEOUT_SECONDS', 3 * 60 * 60)

            if last_activity_str:
                last_activity_dt = datetime.fromisoformat(last_activity_str)
                elapsed_seconds = (datetime.utcnow() - last_activity_dt).total_seconds()
                if elapsed_seconds > inactivity_timeout:
                    logout_user()
                    flash("You have been logged out due to inactivity.", "info")
                    return redirect(url_for('auth.login'))

            # Update last activity timestamp for this request
            session['_last_activity_ts'] = datetime.utcnow().isoformat()
            session.modified = True # Ensure session is saved if only _last_activity_ts changed


    @app.route('/')
    def home():
        if current_user.is_authenticated:
            # ... (role-based redirects) ...
            if current_user.role == 'admin': return redirect(url_for('admin.admin_dashboard'))
            elif current_user.role == 'supervisor': return redirect(url_for('supervisor.supervisor_home'))
            elif current_user.role == 'dot_officer': return redirect(url_for('dot.dot_home'))
            else: return redirect(url_for('main.player_home'))
        else:
            return redirect(url_for('auth.login'))

    return app
