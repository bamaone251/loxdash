# Must be first!
import eventlet
eventlet.monkey_patch()
import os
import sqlite3
from io import BytesIO
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

DB_PATH = os.environ.get("instance/database.db", "database.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'f3cfe9ed8fae309f02079dbf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    loader = db.Column(db.String(100), nullable=True)
    trailer = db.Column(db.String(100), nullable=True)
    trailer_temp1 = db.Column(db.String(50), nullable=True)
    trailer_temp2 = db.Column(db.String(50), nullable=True)
    stores = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    door = db.relationship('Door', backref=db.backref('detail', uselist=False))

class NewDoor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    door_number = db.Column(db.String(50), nullable=False)
    trailer_number = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db():
    with app.app_context():
        db.create_all()
        if Door.query.count() == 0:
            for i in range(1, 51):
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
                'stores': detail.stores,
                'notes': detail.notes
            })
        return jsonify({'door_id': door_id}), 200

    # POST - create or update
    data = request.get_json() or {}
    run_number = data.get('run_number')
    loader = data.get('loader')
    trailer = data.get('trailer')
    stores = data.get('stores')
    notes = data.get('notes')

    detail = DoorDetail.query.filter_by(door_id=door_id).first()
    if not detail:
        detail = DoorDetail(
            door_id=door_id, 
            run_number=run_number, 
            loader=loader, 
            trailer=trailer,
            stores=stores,
            notes=notes
        )
        db.session.add(detail)
    else:
        detail.run_number = run_number
        detail.loader = loader
        detail.trailer = trailer
        detail.stores = stores
        detail.notes = notes

    db.session.commit()
    
    emit_payload = {
        'door_id': door_id,
        'run_number': run_number,
        'loader': loader,
        'trailer': trailer,
        'stores': stores,
        'notes': notes
    }
    socketio.emit('door_details', emit_payload)
    return jsonify(emit_payload), 200

@app.route('/new_doors_ui')
def new_doors_ui():
    return render_template('new_doors.html')

@app.route('/api/status_counts', methods=['GET'])
def status_counts():
    doors = Door.query.all()
    counts = {}
    for door in doors:
        status = door.status
        counts[status] = counts.get(status, 0) + 1
    return jsonify(counts)

@app.route('/api/reset_all', methods=['POST'])
def reset_all():
    """Reset all doors to Empty status"""
    doors = Door.query.all()
    for door in doors:
        door.status = 'Empty'
    db.session.commit()
    for door in doors:
        socketio.emit('status_updated', {'door_id': door.id, 'status': door.status})
    return jsonify({'reset': True, 'count': len(doors)}), 200

@app.route('/api/clear_all_data', methods=['POST'])
def clear_all_data():
    """Clear all door details and reset statuses to Empty"""
    # Delete all door details
    DoorDetail.query.delete()
    
    # Reset all doors to Empty
    doors = Door.query.all()
    for door in doors:
        door.status = 'Empty'
    
    db.session.commit()
    
    # Emit updates to all clients
    for door in doors:
        socketio.emit('status_updated', {
            'door_id': door.id, 
            'status': door.status,
            'run_number': None,
            'stores': None,
            'loader': None,
            'trailer': None,
            
            'notes': None
        })
    
    return jsonify({'cleared': True, 'count': len(doors)}), 200

@app.route('/api/new_doors', methods=['GET'])
def get_new_doors():
    """Return all current NEW DOORS entries."""
    new_doors = NewDoor.query.order_by(NewDoor.created_at.asc()).all()
    return jsonify([
        {
            'id': nd.id,
            'door_number': nd.door_number,
            'trailer_number': nd.trailer_number,
        }
        for nd in new_doors
    ])


@app.route('/api/new_doors', methods=['POST'])
def create_new_door():
    """Create a new entry in NEW DOORS."""
    data = request.get_json() or {}
    door_number = (data.get('door_number') or '').strip()
    trailer_number = (data.get('trailer_number') or '').strip()

    if not door_number or not trailer_number:
        return jsonify({'error': 'door_number and trailer_number are required'}), 400

    nd = NewDoor(door_number=door_number, trailer_number=trailer_number)
    db.session.add(nd)
    db.session.commit()

    payload = {
        'id': nd.id,
        'door_number': nd.door_number,
        'trailer_number': nd.trailer_number,
    }

    # Broadcast to all connected clients
    socketio.emit('new_door_added', payload, broadcast=True)

    return jsonify(payload), 201


