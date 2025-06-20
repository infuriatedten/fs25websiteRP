from flask import Blueprint, request, jsonify
from app import db
from app.models import Ticket, TicketItem, User, Company
from flask_login import login_required, current_user

bp = Blueprint('tickets', __name__, url_prefix='/tickets')

@bp.route('/', methods=['GET'])
@login_required
def list_tickets():
    # List tickets issued to current user (billed)
    tickets = Ticket.query.filter_by(issued_to=current_user.id).all()
    result = []
    for t in tickets:
        result.append({
            'id': t.id,
            'reason': t.reason,
            'fine_amount': t.fine_amount,
            'company': t.company.name if t.company else None,
            'paid': t.paid,
            'created_at': t.created_at.isoformat(),
            'total_price': t.total_price,
            'items': [
                {
                    'material_name': item.material_name,
                    'quantity': item.quantity,
                    'price_per_unit': item.price_per_unit,
                    'total_price': item.total_price
                }
                for item in t.items
            ]
        })
    return jsonify(result), 200

@bp.route('/create', methods=['POST'])
@login_required
def create_ticket():
    """
    Expected JSON:
    {
      "reason": "Reason for ticket",
      "fine_amount": 50,
      "company_id": 1,
      "items": [
        {"material_name": "Wood", "quantity": 10, "price_per_unit": 5.0},
        {"material_name": "Steel", "quantity": 5, "price_per_unit": 20.0}
      ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    reason = data.get('reason')
    fine_amount = data.get('fine_amount', 0)
    company_id = data.get('company_id')
    items_data = data.get('items', [])

    if not reason or not company_id:
        return jsonify({"error": "Missing required fields"}), 400

    # Verify company exists
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    ticket = Ticket(
        reason=reason,
        fine_amount=fine_amount,
        issued_to=current_user.id,
        company_id=company_id
    )
    db.session.add(ticket)
    db.session.flush()  # To get ticket.id before commit

    for item in items_data:
        material_name_
