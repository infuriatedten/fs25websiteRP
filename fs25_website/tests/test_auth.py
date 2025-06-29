from flask import url_for
from app.models import User # Corrected import

def test_register_page_loads(client, app):
    with app.app_context():
        response = client.get(url_for('auth.register'))
    assert response.status_code == 200
    assert b"Register New Account" in response.data
    assert b"Register with Email" in response.data
    assert b"Sign up with Discord" in response.data

def test_login_page_loads(client, app):
    with app.app_context():
        response = client.get(url_for('auth.login'))
    assert response.status_code == 200
    assert b"Login to Your Account" in response.data
    assert b"Login with Discord" in response.data

def test_successful_registration_and_login(client, app, db_session): # db_session for querying
    with app.app_context():
        register_response = client.post(url_for('auth.register'), data={
            'username': 'testuser_reg',
            'email': 'test_reg@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert register_response.status_code == 200
        assert b"Registered successfully! Please log in." in register_response.data

        user = User.query.filter_by(email='test_reg@example.com').first()
        assert user is not None
        assert user.username == 'testuser_reg'
        assert user.password is not None

        login_response = client.post(url_for('auth.login'), data={
            'username_or_email': 'testuser_reg',
            'password': 'password123'
        }, follow_redirects=True)
        assert login_response.status_code == 200
        assert b"Logout" in login_response.data
        assert b"Balance:" in login_response.data

def test_registration_duplicate_username(client, new_user_factory, app):
    new_user_factory(username="existinguser", email="unique_email@example.com", password="pw")
    with app.app_context():
        response = client.post(url_for('auth.register'), data={
            'username': 'existinguser',
            'email': 'another_email@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Username already taken." in response.data

def test_registration_duplicate_email(client, new_user_factory, app):
    new_user_factory(username="anotheruser", email="existing_email@example.com", password="pw")
    with app.app_context():
        response = client.post(url_for('auth.register'), data={
            'username': 'newuniqueuser',
            'email': 'existing_email@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Email address already registered." in response.data

def test_login_nonexistent_user(client, app):
    with app.app_context():
        response = client.post(url_for('auth.login'), data={
            'username_or_email': 'nouser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid credentials" in response.data

def test_login_wrong_password(client, new_user_factory, app):
    new_user_factory(username="loginuser2", email="login2@example.com", password="correctpassword")
    with app.app_context():
        response = client.post(url_for('auth.login'), data={
            'username_or_email': 'loginuser2',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid credentials" in response.data

def test_logout(client, logged_in_user, app):
    _user, _client = logged_in_user
    with app.app_context():
        response = _client.get(url_for('auth.logout'), follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been successfully logged out." in response.data
    assert b"Login to Your Account" in response.data

def test_login_with_email(client, new_user_factory, app):
    new_user_factory(username="email_login_user", email="email_login@example.com", password="password123")
    with app.app_context():
        response = client.post(url_for('auth.login'), data={
            'username_or_email': 'email_login@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Logout" in response.data
        assert b"Balance:" in response.data

# Further tests to add:
# - Registration missing fields (e.g. no email, no password for local reg)
# - Login for Discord-only user (no password) - should fail local password login
# - Mocked Discord login flow (new user, link existing by email, existing Discord user)
# - Access control for @login_required routes
# - Password hashing check (if User model had set_password/check_password methods)
# - Email validation edge cases if using more complex validation than basic string checks.
