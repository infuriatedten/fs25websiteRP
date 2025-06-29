from flask import url_for
from app.models import User, Vehicle

def test_my_vehicles_page_loads(client, logged_in_user, app):
    _user, _client = logged_in_user
    with app.app_context():
        response = _client.get(url_for('dot.my_vehicles'))
    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    assert "<h2>My Registered Vehicles</h2>" in decoded_data

def test_add_vehicle_page_loads(client, logged_in_user, app):
    _user, _client = logged_in_user
    with app.app_context():
        response = _client.get(url_for('dot.add_vehicle'))
    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    assert "<h2>Add New Vehicle</h2>" in decoded_data

def test_add_vehicle_success(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    plate = "TESTV1"
    with app.app_context():
        post_response = _client.post(url_for('dot.add_vehicle'), data={
            'plate': plate, 'make': "Generic", 'model': "TestModel", 'year': "2023", 'color': "Blue"
        })
        assert post_response.status_code == 302
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        # From route: flash(f'Vehicle {plate} added successfully!', 'success')
        expected_msg_tuple = ('success', f"Vehicle {plate} added successfully!")
        assert expected_msg_tuple in flashes
        _client.get(url_for('dot.my_vehicles'))
    vehicle = db_session.query(Vehicle).filter_by(plate=plate).first()
    assert vehicle is not None; assert vehicle.owner_id == user.id

def test_add_vehicle_duplicate_plate(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    plate = "DUPVCL"
    with app.app_context():
        db_session.add(Vehicle(plate=plate, make="Make1", model="Model1", owner_id=user.id))
        db_session.commit()
        response = _client.post(url_for('dot.add_vehicle'), data={'plate': plate, 'make': "Make2"})
    assert response.status_code == 200
    decoded_data = response.data.decode('utf-8')
    # From route: flash(f'Vehicle with plate {plate} already exists.', 'danger')
    expected_msg = f"Vehicle with plate {plate} already exists."
    assert '<div class="alert alert-danger' in decoded_data
    assert expected_msg in decoded_data
    assert "<h2>Add New Vehicle</h2>" in decoded_data

def test_edit_vehicle_page_loads_and_updates(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    plate = "EDITME"
    vehicle_id = None
    with app.app_context():
        vehicle = Vehicle(plate=plate, make="OldMake", model="OldModel", owner_id=user.id, year=2020, color="Red")
        db_session.add(vehicle); db_session.commit(); vehicle_id = vehicle.id
        response_get = _client.get(url_for('dot.edit_vehicle', vehicle_id=vehicle_id))
        assert response_get.status_code == 200
        decoded_data_get = response_get.data.decode('utf-8')
        assert f"<h2>Edit Vehicle {plate}</h2>" in decoded_data_get
        assert "OldMake" in decoded_data_get

        updated_make = "NewMake"; updated_color = "Green"
        post_response = _client.post(url_for('dot.edit_vehicle', vehicle_id=vehicle_id), data={
            'plate': plate, 'make': updated_make, 'model': "OldModel", 'year': '2020', 'color': updated_color
        })
        assert post_response.status_code == 302
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        # From route: flash(f'Vehicle {new_plate} updated!', 'success')
        expected_msg_tuple = ('success', f"Vehicle {plate} updated!") # new_plate is 'plate' from form
        assert expected_msg_tuple in flashes
        _client.get(url_for('dot.my_vehicles'))
        updated_vehicle = db_session.query(Vehicle).get(vehicle_id)
        assert updated_vehicle.make == updated_make

def test_delete_vehicle_success(client, logged_in_user, app, db_session):
    user, _client = logged_in_user
    plate = "DELME"
    vehicle_id = None
    with app.app_context():
        vehicle = Vehicle(plate=plate, make="ToDelete", model="ToDelete", owner_id=user.id)
        db_session.add(vehicle); db_session.commit(); vehicle_id = vehicle.id
        post_response = _client.post(url_for('dot.delete_vehicle', vehicle_id=vehicle_id))
        assert post_response.status_code == 302
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        # From route: flash(f'Vehicle {plate_to_report} deleted successfully.', 'success')
        expected_msg_tuple = ('success', f"Vehicle {plate} deleted successfully.")
        assert expected_msg_tuple in flashes
        _client.get(url_for('dot.my_vehicles'))
    assert db_session.query(Vehicle).get(vehicle_id) is None

def test_edit_delete_unauthorized_vehicle(client, logged_in_user, new_user_factory, app, db_session):
    _user1, _client = logged_in_user
    with app.app_context():
        owner_id = new_user_factory(username="vehicleowner", email="vo@example.com", password="pw")
        vehicle = Vehicle(plate="OTHERSV",make="OtherMake",model="OtherModel",owner_id=owner_id)
        db_session.add(vehicle); db_session.commit(); target_vehicle_id = vehicle.id

        get_edit_response = _client.get(url_for('dot.edit_vehicle', vehicle_id=target_vehicle_id))
        assert get_edit_response.status_code == 302
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        # From route: flash('Not authorized to edit this vehicle.', 'danger')
        assert ('danger', "Not authorized to edit this vehicle.") in flashes
        _client.get(url_for('dot.my_vehicles'))

        post_delete_response = _client.post(url_for('dot.delete_vehicle', vehicle_id=target_vehicle_id))
        assert post_delete_response.status_code == 302
        with _client.session_transaction() as session:
            flashes = session.get('_flashes', [])
        # From route: flash('Not authorized to delete this vehicle.', 'danger')
        assert ('danger', "Not authorized to delete this vehicle.") in flashes
    assert db_session.query(Vehicle).get(target_vehicle_id) is not None
