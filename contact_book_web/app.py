import os
import re
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template

# SQLAlchemy database import
from flask_sqlalchemy import SQLAlchemy

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

# Database path setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'contacts.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-card-catalog-secret-key-1892'

db = SQLAlchemy(app)

# Database Model
class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    favorite = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone or '',
            'email': self.email or '',
            'address': self.address or '',
            'notes': self.notes or '',
            'favorite': self.favorite,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Validation Helpers
def validate_phone(phone):
    if not phone:
        return True
    # Loose regex: starts with optional '+', followed by 3-40 chars of numbers, spaces, hyphens, dots, parentheses
    pattern = re.compile(r'^\+?[\d\s\-()\.]{3,40}$')
    return bool(pattern.match(phone))

def validate_email(email):
    if not email:
        return True
    # Basic email format check
    pattern = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    return bool(pattern.match(email))

def validate_contact_data(data, is_patch=False):
    errors = []
    
    # Validate name
    if 'name' in data or not is_patch:
        name = data.get('name', '')
        if name is None or not str(name).strip():
            errors.append("Name is required.")
        elif len(str(name).strip()) > 120:
            errors.append("Name must not exceed 120 characters.")
            
    # Validate phone
    if 'phone' in data:
        phone = data.get('phone')
        if phone:
            phone_str = str(phone).strip()
            if phone_str:
                if len(phone_str) > 40:
                    errors.append("Phone number must not exceed 40 characters.")
                elif not validate_phone(phone_str):
                    errors.append("Invalid phone format. Allowed: digits, spaces, hyphens, dots, parentheses, optional leading '+'.")

    # Validate email
    if 'email' in data:
        email = data.get('email')
        if email:
            email_str = str(email).strip()
            if email_str:
                if len(email_str) > 160:
                    errors.append("Email address must not exceed 160 characters.")
                elif not validate_email(email_str):
                    errors.append("Invalid email address format.")

    # Validate address
    if 'address' in data:
        address = data.get('address')
        if address and len(str(address).strip()) > 300:
            errors.append("Address must not exceed 300 characters.")

    # Validate notes
    if 'notes' in data:
        notes = data.get('notes')
        if notes and len(str(notes)) > 2000:
            errors.append("Notes must not exceed 2000 characters.")

    return errors

# One-time migration function
def migrate_if_needed():
    try:
        if Contact.query.count() == 0:
            # Check standard path locations for CLI's contacts.json
            parent_json = os.path.join(basedir, '..', 'contacts.json')
            local_json = os.path.join(basedir, 'contacts.json')
            
            json_path = None
            if os.path.exists(parent_json):
                json_path = parent_json
            elif os.path.exists(local_json):
                json_path = local_json
                
            if json_path:
                app.logger.info(f"Empty database detected. Starting one-time migration from {json_path}")
                with open(json_path, 'r', encoding='utf-8') as f:
                    contacts_data = json.load(f)
                    if isinstance(contacts_data, list):
                        for item in contacts_data:
                            name = item.get('name', '').strip()
                            if not name:
                                continue
                            
                            # Check duplicates before importing
                            existing = Contact.query.filter(db.func.lower(Contact.name) == name.lower()).first()
                            if existing:
                                continue
                            
                            phone = item.get('phone', '').strip()
                            email = item.get('email', '').strip()
                            address = item.get('address', '').strip()
                            
                            contact = Contact(
                                name=name,
                                phone=phone if phone else None,
                                email=email if email else None,
                                address=address if address else None,
                                favorite=False
                            )
                            db.session.add(contact)
                        db.session.commit()
                        app.logger.info("Data migration completed successfully.")
    except Exception as e:
        app.logger.error(f"Migration error occurred: {str(e)}")

