from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import logging
from models import db, User, Point, Route

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///routes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret_key_here'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Координаты фиксированной начальной точки (например, Красная площадь в Москве)
start_point = [55.753215, 37.622504]

# Логирование
logging.basicConfig(level=logging.DEBUG)

# Функция для получения маршрута через OSRM API
def get_route(start, points):
    coordinates = ";".join([f"{p[1]},{p[0]}" for p in points])
    url = f'http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{coordinates}?overview=full&geometries=geojson'
    response = requests.get(url).json()
    if response['code'] == 'Ok':
        return response['routes'][0]['geometry']['coordinates']
    return []

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'builder':
            return redirect(url_for('builder'))
        elif current_user.role == 'executor':
            return redirect(url_for('executor'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/builder')
@login_required
def builder():
    if current_user.role != 'builder':
        return redirect(url_for('index'))
    executors = User.query.filter_by(role='executor').all()
    routes = Route.query.filter_by(user_id=current_user.id).all()
    return render_template('builder.html', executors=executors, routes=routes)

@app.route('/executor')
@login_required
def executor():
    if current_user.role != 'executor':
        return redirect(url_for('index'))
    routes = Route.query.filter_by(user_id=current_user.id).all()
    return render_template('executor.html', routes=routes)

@app.route('/calculate', methods=['POST'])
@login_required
def calculate():
    if current_user.role != 'builder':
        return jsonify({'error': 'Unauthorized'}), 403

    points = request.json['points']
    route_name = request.json['route_name']
    executor_id = request.json['executor_id']
    all_points = [start_point] + points

    # Получаем маршрут
    route_coords = get_route(start_point, points)
    if not route_coords:
        return jsonify({'error': 'Could not calculate route'}), 500

    # Сохраняем маршрут в базе данных
    route = Route(name=route_name, user_id=executor_id)
    db.session.add(route)
    db.session.commit()

    for point in points:
        db.session.add(Point(latitude=point[0], longitude=point[1], route_id=route.id))
    db.session.commit()

    # Формируем ссылки для Google Maps
    google_maps_urls = []
    for i in range(1, len(all_points)):
        google_maps_urls.append(
            f"https://www.google.com/maps/dir/{all_points[i-1][0]},{all_points[i-1][1]}/{all_points[i][0]},{all_points[i][1]}"
        )

    return jsonify({
        'route': route_coords,
        'google_maps_urls': google_maps_urls
    })

@app.route('/view_route/<int:route_id>')
@login_required
def view_route(route_id):
    route = Route.query.get_or_404(route_id)
    if current_user.id != route.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    points = Point.query.filter_by(route_id=route.id).all()
    points_data = [{'latitude': p.latitude, 'longitude': p.longitude} for p in points]

    # Добавление начальной точки
    all_points = [start_point] + [[p['latitude'], p['longitude']] for p in points_data]

    # Формируем ссылки для Google Maps
    google_maps_urls = []
    for i in range(1, len(all_points)):
        google_maps_urls.append(
            f"https://www.google.com/maps/dir/{all_points[i-1][0]},{all_points[i-1][1]}/{all_points[i][0]},{all_points[i][1]}"
        )

    return jsonify({
        'points': points_data,
        'google_maps_urls': google_maps_urls
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
