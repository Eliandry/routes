from flask import Flask, render_template, request, jsonify, redirect, url_for
from models import db, Point, Route
import requests
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///routes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

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

@app.route('/')
def index():
    routes = Route.query.all()
    return render_template('index.html', routes=routes)

@app.route('/calculate', methods=['POST'])
def calculate():
    points = request.json['points']
    route_name = request.json['route_name']
    all_points = [start_point] + points

    # Получаем маршрут
    route_coords = get_route(start_point, points)
    if not route_coords:
        return jsonify({'error': 'Could not calculate route'}), 500

    # Сохраняем маршрут в базе данных
    route = Route(name=route_name)
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
def view_route(route_id):
    route = Route.query.get_or_404(route_id)
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
