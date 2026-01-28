from app import app, db, User

with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username='admin', password='password'))
        db.session.add(User(username='user', password='pass'))
        db.session.commit()