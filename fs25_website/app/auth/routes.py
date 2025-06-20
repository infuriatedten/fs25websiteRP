from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from app.models import User
from app import db
from datetime import datetime

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            # Record login time
            user.login_time = datetime.utcnow()
            db.session.commit()

            # Redirect by role
            if user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            elif user.role == 'supervisor':
                return redirect(url_for('supervisor.supervisor_home'))
            elif user.role == 'dot_officer':
                return redirect(url_for('dot.dot_home'))
            else:
                return redirect(url_for('main.player_home'))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Basic check if username already exists
        if User.query.filter_by(username=username).first():
            flash("Username already taken", "error")
            return redirect(url_for('auth.register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Registered successfully! Please log in.')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@bp.route('/logout')
@login_required
def logout():
    # Record logout time and update total logged hours
    current_user.logout_time = datetime.utcnow()
    if current_user.login_time:
        delta = current_user.logout_time - current_user.login_time
        hours = delta.total_seconds() / 3600.0
        current_user.total_logged_hours += hours
    current_user.login_time = None
    db.session.commit()

    logout_user()
    return redirect(url_for('auth.login'))
