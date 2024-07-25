from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()

    # Создание строителя маршрутов
    if not User.query.filter_by(username='builder').first():
        builder = User(
            username='builder',
            password=generate_password_hash('builder_password', method='pbkdf2:sha256'),
            role='builder'
        )
        db.session.add(builder)

    # Создание исполнителя
    if not User.query.filter_by(username='executor').first():
        executor = User(
            username='executor',
            password=generate_password_hash('executor_password', method='pbkdf2:sha256'),
            role='executor'
        )
        db.session.add(executor)

    db.session.commit()
    print("Users created: builder (password: builder_password), executor (password: executor_password)")
