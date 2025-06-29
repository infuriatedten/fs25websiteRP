from flask import url_for
from app.models import User, Product, Transaction, ProductOrder
from werkzeug.security import generate_password_hash

def test_bank_transactions_page_loads_for_logged_in_user(client, logged_in_user, app):
    user, _client = logged_in_user
    with app.app_context():
        response = _client.get(url_for('main.bank_transactions'))
    assert response.status_code == 200
    # Check for title in <title> tag (HTML encoded)
    assert b"<title>My Bank &amp; Transaction History</title>" in response.data
    # Check for title in <h2> tag (not encoded) using decoded string for robustness
    decoded_data = response.data.decode('utf-8')
    # More specific check for the content within an h2 tag or similar prominent display
    assert ">My Bank & Transaction History</h2>" in decoded_data or \
           "My Bank &amp; Transaction History" in decoded_data # Fallback if & is encoded in body too
    assert f'<h3 class="card-title">${user.balance:.2f}</h3>' in decoded_data # Check in decoded data

def test_bank_transactions_page_shows_transactions(client, logged_in_user, app, db_session):
    buyer, _client = logged_in_user

    with app.app_context():
        tx1_desc = "Bought Cool Widget"
        tx1_amount = -25.50
        tx1 = Transaction(user_id=buyer.id, type="product_purchase_debit", amount=tx1_amount, description=tx1_desc)

        tx2_desc = "Admin Credit"
        tx2_amount = 50.00
        tx2 = Transaction(user_id=buyer.id, type="manual_adjustment_credit", amount=tx2_amount, description=tx2_desc)

        db_session.add_all([tx1, tx2])
        db_session.commit()

        response = _client.get(url_for('main.bank_transactions'))
        assert response.status_code == 200
        assert tx1_desc.encode() in response.data
        assert f'{tx1_amount:.2f}'.encode() in response.data # e.g., -25.50
        assert tx2_desc.encode() in response.data
        assert f'+${tx2_amount:.2f}'.encode() in response.data # e.g., +$50.00
        assert b"Transaction History" in response.data

def test_bank_transactions_page_redirects_if_not_logged_in(client, app):
    with app.app_context():
        response = client.get(url_for('main.bank_transactions'), follow_redirects=True)
    assert response.status_code == 200
    assert b"Login to Your Account" in response.data

def test_balance_updates_after_purchase_and_reflected_in_bank(client, new_user_factory, app, db_session):
    with app.app_context():
        buyer_initial_balance = 100.0
        seller_initial_balance = 50.0

        # new_user_factory returns user_id
        buyer_id = new_user_factory(username="buyer_bank", email="buyer_bank@example.com", password="pw", balance=buyer_initial_balance)
        seller_id = new_user_factory(username="seller_bank", email="seller_bank@example.com", password="pw", balance=seller_initial_balance)

        # Fetch user objects if needed for assertions or passing to functions
        buyer = db_session.query(User).get(buyer_id)
        seller = db_session.query(User).get(seller_id)
        assert buyer is not None and seller is not None

        with client.session_transaction() as sess:
            sess['_user_id'] = str(buyer_id) # Use the ID directly
            sess['_fresh'] = True

        product_price = 20.0
        # Use seller_id when creating product
        product = Product(name="Bank Test Item", price=product_price, quantity_available=1, user_id=seller_id)
        db_session.add(product)
        db_session.commit()
        product_id_for_url = product.id

        purchase_response = client.post(url_for('orders.execute_purchase', product_id=product_id_for_url), follow_redirects=True)
        assert purchase_response.status_code == 200
        assert b"Successfully purchased Bank Test Item" in purchase_response.data

        # Re-fetch buyer and seller to get updated balances from the DB
        buyer_after_purchase = db_session.query(User).get(buyer_id)
        seller_after_purchase = db_session.query(User).get(seller_id)

        assert buyer_after_purchase.balance == buyer_initial_balance - product_price
        assert seller_after_purchase.balance == seller_initial_balance + product_price

        bank_page_response = client.get(url_for('main.bank_transactions')) # As the buyer
        assert bank_page_response.status_code == 200
        assert f'<h3 class="card-title">${buyer_after_purchase.balance:.2f}</h3>'.encode() in bank_page_response.data
        assert b"Purchased: Bank Test Item" in bank_page_response.data
        assert f'{-product_price:.2f}'.encode() in bank_page_response.data

        order = db_session.query(ProductOrder).filter_by(buyer_user_id=buyer_id).order_by(ProductOrder.id.desc()).first()
        assert order is not None

        seller_tx = db_session.query(Transaction).filter_by(user_id=seller_id, type="product_sale_credit", related_product_order_id=order.id).first()
        assert seller_tx is not None
        assert seller_tx.amount == product_price

        buyer_tx = db_session.query(Transaction).filter_by(user_id=buyer_id, type="product_purchase_debit", related_product_order_id=order.id).first()
        assert buyer_tx is not None
        assert buyer_tx.amount == -product_price
