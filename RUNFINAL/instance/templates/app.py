# Must be first!
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True



db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class Door(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Empty')

class DoorDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    door_id = db.Column(db.Integer, db.ForeignKey('door.id'), nullable=False, unique=True)
    run_number = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    door = db.relationship('Door', backref=db.backref('detail', uselist=False))

# We use app_context manually instead of @before_first_request to avoid issues in some environments
def init_db():
    with app.app_context():
        db.create_all()
        if Door.query.count() == 0:
            for i in range(50, 100):
                db.session.add(Door(name=f"Run  {i}", status="Backhaul"))
            db.session.commit()

@app.route('/')
def index():
    doors = Door.query.all()
    return render_template('index.html', doors=doors)

@app.route('/runs')
def runs():
    doors = Door.query.all()
    return render_template('runs.html', doors=doors)

@app.route('/api/door/<int:door_id>/details', methods=['GET', 'POST'])
def door_details(door_id):
    if request.method == 'GET':
        detail = DoorDetail.query.filter_by(door_id=door_id).first()
        if detail:
            return jsonify({
                'door_id': door_id,
                'run_number': detail.run_number,
                'loader': detail.loader,
                'trailer': detail.trailer,
                'notes': detail.notes
            })
        return jsonify({'door_id': door_id}), 200

    # POST - create or update
    data = request.get_json() or {}
    run_number = data.get('run_number')
    loader = data.get('loader')
    trailer = data.get('trailer')
    notes = data.get('notes')

    detail = DoorDetail.query.filter_by(door_id=door_id).first()
    if not detail:
        detail = DoorDetail(door_id=door_id, run_number=run_number, loader=loader, trailer=trailer, notes=notes)
        db.session.add(detail)
    else:
        detail.run_number = run_number
        detail.loader = loader
        detail.trailer = trailer
        detail.notes = notes

    db.session.commit()
    # broadcast saved details to other clients
    emit_payload = {
        'door_id': door_id,
        'run_number': run_number,
        'loader': loader,
        'trailer': trailer,
        'notes': notes
    }
    socketio.emit('door_details_saved', emit_payload)
    return jsonify(emit_payload), 200


@app.route('/api/reset_all', methods=['POST'])
def reset_all():
    # set all doors to Empty and emit status updates
    doors = Door.query.all()
   
    for door in doors:
        socketio.emit('status_updated', {'door_id': door.id, 'status': door.status})
    return jsonify({'reset': True, 'count': len(doors)}), 200

@socketio.on('update_status')
def on_update_status(data):
    door_id = data.get('door_id')
    new_status = data.get('status')
    new_status = data.get('door_status', new_status)  # support both keys
    new_status = data.get('trailer_status', new_status)  # support both keys
    door = Door.query.get(door_id)
    if door:
        door.status = new_status
        db.session.commit()
        socketio.emit('status_updated', {
            'door_id': door.id,
            'status': door.status
        })

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
