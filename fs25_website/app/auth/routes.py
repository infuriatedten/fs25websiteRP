from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_dance.contrib.discord import discord
from app.models import User
from app import db
from datetime import datetime
# import uuid # Not strictly needed if password can be null for Discord users
from .forms import LoginForm, RegistrationForm # Import WTForms

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.player_home'))

    form = LoginForm()
    if form.validate_on_submit():
        username_or_email = form.username_or_email.data
        password = form.password.data
        remember = form.remember_me.data

        user_by_username = User.query.filter_by(username=username_or_email).first()
        user_by_email = User.query.filter(User.email.ilike(username_or_email)).first() # Case-insensitive email
        user = user_by_username or user_by_email

        if user and user.password and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            user.login_time = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get('next')
            # Use is_safe_url to ensure the redirect is safe
            if not next_page or not is_safe_url(next_page):
                # Default redirect based on role if 'next' is unsafe or not provided
                if user.role == 'admin': next_page = url_for('admin.admin_dashboard')
                elif user.role == 'supervisor': next_page = url_for('supervisor.supervisor_home')
                elif user.role == 'dot_officer': next_page = url_for('dot.dot_home') # This redirects to supervisor_panel or my_vehicles
                else: next_page = url_for('main.player_home')
            return redirect(next_page)
        else:
            flash("Invalid credentials or password not set (try Discord login?).", "error")
            # When form validation fails, or login fails, re-render the login template with the form
            # WTForms will automatically populate errors if form.validate_on_submit() returned False
            # If it's a custom flash like here, it will also be shown.
    return render_template('auth/login.html', title="Login", form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.player_home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data,
            email=form.email.data.lower(), # Store email as lowercase
            password=hashed_pw
            # Role defaults to 'player' in model
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    # If form validation fails, WTForms will pass errors to the template
    return render_template('auth/register.html', title="Register", form=form)

@bp.route('/logout')
@login_required
def logout():
    if hasattr(current_user, 'login_time') and hasattr(current_user, 'logout_time') and hasattr(current_user, 'total_logged_hours'):
        current_user.logout_time = datetime.utcnow()
        if current_user.login_time:
            delta = current_user.logout_time - current_user.login_time
            hours = delta.total_seconds() / 3600.0
            current_user.total_logged_hours = (current_user.total_logged_hours or 0.0) + hours
        current_user.login_time = None
        db.session.commit()
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route("/discord/callback")
def discord_callback():
    if not discord.authorized:
        flash("Discord authorization failed or was denied.", "error")
        return redirect(url_for("auth.login"))

    try:
        resp = discord.get("/api/users/@me")
        resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        discord_user_data = resp.json()
    except Exception as e:
        flash(f"Failed to fetch user data from Discord: {str(e)}", "error")
        # Log the actual error: current_app.logger.error(f"Discord API error: {e}")
        return redirect(url_for("auth.login"))

    discord_id = discord_user_data.get("id")
    discord_email = discord_user_data.get("email") # This might be None if not verified or scope insufficient
    discord_username = discord_user_data.get("username")

    if not discord_id:
        flash("Could not retrieve user ID from Discord.", "error")
        return redirect(url_for("auth.login"))

    if not discord_email: # Handle cases where email is not provided by Discord
        flash("Discord did not provide an email address. Please register using email or ensure your Discord email is verified and shared.", "warning")
        # Potentially redirect to a page where they can manually enter an email to link,
        # or allow username-only accounts if your system supports it (current User model requires email).
        return redirect(url_for("auth.register")) # Or auth.login

    user = User.query.filter_by(discord_user_id=discord_id).first()
    if not user: # No user with this discord_id, try email
        user = User.query.filter(User.email.ilike(discord_email)).first()
        if user: # Found by email, link account
            user.discord_user_id = discord_id
            # User might not have a password if they previously only used local login with a different provider
            # or if admin created. This is fine.
        else: # No user by discord_id or email, create new user
            local_username = discord_username
            counter = 1
            while User.query.filter_by(username=local_username).first():
                local_username = f"{discord_username}_{counter}"
                counter += 1

            user = User(
                username=local_username,
                email=discord_email.lower(),
                discord_user_id=discord_id,
                # Password can be None as User.password is nullable
            )
            db.session.add(user)

    try: # Commit any changes (new user or linking discord_id)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Database error during Discord login/registration: {str(e)}", "danger")
        # current_app.logger.error(f"DB error in discord_callback: {e}")
        return redirect(url_for("auth.login"))

    login_user(user) # Log in the found or new user
    user.login_time = datetime.utcnow() # Update login time
    db.session.commit() # Commit login time update

    flash("Logged in successfully via Discord!", "success")
    return redirect(url_for("main.player_home"))

from urllib.parse import urlparse, urljoin # Moved to top-level imports

# Helper for 'next' query param security
def is_safe_url(target):
    # request needs to be imported from flask for this helper if it's at module level
    # or accessed via current_app.request if used inside a request context without direct import
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc
