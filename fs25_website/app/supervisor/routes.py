from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')

@bp.route('/dashboard')
@login_required
def supervisor_home():
    return render_template('supervisor/dashboard.html', user=current_user)
