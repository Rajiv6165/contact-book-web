import os
import re
import json
import csv
import io
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, make_response, redirect, url_for, session, g

# SQLAlchemy database import
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

# Database and Config setup
db_path = os.environ.get('DATABASE_URL') or os.environ.get('SQLITE_DB_PATH')
if db_path:
    if db_path.startswith('sqlite:///'):
        app.config['SQLALCHEMY_DATABASE_URI'] = db_path
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.abspath(db_path)
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'contacts.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-card-catalog-secret-key-1892')

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    contacts = db.relationship('Contact', backref='user', lazy=True)


class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
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
            'user_id': self.user_id,
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

# Dynamic Schema Migration Helper
def migrate_database_schema():
    try:
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('contacts')]
        if 'user_id' not in columns:
            app.logger.info("Schema migration: Adding user_id column to contacts table.")
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE contacts ADD COLUMN user_id INTEGER REFERENCES users(id)"))
    except Exception as e:
        app.logger.error(f"Error during schema migration: {e}")

# One-time migration function
def migrate_if_needed():
    try:
        basedir = os.path.abspath(os.path.dirname(__file__))
        
        # Check if we have contacts to import from JSON (if DB is completely empty)
        has_json_contacts = False
        json_contacts_data = []
        if Contact.query.count() == 0:
            parent_json = os.path.join(basedir, '..', 'contacts.json')
            local_json = os.path.join(basedir, 'contacts.json')
            
            json_path = parent_json if os.path.exists(parent_json) else (local_json if os.path.exists(local_json) else None)
            if json_path:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_contacts_data = json.load(f)
                    if isinstance(json_contacts_data, list) and len(json_contacts_data) > 0:
                        has_json_contacts = True

        # Check if there are any orphaned contacts (user_id is NULL)
        orphaned_contacts = Contact.query.filter(Contact.user_id.is_(None)).all()

        if orphaned_contacts or has_json_contacts:
            # We need to find or create the default user to assign contacts to
            default_user = User.query.first()
            if not default_user:
                username = os.environ.get('BASIC_AUTH_USERNAME') or 'admin'
                password = os.environ.get('BASIC_AUTH_PASSWORD') or 'adminpassword'
                email = f"{username}@example.com"
                
                default_user = User(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password)
                )
                db.session.add(default_user)
                db.session.commit()
                app.logger.info(f"Created default migration user: {username}")
                
            # Assign orphaned contacts to the default user
            if orphaned_contacts:
                for contact in orphaned_contacts:
                    contact.user_id = default_user.id
                db.session.commit()
                app.logger.info(f"Assigned {len(orphaned_contacts)} orphaned contacts to user '{default_user.username}'.")
                
            # Import JSON contacts if database was empty
            if has_json_contacts:
                app.logger.info("Empty database detected. Seeding contacts from JSON.")
                for item in json_contacts_data:
                    name = item.get('name', '').strip()
                    if not name:
                        continue
                    
                    # Duplicate check for this user
                    existing = Contact.query.filter_by(user_id=default_user.id).filter(db.func.lower(Contact.name) == name.lower()).first()
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
                        favorite=False,
                        user_id=default_user.id
                    )
                    db.session.add(contact)
                db.session.commit()
                app.logger.info("JSON seed completed successfully.")
    except Exception as e:
        app.logger.error(f"Migration error occurred: {str(e)}")

# Authentication Enforcement Hook
@app.before_request
def require_login():
    if request.path == '/health':
        return None
    if request.path.startswith('/static/'):
        return None
    if request.path in ('/login', '/register'):
        return None
        
    user_id = session.get('user_id')
    g.user = None
    if user_id:
        g.user = db.session.get(User, user_id)
        
    if g.user is None:
        if request.path.startswith('/api/'):
            return jsonify({"errors": ["Unauthorized. Please login."]}), 401
        return redirect(url_for('login'))
    return None

# Auth Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id') and db.session.get(User, session.get('user_id')):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        elif not validate_email(email):
            errors.append("Invalid email address format.")
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
            
        if not errors:
            existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing_user:
                if existing_user.username == username:
                    errors.append("Username is already taken.")
                if existing_user.email == email:
                    errors.append("Email is already registered.")
                    
        if errors:
            return render_template('register.html', errors=errors, username=username, email=email)
            
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login', registered='true'))
        
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id') and db.session.get(User, session.get('user_id')):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
            
        return render_template('login.html', error="Invalid username or password.")
        
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


