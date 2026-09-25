from app import create_app
from app.extensions import db
from app.models import User

SEED_USERS = [
    {"username": "alice", "role": "sst_user", "password": "password123"},
    {"username": "bob", "role": "director", "password": "password123"},
]


def seed_users():
    created = []
    for entry in SEED_USERS:
        existing = User.query.filter_by(username=entry["username"]).first()
        if existing:
            continue
        user = User(username=entry["username"], role=entry["role"])
        user.set_password(entry["password"])
        db.session.add(user)
        created.append(entry["username"])
    db.session.commit()
    return created


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        created = seed_users()
        usernames = ", ".join(u["username"] + f" ({u['role']})" for u in SEED_USERS)
        if created:
            print(f"Database initialized. Users created: {', '.join(created)}")
        else:
            print(f"Database already initialized. Users: {usernames}")


if __name__ == "__main__":
    main()
