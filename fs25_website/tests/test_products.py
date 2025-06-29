from flask import url_for, get_flashed_messages
from app.models import User, Product

def test_create_product_page_loads(client, logged_in_user, app):
    _user, _client = logged_in_user
    with app.app_context():
        response = _client.get(url_for('products.create_product'))
    assert response.status_code == 200
    assert b"Create New Product" in response.data

def test_create_product_success(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    product_name = "Test Widget"
    product_desc = "A fantastic widget for testing."
    product_price = 19.99
    product_qty = 10

    with app.app_context():
        response = _client.post(url_for('products.create_product'), data={
            'name': product_name,
            'description': product_desc,
            'price': str(product_price),
            'quantity_available': str(product_qty)
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"My Listed Products" in response.data
    assert b"Product listed successfully!" in response.data

    product = Product.query.filter_by(name=product_name).first()
    assert product is not None
    assert product.user_id == user.id
    assert product.description == product_desc
    assert product.price == product_price
    assert product.quantity_available == product_qty
    assert product.is_active is True

def test_create_product_missing_fields(client, logged_in_user, app):
    _user, _client = logged_in_user
    with app.app_context():
        response = _client.post(url_for('products.create_product'), data={
            'name': 'Incomplete Product'
        }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Name, price, and quantity are required." in response.data
    assert b"Create New Product" in response.data

def test_my_products_page(client, logged_in_user, new_user_factory, app, db_session):
    user, _client = logged_in_user

    with app.app_context():
        db_session.add(Product(name="UserProduct1", price=10, quantity_available=5, user_id=user.id))
        db_session.add(Product(name="UserProduct2", price=20, quantity_available=3, user_id=user.id, is_active=False))
        db_session.commit()

        other_user_id = new_user_factory(username="other_seller", email="other@sel.com", password="pw")
        db_session.add(Product(name="OtherUserProduct", price=30, quantity_available=1, user_id=other_user_id))
        db_session.commit()

        response = _client.get(url_for('products.my_products'))

    assert response.status_code == 200
    assert b"My Listed Products" in response.data
    assert b"UserProduct1" in response.data
    assert b"UserProduct2" in response.data
    assert b"Active" in response.data
    assert b"Inactive" in response.data
    assert b"OtherUserProduct" not in response.data

def test_edit_product_page_loads_and_updates(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    product_id = None
    product_original_name = "Editable"
    with app.app_context():
        product = Product(name=product_original_name, description="Old Desc", price=15, quantity_available=7, user_id=user.id)
        db_session.add(product)
        db_session.commit()
        product_id = product.id

        response_get = _client.get(url_for('products.edit_product', product_id=product_id))
        assert response_get.status_code == 200
        decoded_data_get = response_get.data.decode('utf-8')
        assert f"<h2>Edit {product_original_name}</h2>" in decoded_data_get
        assert f"<title>Edit {product_original_name}</title>".encode() in response_get.data
        assert b"Old Desc" in response_get.data

        updated_name = "Updated Widget"
        updated_desc = "New Shiny Description"
        updated_price = 25.50
        updated_qty = 3

        response_post = _client.post(url_for('products.edit_product', product_id=product_id), data={
            'name': updated_name,
            'description': updated_desc,
            'price': str(updated_price),
            'quantity_available': str(updated_qty),
            'is_active': 'on'
        }, follow_redirects=True)

        assert response_post.status_code == 200
        assert b"My Listed Products" in response_post.data
        assert b"Product updated successfully!" in response_post.data

        updated_product = db_session.query(Product).get(product_id)
        assert updated_product.name == updated_name
        assert updated_product.description == updated_desc
        assert updated_product.price == updated_price
        assert updated_product.quantity_available == updated_qty
        assert updated_product.is_active is True

def test_edit_product_unauthorized(client, logged_in_user, new_user_factory, app, db_session):
    _user, _client = logged_in_user

    with app.app_context():
        other_user_id = new_user_factory(username="owner", email="owner@example.com", password="pw")
        other_product = Product(name="OthersProduct", price=5, quantity_available=1, user_id=other_user_id)
        db_session.add(other_product)
        db_session.commit()
        other_product_id = other_product.id

        response = _client.get(url_for('products.edit_product', product_id=other_product_id), follow_redirects=True)

    assert response.status_code == 200
    assert b"You are not authorized to edit this product." in response.data
    assert b"Marketplace" in response.data

def test_activate_deactivate_product(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    product_id = None
    product_name_for_test = "Switchable" # Define for use in assertions
    with app.app_context():
        product = Product(name=product_name_for_test, price=10, quantity_available=1, user_id=user.id, is_active=True)
        db_session.add(product)
        db_session.commit()
        product_id = product.id

        # Deactivate
        response_deact = _client.post(url_for('products.deactivate_product', product_id=product_id), follow_redirects=True)
        assert response_deact.status_code == 200
        decoded_deact_data = response_deact.data.decode('utf-8')
        # Check for the flash message within its typical alert structure
        expected_deact_msg_literal = f"Product '{product_name_for_test}' has been deactivated."
        expected_deact_msg_encoded = f"Product &#39;{product_name_for_test}&#39; has been deactivated."
        assert f'<div class="alert alert-success' in decoded_deact_data # Check for alert div
        assert (expected_deact_msg_literal in decoded_deact_data or
                expected_deact_msg_encoded in decoded_deact_data) # Check for the message text
        assert db_session.query(Product).get(product_id).is_active is False

        # Activate
        response_act = _client.post(url_for('products.activate_product', product_id=product_id), follow_redirects=True)
        assert response_act.status_code == 200
        decoded_act_data = response_act.data.decode('utf-8')
        expected_act_msg_literal = f"Product '{product_name_for_test}' has been activated."
        expected_act_msg_encoded = f"Product &#39;{product_name_for_test}&#39; has been activated."
        assert f'<div class="alert alert-success' in decoded_act_data # Check for alert div
        assert (expected_act_msg_literal in decoded_act_data or
                expected_act_msg_encoded in decoded_act_data) # Check for the message text
        assert db_session.query(Product).get(product_id).is_active is True

def test_marketplace_shows_active_products(client, new_user_factory, app, db_session):
    with app.app_context():
        user1_id = new_user_factory(username="seller1", email="s1@ex.com", password="p")
        user2_id = new_user_factory(username="seller2", email="s2@ex.com", password="p")

        db_session.add(Product(name="ActiveProd", price=1, quantity_available=1, user_id=user1_id, is_active=True))
        db_session.add(Product(name="InactiveProd", price=1, quantity_available=1, user_id=user2_id, is_active=False))
        db_session.commit()

        response = client.get(url_for('products.list_products'))

    assert response.status_code == 200
    assert b"Marketplace" in response.data
    assert b"ActiveProd" in response.data
    assert b"InactiveProd" not in response.data
