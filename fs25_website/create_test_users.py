from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Clear all users first (optional)
    User.query.delete()

    users = [
        {"username": "player1", "password": "password1", "role": "player"},
        {"username": "officer1", "password": "password2", "role": "dot_officer"},
        {"username": "supervisor1", "password": "password3", "role": "supervisor"},
        {"username": "admin1", "password": "password4", "role": "admin"},
    ]

    for u in users:
        user = User(
            username=u["username"],
            password=generate_password_hash(u["password"]),
            role=u["role"]
        )
        db.session.add(user)

    db.session.commit()
    print("Test users created successfully!")
