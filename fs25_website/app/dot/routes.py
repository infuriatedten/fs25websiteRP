from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Ticket, Permit, Vehicle, Inspection, User
from app.models import Order
from app import db

bp = Blueprint('dot', __name__, url_prefix='/dot')

@bp.route('/')
@login_required
def dot_home():
    user_tickets = Ticket.query.filter_by(issued_to=current_user.id).all()
    user_permits = Permit.query.filter_by(owner_id=current_user.id).all()
    return render_template('dot_home.html', tickets=user_tickets, permits=user_permits)

@bp.route('/supervisor', methods=['GET', 'POST'])
@login_required
def supervisor_panel():
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))  # or some other fallback page

    query = Ticket.query
    search_user = request.args.get("user_id")
    search_status = request.args.get("status")
    search_term = request.args.get("search")

    if search_user:
        query = query.filter_by(issued_to=search_user)
    if search_status:
        query = query.filter_by(paid=(search_status == "paid"))
    if search_term:
        query = query.filter(Ticket.reason.ilike(f"%{search_term}%"))

    tickets = query.all()
    permits = Permit.query.filter_by(status='pending').all()
    vehicles = Vehicle.query.all()
    return render_template("dot/supervisor_panel.html", tickets=tickets, permits=permits, vehicles=vehicles)


@bp.route("/issue_ticket", methods=["POST"])
@login_required
def issue_ticket():
    if current_user.role not in ['supervisor', 'admin']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    t = Ticket(reason=request.form['reason'], fine_amount=int(request.form['fine_amount']), issued_to=int(request.form['user_id']))
    db.session.add(t)
    db.session.commit()
    flash("Ticket issued.")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route("/permit/<int:permit_id>/approve")
@login_required
def approve_permit(permit_id):
    if current_user.role not in ['supervisor', 'admin']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    permit = Permit.query.get_or_404(permit_id)
    permit.status = "approved"
    db.session.commit()
    flash("Permit approved.")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route("/permit/<int:permit_id>/reject")
@login_required
def reject_permit(permit_id):
    if current_user.role not in ['supervisor', 'admin']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    permit = Permit.query.get_or_404(permit_id)
    permit.status = "rejected"
    db.session.commit()
    flash("Permit rejected.")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route("/log_inspection", methods=["POST"])
@login_required
def log_inspection():
    if current_user.role not in ['supervisor', 'admin']:
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    insp = Inspection(vehicle_id=int(request.form['vehicle_id']), passed=(request.form['passed'] == '1'), notes=request.form['notes'])
    db.session.add(insp)
    db.session.commit()
    flash("Inspection logged.")
    return redirect(url_for("dot.supervisor_panel"))
@bp.route('/ticket/<int:ticket_id>/orders', methods=['GET', 'POST'])
@login_required
def ticket_orders(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # Authorization: only admin, supervisor or ticket owner can view
    if not (current_user.role in ['admin', 'supervisor'] or ticket.issued_to == current_user.id):
        flash("Access denied.")
        return redirect(url_for('dot.dot_home'))

    if request.method == 'POST':
        item_name = request.form['item_name']
        quantity = int(request.form['quantity'])
        price_per_unit = float(request.form['price_per_unit'])
        order = Order(ticket_id=ticket.id, item_name=item_name, quantity=quantity, price_per_unit=price_per_unit)
        db.session.add(order)
        db.session.commit()
        flash("Order added.")
        return redirect(url_for('dot.ticket_orders', ticket_id=ticket.id))

    orders = Order.query.filter_by(ticket_id=ticket.id).all()
    return render_template('ticket_orders.html', ticket=ticket, orders=orders)