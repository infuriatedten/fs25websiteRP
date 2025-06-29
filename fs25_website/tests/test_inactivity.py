from flask import url_for, session
from datetime import datetime, timedelta
import time # For simulating passage of time

def test_inactivity_logout(client, logged_in_user, app):
    user, _client = logged_in_user # User is now logged in

    # Access a page to set initial activity timestamp
    with app.app_context():
        response = _client.get(url_for('main.player_home')) # Or any @login_required route
        assert response.status_code == 302 # player_home redirects to itself or other places based on role
        # Follow the redirect to ensure the page is loaded and before_request runs
        response = _client.get(response.location)
        assert response.status_code == 200


    # Check that the activity timestamp is in the session
    with _client.session_transaction() as sess:
        assert '_last_activity_ts' in sess

    # Simulate time passing beyond the inactivity limit
    # Get the timeout from app config (defaulting if necessary)
    inactivity_timeout_seconds = app.config.get('USER_INACTIVITY_TIMEOUT_SECONDS', 3 * 60 * 60)

    # To simulate time passing, we can't actually use time.sleep in a test like this effectively.
    # Instead, we modify the stored timestamp in the session to be in the past.
    with _client.session_transaction() as sess:
        # Set last activity to be older than the timeout
        past_activity_dt = datetime.utcnow() - timedelta(seconds=inactivity_timeout_seconds + 60) # 1 minute past timeout
        sess['_last_activity_ts'] = past_activity_dt.isoformat()
        sess.modified = True # Ensure session is saved

    # Make another request - the before_request handler should now log the user out
    with app.app_context():
        response_after_timeout = _client.get(url_for('main.player_home'), follow_redirects=True)

    assert response_after_timeout.status_code == 200 # Should redirect to login, which is 200

    # Check for flash message
    # Since we can't guarantee flash messages persist reliably across separate client requests in tests
    # without a full browser, we'll check the session directly after the logout-triggering request.
    # However, follow_redirects=True means the flash might be consumed by the redirected page.
    # A more direct check is to see if current_user is no longer authenticated in a new request context.

    # For now, let's check if the user is redirected to login and the flash message is present in the data
    decoded_data = response_after_timeout.data.decode('utf-8')
    assert "You have been logged out due to inactivity." in decoded_data
    assert "Login to Your Account" in decoded_data # Check if it's the login page

    # Verify user is logged out by trying to access a protected page again
    with app.app_context():
        response_final_check = _client.get(url_for('main.player_home'), follow_redirects=True)
    assert "Login to Your Account" in response_final_check.data.decode('utf-8')


def test_activity_updates_timestamp(client, logged_in_user, app):
    _user, _client = logged_in_user

    initial_ts = None
    with app.app_context():
        _client.get(url_for('main.player_home'), follow_redirects=True) # Initial request
    with _client.session_transaction() as sess:
        initial_ts_str = sess.get('_last_activity_ts')
        assert initial_ts_str is not None
        initial_ts = datetime.fromisoformat(initial_ts_str)

    # Simulate some interaction or just passage of a short amount of time
    # For this test, we'll just make another request.
    # We can't use time.sleep() effectively to simulate real passage of time for session timeout.
    # The core idea is that each request updates the timestamp.

    # To "simulate" time passing slightly for the purpose of checking if the timestamp updates,
    # we'd ideally check the timestamp, then make another request, then check it changed.
    # This doesn't test the timeout itself, but that activity *resets* the timeout countdown.

    with app.app_context():
        _client.get(url_for('products.list_products')) # Another request to a different page

    updated_ts = None
    with _client.session_transaction() as sess:
        updated_ts_str = sess.get('_last_activity_ts')
        assert updated_ts_str is not None
        updated_ts = datetime.fromisoformat(updated_ts_str)

    assert updated_ts > initial_ts
```
