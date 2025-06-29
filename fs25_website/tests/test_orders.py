from flask import url_for
from app.models import User, Product, ProductOrder, ProductOrderItem, Transaction

def test_confirm_purchase_page_loads(client, logged_in_user, new_user_factory, app, db_session):
    _buyer, _client = logged_in_user # Buyer is logged in (from logged_in_user fixture)
    with app.app_context():
        seller_user_id = new_user_factory(username="orders_seller_confirm", email="osc@example.com", password="pw")
        product = Product(name="OrderTestConfirmProd", price=10.99, quantity_available=1, user_id=seller_user_id)
        db_session.add(product)
        db_session.commit()
        product_id = product.id

        response = _client.get(url_for('orders.confirm_purchase', product_id=product_id))
    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    assert "Confirm Your Purchase" in decoded_data
    assert "OrderTestConfirmProd" in decoded_data
    assert "$10.99" in decoded_data

def test_successful_purchase(client, logged_in_user, new_user_factory, app, db_session):
    buyer_initial_balance = 100.00
    seller_initial_balance = 50.00

    with app.app_context():
        # logged_in_user fixture creates a user and logs them in.
        # We need to fetch this user and set their balance.
        buyer_obj, _client = logged_in_user # Use the client from logged_in_user
        buyer = db_session.merge(buyer_obj) # Ensure buyer_obj is session-managed
        buyer.balance = buyer_initial_balance

        seller_id = new_user_factory(username="orders_seller_success", email="oss@example.com", password="pw", balance=seller_initial_balance)
        # seller = db_session.query(User).get(seller_id) # Not strictly needed unless asserting seller name etc.

        product_price = 20.00
        product_name = "PurchasableItem"
        product = Product(name=product_name, price=product_price, quantity_available=5, user_id=seller_id)
        db_session.add(product)
        db_session.commit() # Commit product and updated buyer balance

        product_id = product.id
        initial_qty = product.quantity_available

        # Make the purchase using the client from logged_in_user fixture
        response = _client.post(url_for('orders.execute_purchase', product_id=product_id), follow_redirects=True)

    assert response.status_code == 200
    assert f"Successfully purchased {product_name}".encode() in response.data

    with app.app_context():
        updated_buyer = db_session.query(User).get(buyer.id)
        updated_seller = db_session.query(User).get(seller_id)
        updated_product = db_session.query(Product).get(product_id)

        assert updated_buyer.balance == buyer_initial_balance - product_price
        assert updated_seller.balance == seller_initial_balance + product_price
        assert updated_product.quantity_available == initial_qty - 1

        order = db_session.query(ProductOrder).filter_by(buyer_user_id=buyer.id).order_by(ProductOrder.id.desc()).first()
        assert order is not None
        assert order.total_amount == product_price
        assert order.items.count() == 1 # Corrected for lazy='dynamic'
        order_item = order.items.first() # Corrected for lazy='dynamic'
        assert order_item is not None # Ensure an item was found
        assert order_item.product_id == product_id
        assert order_item.quantity_ordered == 1
        assert order_item.price_at_purchase == product_price

        buyer_tx = db_session.query(Transaction).filter_by(user_id=buyer.id, type='product_purchase_debit', related_product_order_id=order.id).first()
        assert buyer_tx is not None
        assert buyer_tx.amount == -product_price

        seller_tx = db_session.query(Transaction).filter_by(user_id=seller_id, type='product_sale_credit', related_product_order_id=order.id).first()
        assert seller_tx is not None
        assert seller_tx.amount == product_price

def test_purchase_insufficient_funds(client, logged_in_user, new_user_factory, app, db_session):
    buyer_initial_balance = 10.00 # Not enough
    with app.app_context():
        buyer_obj, _client = logged_in_user
        buyer = db_session.merge(buyer_obj)
        buyer.balance = buyer_initial_balance

        seller_id = new_user_factory(username="orders_seller_funds", email="osf@example.com", password="pw")

        product_price = 20.00
        product = Product(name="ExpensiveItem", price=product_price, quantity_available=1, user_id=seller_id)
        db_session.add(product)
        db_session.commit() # Commit product and updated buyer balance
        product_id = product.id

        response = _client.post(url_for('orders.execute_purchase', product_id=product_id), follow_redirects=True)

    assert response.status_code == 200
    assert b"Insufficient funds" in response.data
    assert b"Confirm Your Purchase" in response.data

def test_purchase_own_product(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    with app.app_context():
        product = Product(name="MyOwnItem", price=10, quantity_available=1, user_id=user.id)
        db_session.add(product)
        db_session.commit()
        product_id = product.id

        response = _client.post(url_for('orders.execute_purchase', product_id=product_id), follow_redirects=True)

    assert response.status_code == 200
    assert b"You cannot purchase your own product." in response.data

def test_purchase_out_of_stock(client, logged_in_user, new_user_factory, app, db_session):
    with app.app_context():
        buyer_obj, _client = logged_in_user
        buyer = db_session.merge(buyer_obj)
        buyer.balance = 100.0 # Sufficient funds

        seller_id = new_user_factory(username="orders_seller_stock", email="oss@example.com", password="pw")
        product = Product(name="OutOfStockItem", price=10, quantity_available=0, user_id=seller_id)
        db_session.add(product)
        db_session.commit() # Commit product and buyer changes
        product_id = product.id

        response = _client.post(url_for('orders.execute_purchase', product_id=product_id), follow_redirects=True)

    assert response.status_code == 200
    assert b"This product is out of stock." in response.data

def test_purchase_inactive_product(client, logged_in_user, new_user_factory, app, db_session):
    with app.app_context():
        buyer_obj, _client = logged_in_user
        buyer = db_session.merge(buyer_obj)
        buyer.balance = 100.0

        seller_id = new_user_factory(username="orders_seller_inactive", email="osi@example.com", password="pw")
        product = Product(name="InactiveItem", price=10, quantity_available=1, user_id=seller_id, is_active=False)
        db_session.add(product)
        db_session.commit() # Commit product and buyer changes
        product_id = product.id

        response = _client.post(url_for('orders.execute_purchase', product_id=product_id), follow_redirects=True)

    assert response.status_code == 200
    assert b"This product is no longer available." in response.data
