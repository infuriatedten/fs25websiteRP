from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Company
from app import db

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/')
@login_required
def admin_panel():
    if current_user.role not in ['admin', 'supervisor']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))  # Or some other safe page
    users = User.query.all()
    return render_template('admin/admin.html', users=users)

@bp.route('/dashboard')
@login_required
def admin_dashboard():
    if current_user.role not in ['admin', 'supervisor']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))
    return render_template('admin/dashboard.html', user=current_user)

@bp.route('/promote', methods=['POST'])
@login_required
def promote_user():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    user_id = int(request.form['user_id'])
    new_role = request.form['role']
    user = User.query.get_or_404(user_id)
    user.role = new_role
    db.session.commit()
    flash(f"{user.username} promoted to {new_role}.")
    return redirect(url_for('admin.admin_panel'))

@bp.route('/companies', methods=['GET', 'POST'])
@login_required
def companies():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        
        # Check if a company with the same name already exists
        existing_company = Company.query.filter_by(name=name).first()
        if existing_company:
            flash('Company with this name already exists.')
            return redirect(url_for('admin.companies'))

        # Create and add new company
        new_company = Company(name=name, description=description)
        db.session.add(new_company)
        db.session.commit()

        flash('Company created successfully!')
        return redirect(url_for('admin.companies'))

    companies = Company.query.all()
    return render_template('admin/companies.html', companies=companies)