# API Routes
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    query_param = request.args.get('q', '').strip()
    sort_param = request.args.get('sort', 'name').strip()

    # Query builder - scope by current user
    query = Contact.query.filter_by(user_id=g.user.id)

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
    
    # Calculate list of uppercase letters having contacts in database overall for the user
    all_contacts = Contact.query.filter_by(user_id=g.user.id).all()
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
    
    # Duplicate name check for this user (case-insensitive)
    existing = Contact.query.filter_by(user_id=g.user.id).filter(db.func.lower(Contact.name) == name.lower()).first()
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
        favorite=favorite,
        user_id=g.user.id
    )

    db.session.add(new_contact)
    db.session.commit()

    return jsonify(new_contact.to_dict()), 201

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    return jsonify(contact.to_dict())

@app.route('/api/contacts/<int:contact_id>', methods=['PUT', 'PATCH'])
def update_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).first()
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
        existing = Contact.query.filter(
            Contact.user_id == g.user.id,
            db.func.lower(Contact.name) == name.lower(),
            Contact.id != contact_id
        ).first()
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
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact deleted successfully."})

@app.route('/api/contacts/<int:contact_id>/favorite', methods=['POST'])
def toggle_favorite(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    contact.favorite = not contact.favorite
    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify(contact.to_dict())

@app.route('/api/contacts/export', methods=['GET'])
def export_contacts():
    try:
        contacts = Contact.query.filter_by(user_id=g.user.id).order_by(db.func.lower(Contact.name).asc()).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['name', 'phone', 'email', 'address', 'notes', 'favorite', 'created_at', 'updated_at'])
        
        for c in contacts:
            writer.writerow([
                c.name,
                c.phone or '',
                c.email or '',
                c.address or '',
                c.notes or '',
                'true' if c.favorite else 'false',
                c.created_at.isoformat() if c.created_at else '',
                c.updated_at.isoformat() if c.updated_at else ''
            ])
            
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=contacts.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    except Exception as e:
        app.logger.error(f"CSV export error: {str(e)}")
        return jsonify({"errors": [f"Export failed: {str(e)}"]}), 500

@app.route('/api/contacts/import', methods=['POST'])
def import_contacts():
    if 'file' not in request.files:
        return jsonify({"errors": ["No file part in the request."]}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"errors": ["No selected file."]}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({"errors": ["Invalid file type. Only CSV files are allowed."]}), 400

    imported_count = 0
    skipped_count = 0
    errors = []

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.reader(stream)
        
        header = next(reader, None)
        if not header:
            return jsonify({"errors": ["Empty CSV file."]}), 400
            
        header_map = {col.strip().lower(): idx for idx, col in enumerate(header)}
        
        if 'name' not in header_map:
            return jsonify({"errors": ["CSV file must contain a 'name' column."]}), 400

        for row_idx, row in enumerate(reader, start=2):
            if not row or all(val.strip() == '' for val in row):
                continue
                
            def get_val(col_name):
                idx = header_map.get(col_name)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return ''

            name = get_val('name')
            if not name:
                errors.append(f"Row {row_idx}: Name is required.")
                continue

            if len(name) > 120:
                errors.append(f"Row {row_idx} ({name}): Name exceeds 120 characters.")
                continue

            existing = Contact.query.filter_by(user_id=g.user.id).filter(db.func.lower(Contact.name) == name.lower()).first()
            if existing:
                skipped_count += 1
                continue

            phone = get_val('phone')
            if phone and len(phone) > 40:
                errors.append(f"Row {row_idx} ({name}): Phone number exceeds 40 characters.")
                continue
            if phone and not validate_phone(phone):
                errors.append(f"Row {row_idx} ({name}): Phone number format is invalid.")
                continue

            email = get_val('email')
            if email and len(email) > 160:
                errors.append(f"Row {row_idx} ({name}): Email address exceeds 160 characters.")
                continue
            if email and not validate_email(email):
                errors.append(f"Row {row_idx} ({name}): Email address format is invalid.")
                continue

            address = get_val('address')
            if address and len(address) > 300:
                errors.append(f"Row {row_idx} ({name}): Address exceeds 300 characters.")
                continue

            notes = get_val('notes')
            if notes and len(notes) > 2000:
                errors.append(f"Row {row_idx} ({name}): Notes exceed 2000 characters.")
                continue

            fav_val = get_val('favorite').lower()
            favorite = fav_val in ['1', 'true', 'yes', 'y']

            new_contact = Contact(
                name=name,
                phone=phone if phone else None,
                email=email if email else None,
                address=address if address else None,
                notes=notes if notes else None,
                favorite=favorite,
                user_id=g.user.id
            )
            db.session.add(new_contact)
            imported_count += 1
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"errors": [f"Failed to process CSV file: {str(e)}"]}), 500

    return jsonify({
        "imported": imported_count,
        "skipped": skipped_count,
        "errors": errors
    })

# Serving SPA
@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

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
    migrate_database_schema()
    migrate_if_needed()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
