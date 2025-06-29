from flask import url_for
from app.models import User, Vehicle, Ticket, Transaction
from app.models import TICKET_STATUS_UNPAID, TICKET_STATUS_PAID, TICKET_STATUS_DISPUTED, \
                     TICKET_STATUS_WARNING, TICKET_STATUS_RESOLVED, \
                     DISPUTE_STATUS_PENDING, DISPUTE_STATUS_APPROVED, DISPUTE_STATUS_REJECTED, \
                     DISPUTE_STATUS_NONE
# werkzeug.security generate_password_hash is not directly used here, but User model might use it.

# Helper function to create a DOT officer/admin for issuing tickets
def create_dot_officer(new_user_factory, app_context_source, username="dotofficer", email="dot@example.com"):
    # new_user_factory returns user_id. User.query.get needs an app context.
    # The 'app' fixture in tests using this helper will provide the overarching context.
    officer_id = new_user_factory(username=username, email=email, password="pw", role="dot_officer", balance=1000)
    # Ensure User.query.get is called within an app context if this helper is used outside one.
    # However, tests will call this helper from within their own app_context block.
    return User.query.get(officer_id)

# Helper function to log in a specific user
def login_specific_user(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

def test_issue_ticket_by_dot_officer_success_fine(client, new_user_factory, app, db_session):
    with app.app_context(): # This app_context is crucial
        dot_officer = create_dot_officer(new_user_factory, app, username="dot_fine_issuer", email="dfi@example.com")
        player_id = new_user_factory(username="player_fine", email="pf@example.com", password="pw")

        vehicle = Vehicle(plate="TICKETME", make="TestMake", model="TestModel", owner_id=player_id)
        db_session.add(vehicle)
        db_session.commit()
        vehicle_id = vehicle.id

        login_specific_user(client, dot_officer.id)

        response = client.post(url_for('dot.issue_ticket'), data={
            'user_id': str(player_id),
            'vehicle_id': str(vehicle_id),
            'reason': "Speeding Violation",
            'fine_amount': "50.00",
            'notes': "Exceeded limit by 20mph"
        }, follow_redirects=True)

        assert response.status_code == 200
        decoded_data = response.data.decode('utf-8')
        # Assuming supervisor_panel is the redirect target and it renders flash messages
        assert "Ticket issued successfully." in decoded_data # Check for flash message

        ticket = db_session.query(Ticket).filter_by(reason="Speeding Violation").first()
        assert ticket is not None
        assert ticket.issued_to == player_id
        assert ticket.issuer_id == dot_officer.id
        assert ticket.vehicle_id == vehicle_id
        assert ticket.fine_amount == 50.00
        assert ticket.notes == "Exceeded limit by 20mph"
        assert ticket.status == TICKET_STATUS_UNPAID

def test_issue_ticket_by_dot_officer_success_warning(client, new_user_factory, app, db_session):
    with app.app_context():
        dot_officer = create_dot_officer(new_user_factory, app, username="dot_warn_issuer", email="dwi@example.com")
        player_id = new_user_factory(username="player_warn", email="pw@example.com", password="pw")

        login_specific_user(client, dot_officer.id)

        response = client.post(url_for('dot.issue_ticket'), data={
            'user_id': str(player_id),
            'reason': "Broken taillight (Warning)",
            'fine_amount': "0",
            'notes': "Advised to fix immediately."
        }, follow_redirects=True)

        assert response.status_code == 200
        assert "Ticket issued successfully." in response.data.decode('utf-8')

        ticket = db_session.query(Ticket).filter_by(reason="Broken taillight (Warning)").first()
        assert ticket is not None
        assert ticket.fine_amount == 0
        # Check the logic in routes.py: issue_ticket sets status based on fine_amount
        assert ticket.status == TICKET_STATUS_WARNING

def test_issue_ticket_unauthorized_user(client, logged_in_user, app, db_session, new_user_factory):
    player, _client = logged_in_user
    with app.app_context():
        other_player_id = new_user_factory(username="player_to_ticket", email="ptt@example.com", password="pw")
        response = _client.post(url_for('dot.issue_ticket'), data={
            'user_id': str(other_player_id), 'reason': "Test", 'fine_amount': "10"
        }, follow_redirects=True) # Route redirects to dot.dot_home, which redirects to my_vehicles for player

    assert response.status_code == 200
    # Flash message is set before redirect. Check response data of the final page.
    assert "Access denied." in response.data.decode('utf-8')

def test_my_dot_tickets_page_loads(client, logged_in_user, app, db_session):
    player, _client = logged_in_user
    with app.app_context():
        db_session.add(Ticket(reason="Parking fine", fine_amount=25, issued_to=player.id, status=TICKET_STATUS_UNPAID))
        db_session.commit()
        response = _client.get(url_for('dot.my_dot_tickets'))

    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    assert "<h2>My DOT Tickets</h2>" in decoded_data
    assert "Parking fine" in decoded_data

def test_view_dot_ticket_page_loads(client, logged_in_user, new_user_factory, app, db_session):
    player, _client = logged_in_user
    with app.app_context():
        dot_officer = create_dot_officer(new_user_factory, app, username="dot_issuer_view", email="div@example.com")
        ticket = Ticket(reason="Test View Ticket", fine_amount=30, issued_to=player.id, issuer_id=dot_officer.id, status=TICKET_STATUS_UNPAID)
        db_session.add(ticket)
        db_session.commit()
        ticket_id = ticket.id

        response = _client.get(url_for('dot.view_dot_ticket', ticket_id=ticket_id))

    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    assert f"<h2>View DOT Ticket #{ticket_id}</h2>" in decoded_data
    assert "Test View Ticket" in decoded_data
    assert "Pay Fine" in decoded_data
    assert "Dispute Ticket" in decoded_data

def test_view_dot_ticket_unauthorized(client, logged_in_user, new_user_factory, app, db_session):
    _player1, _client = logged_in_user
    with app.app_context():
        player2_id = new_user_factory(username="player_other_ticket", email="pot@example.com", password="pw")
        ticket_for_player2 = Ticket(reason="Other's Ticket", fine_amount=10, issued_to=player2_id, status=TICKET_STATUS_UNPAID)
        db_session.add(ticket_for_player2)
        db_session.commit()
        ticket_id = ticket_for_player2.id

        # POST/GET that causes redirect and sets flash
        response_action = _client.get(url_for('dot.view_dot_ticket', ticket_id=ticket_id))
        assert response_action.status_code == 302 # Expect redirect
        with app.test_request_context(): # For url_for in assertion
            assert response_action.location == url_for('dot.my_dot_tickets')

        # Check flash message in session
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        expected_flash = ('danger', "Not authorized to view this ticket.")
        assert expected_flash in flashes

        # Optionally, check the content of the page after redirect
        response_after_redirect = _client.get(url_for('dot.my_dot_tickets')) # Consume the flash
    assert response_after_redirect.status_code == 200
    # The flash message will be rendered on this page, so it won't be in session for a *second* GET
    # but this test confirms the redirect and that the flash *was* set.
    # To check if it rendered, you'd check response_after_redirect.data.
    # For now, checking it was set is the primary goal.
    assert b"My DOT Tickets" in response_after_redirect.data # Check title of redirected page
```
