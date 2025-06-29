from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Ticket, Permit, Vehicle, Inspection, User, Order, Transaction
from app import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from .forms import VehicleForm, IssueTicketForm, LogInspectionForm, TicketItemForm # Import DOT forms

# Constants for Ticket statuses
TICKET_STATUS_UNPAID = "unpaid"
TICKET_STATUS_PAID = "paid"
TICKET_STATUS_DISPUTED = "disputed"
TICKET_STATUS_WARNING = "warning_issued"
TICKET_STATUS_COMPLIANCE_PENDING = "compliance_pending"
TICKET_STATUS_RESOLVED = "resolved"

DISPUTE_STATUS_NONE = "none"
DISPUTE_STATUS_PENDING = "pending_review"
DISPUTE_STATUS_APPROVED = "review_approved"
DISPUTE_STATUS_REJECTED = "review_rejected"

bp = Blueprint('dot', __name__, url_prefix='/dot') # Templates expected in app/templates/dot/

@bp.route('/')
@login_required
def dot_home():
    if current_user.role in ['dot_officer', 'supervisor', 'admin']:
        return redirect(url_for('dot.supervisor_panel'))
    else:
        return redirect(url_for('dot.my_vehicles'))

# --- DOT Officer/Supervisor Routes ---
@bp.route('/supervisor_panel', methods=['GET'])
@login_required
def supervisor_panel():
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.", "danger")
        return redirect(url_for('main.player_home'))

    tickets_query = Ticket.query
    search_user_id = request.args.get("user_id")
    search_ticket_status = request.args.get("ticket_status")
    search_reason = request.args.get("reason")

    if search_user_id and search_user_id.isdigit():
        tickets_query = tickets_query.filter(Ticket.issued_to == int(search_user_id))
    if search_ticket_status:
        tickets_query = tickets_query.filter(Ticket.status == search_ticket_status)
    if search_reason:
        tickets_query = tickets_query.filter(Ticket.reason.ilike(f"%{search_reason}%"))
    all_tickets = tickets_query.order_by(Ticket.created_at.desc()).all()

    pending_permits = Permit.query.filter_by(status='pending').order_by(Permit.id.desc()).all()
    all_vehicles = Vehicle.query.order_by(Vehicle.plate).all()
    disputed_tickets = Ticket.query.filter(
        Ticket.status == TICKET_STATUS_DISPUTED,
        Ticket.dispute_status == DISPUTE_STATUS_PENDING
    ).order_by(Ticket.updated_at.asc()).all()

    # Forms for supervisor actions
    issue_ticket_form = IssueTicketForm()
    log_inspection_form = LogInspectionForm()

    return render_template("dot/supervisor_panel.html",
                           tickets=all_tickets,
                           pending_permits=pending_permits,
                           all_vehicles=all_vehicles,
                           disputed_tickets=disputed_tickets,
                           issue_ticket_form=issue_ticket_form,
                           log_inspection_form=log_inspection_form,
                           title="DOT Supervisor Panel")

@bp.route("/ticket/issue", methods=["POST"]) # Should be GET and POST if using WTForms for display
@login_required
def issue_ticket(): # Integrated with IssueTicketForm
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.", "danger"); return redirect(url_for('dot.dot_home'))

    form = IssueTicketForm() # Process this form
    if form.validate_on_submit():
        try:
            ticket_status = TICKET_STATUS_WARNING if form.fine_amount.data == 0 else TICKET_STATUS_UNPAID
            new_ticket = Ticket(
                reason=form.reason.data, notes=form.notes.data, fine_amount=form.fine_amount.data,
                status=ticket_status, issued_to=form.user_id.data,
                issuer_id=current_user.id, vehicle_id=form.vehicle_id.data
            )
            db.session.add(new_ticket); db.session.commit()
            flash("Ticket issued successfully.", "success")
        except Exception as e:
            db.session.rollback(); flash(f"Error issuing ticket: {str(e)}", "danger")
    else: # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")
    return redirect(url_for("dot.supervisor_panel"))