@app.route('/api/new_doors/<int:new_door_id>', methods=['DELETE'])
def delete_new_door(new_door_id):
    """Delete a NEW DOORS entry."""
    nd = NewDoor.query.get(new_door_id)
    if not nd:
        return jsonify({'error': 'not found'}), 404

    db.session.delete(nd)
    db.session.commit()

    # Broadcast deletion
    socketio.emit('new_door_removed', {'id': new_door_id}, broadcast=True)

    return jsonify({'deleted': True, 'id': new_door_id}), 200

@app.route('/api/export_pdf', methods=['GET'])
def export_pdf():
    """Export all door data to PDF"""
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), 
                           rightMargin=10, leftMargin=10,
                           topMargin=30, bottomMargin=18)
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=25,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=1  # Center
    )
    
    # Title
    title = Paragraph(f"Daily Load Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Get all doors with details
    doors = Door.query.order_by(Door.id).all()
    
    # Status summary
    status_counts = {}
    for door in doors:
        status_counts[door.status] = status_counts.get(door.status, 0) + 1
    
    summary_data = [
        ['Status Summary', 'Count'],
        ['Empty', status_counts.get('Empty', 0)],
        ['Loading', status_counts.get('Loading', 0)],
        ['Loaded', status_counts.get('Loaded', 0)],
        ['Backhaul', status_counts.get('Backhaul', 0)],
        ['Total Doors', len(doors)]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 16),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Detailed door information
    detail_title = Paragraph("Detailed Run Information", styles['Heading2'])
    elements.append(detail_title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Table headers
    data = [['Run', 'Status', 'Door #', 'Loader', 'Trailer', 'Stores', 'Notes']]
    
    # Add door data
    for door in doors:
        detail = door.detail
        notes_text = ''
        if detail and detail.notes:
            # Truncate long notes
            notes_text = detail.notes[:50] + '...' if len(detail.notes) > 50 else detail.notes
        
        row = [
            door.name,
            door.status,
            detail.run_number if detail else '',
            detail.loader if detail else '',
            detail.trailer if detail else '',
            detail.stores if detail else '',
            notes_text
        ]
        data.append(row)
    
    # Create table with adjusted column widths
    col_widths = [1*inch, 1*inch, 1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 2*inch]
    table = Table(data, colWidths=col_widths)
    
    # Define status colors
    status_colors = {
        'Empty': colors.HexColor("#952B16"),
        'Loading': colors.HexColor('#ecc94b'),
        'Loaded': colors.HexColor("#64953b"),
        'Backhaul': colors.HexColor("#193244")
    }
    
    # Apply table style
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 15),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    
    # Color code rows based on status
    for i, door in enumerate(doors, start=1):
        bg_color = status_colors.get(door.status, colors.white)
        table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
        # Add black text for better contrast on colored backgrounds
        table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.black))
    
    table.setStyle(TableStyle(table_style))
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    # Prepare file for download
    buffer.seek(0)
    filename = f"door_management_report_{datetime.now().strftime('%m%d%Y_%H%M%S')}.pdf"
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )
    
@app.route('/details')
def details_view():
    doors = Door.query.all()
    return render_template('details.html', doors=doors)

    


@socketio.on('update_status')
def on_update_status(data):
    door_id = data.get('door_id')
    new_status = data.get('status')
    door = Door.query.get(door_id)
    if door:
        door.status = new_status
        db.session.commit()
        detail = door.detail
        socketio.emit('status_updated', {
            'door_id': door.id,
            'status': door.status,
            'run_number': detail.run_number if detail else None,
            'stores': detail.stores if detail else None,
            'loader': detail.loader if detail else None,
            'trailer': detail.trailer if detail else None,
            'stores': detail.stores if detail else None,
            'notes': detail.notes if detail else None
        })
    
if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=8222, debug=True)

