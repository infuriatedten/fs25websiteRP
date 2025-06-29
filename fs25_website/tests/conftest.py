import pytest
from app import create_app, db as _db
from app.models import User
from werkzeug.security import generate_password_hash

@pytest.fixture(scope='function')
def app():
    app_obj = create_app()
    app_obj.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": False,
        "SERVER_NAME": "localhost.localdomain",
        "SECRET_KEY": "test-secret-key",
        "DISCORD_OAUTH_CLIENT_ID": "test_client_id_for_pytest",
        "DISCORD_OAUTH_CLIENT_SECRET": "test_client_secret_for_pytest",
        "DEBUG_TB_ENABLED": False,
        "SQLALCHEMY_ECHO": False
    })

    with app_obj.app_context():
        _db.drop_all()
        _db.create_all()

    yield app_obj

    with app_obj.app_context():
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    return app.test_cli_runner()

@pytest.fixture(scope='function')
def db_session(app):
    with app.app_context():
        for tbl in reversed(_db.metadata.sorted_tables):
            _db.session.execute(tbl.delete())
        _db.session.commit()

        yield _db.session

        _db.session.remove()

@pytest.fixture
def new_user_factory(app, db_session):
    def _create_user(username="testuser", email="test@example.com", password="password", role="player", balance=100.0, discord_id=None):
        with app.app_context():
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password) if password else None,
                role=role,
                balance=balance,
                discord_user_id=discord_id
            )
            db_session.add(user)
            db_session.commit()
            # IMPORTANT: Return the ID, not the instance, to avoid detached instance issues.
            return user.id
    return _create_user

@pytest.fixture
def logged_in_user(client, new_user_factory, app, db_session):
    user_id_val = None
    user_for_test = None

    with app.app_context():
        # new_user_factory now returns the ID
        user_id_val = new_user_factory(username="autologinuser", email="autologin@example.com", password="password")
        # Fetch the user instance within the same context using the ID
        user_for_test = db_session.query(User).get(user_id_val)

    # Set the client session using the obtained ID
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id_val)
        sess['_fresh'] = True

    assert user_for_test is not None, "User could not be fetched in logged_in_user fixture"
    return user_for_test, client


@pytest.fixture
def login_user_directly_helper(app):
    from flask_login import login_user as flask_login_user_actual
    def _login(user_obj, remember=False):
        with app.test_request_context():
            flask_login_user_actual(user_obj, remember=remember)
    return _login