# API Routes
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    query_param = request.args.get('q', '').strip()
    sort_param = request.args.get('sort', 'name').strip()

    # Query builder
    query = Contact.query

    # Apply search filter across name, phone, email, address (case-insensitive)
    if query_param:
        search_filter = f"%{query_param}%"
        query = query.filter(
            Contact.name.ilike(search_filter) |
            Contact.phone.ilike(search_filter) |
            Contact.email.ilike(search_filter) |
            Contact.address.ilike(search_filter)
        )

    # Sort logic: Favorite status always comes first. Then sub-sorted by chosen option.
    if sort_param == 'recent':
        query = query.order_by(Contact.favorite.desc(), Contact.updated_at.desc())
    else:
        # Default alphabetical
        query = query.order_by(Contact.favorite.desc(), db.func.lower(Contact.name).asc())

    filtered_contacts = query.all()
    
    # Calculate list of uppercase letters having contacts in database overall
    all_contacts = Contact.query.all()
    initials = sorted(list(set(c.name[0].upper() for c in all_contacts if c.name)))

    return jsonify({
        'contacts': [c.to_dict() for c in filtered_contacts],
        'total_count': len(filtered_contacts),
        'initials': initials
    })

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    data = request.get_json() or {}
    
    errors = validate_contact_data(data, is_patch=False)
    if errors:
        return jsonify({"errors": errors}), 400

    name = data.get('name', '').strip()
    
    # Duplicate name check (case-insensitive)
    existing = Contact.query.filter(db.func.lower(Contact.name) == name.lower()).first()
    if existing:
        return jsonify({"errors": [f"A contact with the name '{name}' already exists."]}), 409

    phone = data.get('phone', '').strip() if data.get('phone') else None
    email = data.get('email', '').strip() if data.get('email') else None
    address = data.get('address', '').strip() if data.get('address') else None
    notes = data.get('notes', '').strip() if data.get('notes') else None
    favorite = bool(data.get('favorite', False))

    new_contact = Contact(
        name=name,
        phone=phone or None,
        email=email or None,
        address=address or None,
        notes=notes or None,
        favorite=favorite
    )

    db.session.add(new_contact)
    db.session.commit()

    return jsonify(new_contact.to_dict()), 201

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    return jsonify(contact.to_dict())

@app.route('/api/contacts/<int:contact_id>', methods=['PUT', 'PATCH'])
def update_contact(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404

    data = request.get_json() or {}
    is_patch = (request.method == 'PATCH')
    
    errors = validate_contact_data(data, is_patch=is_patch)
    if errors:
        return jsonify({"errors": errors}), 400

    # If updating name, check duplicates (excluding current contact)
    if 'name' in data:
        name = data.get('name', '').strip()
        existing = Contact.query.filter(db.func.lower(Contact.name) == name.lower(), Contact.id != contact_id).first()
        if existing:
            return jsonify({"errors": [f"A contact with the name '{name}' already exists."]}), 409
        contact.name = name

    if 'phone' in data:
        phone = data.get('phone', '').strip() if data.get('phone') else None
        contact.phone = phone or None

    if 'email' in data:
        email = data.get('email', '').strip() if data.get('email') else None
        contact.email = email or None

    if 'address' in data:
        address = data.get('address', '').strip() if data.get('address') else None
        contact.address = address or None

    if 'notes' in data:
        notes = data.get('notes', '').strip() if data.get('notes') else None
        contact.notes = notes or None

    if 'favorite' in data:
        contact.favorite = bool(data.get('favorite', False))

    # Explicitly update timestamp
    contact.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    return jsonify(contact.to_dict())

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact deleted successfully."})

@app.route('/api/contacts/<int:contact_id>/favorite', methods=['POST'])
def toggle_favorite(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    contact.favorite = not contact.favorite
    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify(contact.to_dict())

# Serving SPA
@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

# Global 404 fallback
@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith('/api/'):
        return jsonify({"errors": ["Resource not found."]}), 404
    # Fallback to SPA for frontend navigation routes
    return render_template("index.html")

# Initialize database and seed migrations
with app.app_context():
    db.create_all()
    migrate_if_needed()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
