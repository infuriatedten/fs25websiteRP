from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Transaction # Corrected import
from sqlalchemy import desc # For ordering transactions

bp = Blueprint('main', __name__, template_folder='templates')

@bp.route('/')
@login_required
def player_home():
    # This could be a dashboard or the main player home page
    # Assuming 'main/player_home.html' exists or will be created.
    # For now, it might be the same as index.html or a specific dashboard.
    return render_template('main/player_home.html', user=current_user, title="Player Dashboard")

@bp.route('/bank')
@login_required
def bank_transactions():
    # Query transactions for the current user, ordered by most recent
    user_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(desc(Transaction.timestamp)).all()
    return render_template('main/bank_transactions.html',
                           transactions=user_transactions,
                           user=current_user,  # Passing the whole user object for balance, etc.
                           title="My Bank & Transaction History")