@bp.route("/permit/<int:permit_id>/approve", methods=['POST'])
@login_required
def approve_permit(permit_id):
    # ... (existing logic, ensure role check) ...
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.", "danger"); return redirect(url_for('dot.dot_home'))
    permit = Permit.query.get_or_404(permit_id)
    permit.status = "approved"; permit.issue_date = datetime.utcnow()
    db.session.commit(); flash(f"Permit ID {permit.id} approved.", "success")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route("/permit/<int:permit_id>/reject", methods=['POST'])
@login_required
def reject_permit(permit_id):
    # ... (existing logic, ensure role check) ...
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.", "danger"); return redirect(url_for('dot.dot_home'))
    permit = Permit.query.get_or_404(permit_id)
    permit.status = "rejected"; db.session.commit()
    flash(f"Permit ID {permit.id} rejected.", "warning")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route("/inspection/log", methods=["POST"]) # Should be GET and POST if using WTForms for display
@login_required
def log_inspection(): # Integrated with LogInspectionForm
    if current_user.role not in ['dot_officer', 'supervisor', 'admin']:
        flash("Access denied.", "danger"); return redirect(url_for('dot.dot_home'))

    form = LogInspectionForm() # Process this form
    if form.validate_on_submit():
        try:
            new_inspection = Inspection(
                vehicle_id=form.vehicle_id.data, passed=form.passed.data,
                notes=form.notes.data, inspector_id=current_user.id
            )
            db.session.add(new_inspection); db.session.commit()
            vehicle = Vehicle.query.get(form.vehicle_id.data) # For flash message
            flash(f"Inspection for vehicle {vehicle.plate if vehicle else 'Unknown'} logged.", "success")
        except Exception as e:
            db.session.rollback(); flash(f"Error logging inspection: {str(e)}", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")
    return redirect(url_for("dot.supervisor_panel"))

@bp.route('/ticket/<int:ticket_id>/items', methods=['GET', 'POST'])
@login_required
def ticket_items(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # ... (authorization) ...
    if not (current_user.role in ['admin', 'supervisor', 'dot_officer'] or ticket.issued_to == current_user.id):
        flash("Access denied.","danger"); return redirect(url_for('dot.dot_home'))

    form = TicketItemForm()
    if form.validate_on_submit(): # Changed from request.method == 'POST'
        try:
            ticket_item_order = Order(
                ticket_id=ticket.id, item_name=form.item_name.data,
                quantity=form.quantity.data, price_per_unit=form.price_per_unit.data
            )
            db.session.add(ticket_item_order); db.session.commit()
            flash("Item added to ticket.", "success")
        except Exception as e:
            db.session.rollback(); flash(f"Error adding item: {str(e)}", "danger")
        return redirect(url_for('dot.ticket_items', ticket_id=ticket.id)) # Redirect after POST

    ticket_item_orders = Order.query.filter_by(ticket_id=ticket.id).all()
    return render_template('dot/ticket_items.html', ticket=ticket, items=ticket_item_orders, form=form, title=f"Items for Ticket #{ticket.id}")

# --- User Vehicle Management Routes ---
@bp.route('/vehicles/mine')
@login_required
def my_vehicles():
    vehicles = Vehicle.query.filter_by(owner_id=current_user.id).order_by(Vehicle.plate).all()
    return render_template('dot/my_vehicles.html', vehicles=vehicles, title="My Registered Vehicles")

@bp.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    form = VehicleForm()
    if form.validate_on_submit():
        try:
            new_vehicle = Vehicle(
                plate=form.plate.data, make=form.make.data, model=form.model.data,
                year=form.year.data, color=form.color.data, owner_id=current_user.id
            )
            db.session.add(new_vehicle); db.session.commit()
            flash(f'Vehicle {form.plate.data} added successfully!', 'success')
            return redirect(url_for('dot.my_vehicles'))
        except IntegrityError: # Already handled by form validator, but as a fallback
            db.session.rollback(); flash(f'Error: Plate {form.plate.data} may already exist.', 'danger')
        except Exception as e:
            db.session.rollback(); flash(f'An unexpected error occurred: {str(e)}', 'danger')
    return render_template('dot/add_edit_vehicle.html', title="Add New Vehicle", form=form)

@bp.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if not (vehicle.owner_id == current_user.id or current_user.role in ['admin', 'supervisor', 'dot_officer']):
        flash('Not authorized to edit this vehicle.', 'danger'); return redirect(url_for('dot.my_vehicles'))

    form = VehicleForm(obj=vehicle, original_plate=vehicle.plate) # Pass original_plate for validation
    if form.validate_on_submit():
        try:
            vehicle.plate = form.plate.data; vehicle.make = form.make.data; vehicle.model = form.model.data
            vehicle.year = form.year.data; vehicle.color = form.color.data
            db.session.commit()
            flash(f'Vehicle {form.plate.data} updated!', 'success')
            return redirect(url_for('dot.my_vehicles'))
        except IntegrityError:
            db.session.rollback(); flash(f'Error: Plate {form.plate.data} may already exist for another vehicle.', 'danger')
        except Exception as e:
            db.session.rollback(); flash(f'An unexpected error occurred: {str(e)}', 'danger')
    return render_template('dot/add_edit_vehicle.html', title=f"Edit Vehicle {vehicle.plate}", form=form, vehicle=vehicle)

@bp.route('/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@login_required
def delete_vehicle(vehicle_id):
    # ... (existing logic, ensure role check and flash message consistency) ...
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if not (vehicle.owner_id == current_user.id or current_user.role in ['admin', 'supervisor', 'dot_officer']):
        flash('Not authorized to delete this vehicle.', 'danger'); return redirect(url_for('dot.my_vehicles'))
    try:
        plate_to_report = vehicle.plate; db.session.delete(vehicle); db.session.commit()
        flash(f'Vehicle {plate_to_report} deleted successfully.', 'success')
    except Exception as e: db.session.rollback(); flash(f'Error deleting vehicle: {str(e)}', 'danger')
    return redirect(url_for('dot.my_vehicles'))

# --- User DOT Ticket Management Routes ---
@bp.route('/tickets/my_tickets')
@login_required
def my_dot_tickets():
    # ... (existing logic) ...
    user_vehicle_ids = [v.id for v in current_user.vehicles]
    tickets_q1 = Ticket.query.filter_by(issued_to=current_user.id)
    tickets_q2 = Ticket.query.filter(Ticket.vehicle_id.in_(user_vehicle_ids), Ticket.issued_to != current_user.id) # Avoid double listing
    combined_tickets = list(set(tickets_q1.all() + tickets_q2.all()))
    combined_tickets.sort(key=lambda t: t.created_at, reverse=True)
    return render_template('dot/my_dot_tickets.html', tickets=combined_tickets, title="My DOT Tickets")

@bp.route('/ticket/<int:ticket_id>/view', methods=['GET', 'POST'])
@login_required
def view_dot_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # ... (authorization) ...
    user_is_recipient = (ticket.issued_to == current_user.id)
    user_owns_vehicle = (ticket.linked_vehicle and ticket.linked_vehicle.owner_id == current_user.id)
    if not (user_is_recipient or user_owns_vehicle or current_user.role in ['admin', 'supervisor', 'dot_officer']):
        flash("Not authorized to view this ticket.", "danger"); return redirect(url_for('dot.my_dot_tickets'))

    form = TicketDisputeForm() # For submitting dispute
    if form.validate_on_submit() and 'submit_dispute' in request.form : # Check which form was submitted
        if ticket.status == TICKET_STATUS_UNPAID or ticket.status == TICKET_STATUS_DISPUTED:
            ticket.dispute_reason = form.dispute_reason.data
            ticket.status = TICKET_STATUS_DISPUTED
            ticket.dispute_status = DISPUTE_STATUS_PENDING; ticket.updated_at = datetime.utcnow()
            db.session.commit(); flash("Dispute submitted for review.", "success")
            return redirect(url_for('dot.view_dot_ticket', ticket_id=ticket.id))
        else: flash("Ticket cannot be disputed now.", "warning")

    return render_template('dot/view_dot_ticket.html', ticket=ticket, form=form, title=f"View DOT Ticket #{ticket.id}",
                           TICKET_STATUS_UNPAID=TICKET_STATUS_UNPAID, TICKET_STATUS_DISPUTED=TICKET_STATUS_DISPUTED)


@bp.route('/ticket/<int:ticket_id>/pay', methods=['POST'])
@login_required
def pay_dot_ticket(ticket_id):
    # ... (existing logic, ensure flash messages are consistent) ...
    ticket = Ticket.query.get_or_404(ticket_id)
    is_responsible = (ticket.issued_to == current_user.id) or \
                     (ticket.linked_vehicle and ticket.linked_vehicle.owner_id == current_user.id)
    if not is_responsible:
        flash("Ticket not issued to you/your vehicle.", "danger"); return redirect(url_for('dot.my_dot_tickets'))
    if ticket.status != TICKET_STATUS_UNPAID:
        flash(f"Ticket cannot be paid (Status: {ticket.status}).", "warning"); return redirect(url_for('dot.view_dot_ticket', ticket_id=ticket.id))
    fine = ticket.fine_amount
    if fine <= 0: # Should be TICKET_STATUS_WARNING if fine is 0 initially
        flash("No outstanding fine or is a warning.", "info");
        if ticket.status != TICKET_STATUS_WARNING: ticket.status = TICKET_STATUS_RESOLVED
        ticket.updated_at = datetime.utcnow(); db.session.commit()
        return redirect(url_for('dot.view_dot_ticket', ticket_id=ticket.id))
    if current_user.balance < fine:
        flash(f"Insufficient funds. Need ${fine:.2f}, have ${current_user.balance:.2f}.", "danger"); return redirect(url_for('dot.view_dot_ticket', ticket_id=ticket.id))
    try:
        current_user.balance -= fine; ticket.status = TICKET_STATUS_PAID; ticket.updated_at = datetime.utcnow()
        payment_tx = Transaction(user_id=current_user.id,type='ticket_payment_debit',amount=-fine,description=f"Paid DOT Ticket #{ticket.id}")
        db.session.add(payment_tx); db.session.commit()
        flash(f"Ticket #{ticket.id} paid successfully for ${fine:.2f}.", "success")
    except Exception as e: db.session.rollback(); flash(f"Error processing payment: {str(e)}", "danger")
    return redirect(url_for('dot.view_dot_ticket', ticket_id=ticket.id))


@bp.route('/ticket/<int:ticket_id>/dispute/<action>', methods=['POST'])
@login_required
def manage_ticket_dispute(ticket_id, action):
    # ... (existing logic, ensure flash messages are consistent) ...
    if current_user.role not in ['admin', 'supervisor', 'dot_officer']:
        flash("Access denied.", "danger"); return redirect(url_for('dot.supervisor_panel'))
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.dispute_status != DISPUTE_STATUS_PENDING:
        flash("Dispute not pending review.", "warning"); return redirect(url_for('dot.supervisor_panel'))

    resolution_notes = request.form.get('resolution_notes', '').strip() # From supervisor_panel form
    admin_note = f"\nDispute {action}d by {current_user.username} on {datetime.utcnow().strftime('%Y-%m-%d')}."
    if resolution_notes: admin_note += f" Notes: {resolution_notes}"
    ticket.notes = (ticket.notes or "") + admin_note

    if action == 'approve':
        ticket.dispute_status = DISPUTE_STATUS_APPROVED; original_fine = ticket.fine_amount
        ticket.fine_amount = 0; ticket.status = TICKET_STATUS_RESOLVED
        flash(f"Dispute for ticket #{ticket.id} approved. Fine ${original_fine:.2f} waived.", "success")
    elif action == 'reject':
        ticket.dispute_status = DISPUTE_STATUS_REJECTED
        if ticket.fine_amount > 0: ticket.status = TICKET_STATUS_UNPAID
        else: ticket.status = TICKET_STATUS_RESOLVED
        flash(f"Dispute for ticket #{ticket.id} rejected.", "warning")
    else: flash("Invalid dispute action.", "danger"); return redirect(url_for('dot.supervisor_panel'))

    ticket.updated_at = datetime.utcnow()
    try: db.session.commit()
    except Exception as e: db.session.rollback(); flash(f"Error updating ticket: {str(e)}", "danger")
    return redirect(url_for('dot.supervisor_panel'))
