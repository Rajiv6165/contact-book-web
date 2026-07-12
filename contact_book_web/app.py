import os
import re
import json
import csv
import io
import uuid
import base64
from datetime import datetime, timezone, date, timedelta
from flask import Flask, request, jsonify, render_template, make_response, redirect, url_for, session, g, send_from_directory

# SQLAlchemy database import
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

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

# Avatar Upload Folder Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_url = os.environ.get('SQLITE_DB_PATH') or os.environ.get('DATABASE_URL')
if db_url and not db_url.startswith('sqlite:///'):
    persistent_dir = os.path.dirname(os.path.abspath(db_url))
    AVATAR_UPLOAD_FOLDER = os.path.join(persistent_dir, 'avatars')
elif os.path.exists('/data'):
    AVATAR_UPLOAD_FOLDER = '/data/avatars'
else:
    AVATAR_UPLOAD_FOLDER = os.path.join(basedir, 'static', 'avatars')

# Ensure directories exist
os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)

# Custom static route to serve avatars from persistent directories
@app.route('/static/avatars/<filename>')
def serve_avatar(filename):
    return send_from_directory(AVATAR_UPLOAD_FOLDER, filename)

# Fixed desaturated vintage color palette for index cards tags
TAG_PALETTE = [
    '#8F9E8B',  # Sage Green
    '#D9A74A',  # Mustard Yellow
    '#C86A5A',  # Terracotta
    '#7A90A4',  # Dusty Blue
    '#967D91',  # Vintage Violet
    '#5C5A55'   # Graphite
]

# Database Models
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    contacts = db.relationship('Contact', backref='user', lazy=True)


# Association Table for Many-to-Many Contacts and Tags
contact_tags = db.Table('contact_tags',
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)


class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uix_user_id_tag_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color
        }


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
    birthday = db.Column(db.Date, nullable=True)
    avatar_url = db.Column(db.String(300), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tags = db.relationship('Tag', secondary=contact_tags, backref=db.backref('contacts', lazy='dynamic'))

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
            'birthday': self.birthday.strftime('%Y-%m-%d') if self.birthday else None,
            'avatar_url': self.avatar_url,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'tags': [t.to_dict() for t in self.tags],
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

    # Validate birthday
    if 'birthday' in data:
        birthday = data.get('birthday')
        if birthday:
            try:
                datetime.strptime(str(birthday).strip(), '%Y-%m-%d')
            except ValueError:
                errors.append("Invalid birthday format. Expected YYYY-MM-DD.")

    return errors

# Dynamic Schema Migration Helper
def migrate_database_schema():
    try:
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('contacts')]
        if 'birthday' not in columns:
            app.logger.info("Schema migration: Adding birthday column to contacts table.")
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE contacts ADD COLUMN birthday DATE"))
                
        # Inspect columns list to check avatar_url
        columns = [c['name'] for c in inspector.get_columns('contacts')]
        if 'avatar_url' not in columns:
            app.logger.info("Schema migration: Adding avatar_url column to contacts table.")
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE contacts ADD COLUMN avatar_url VARCHAR(300)"))
                
        # Inspect columns list to check deleted_at (soft delete support)
        columns = [c['name'] for c in inspector.get_columns('contacts')]
        if 'deleted_at' not in columns:
            app.logger.info("Schema migration: Adding deleted_at column to contacts table.")
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE contacts ADD COLUMN deleted_at DATETIME"))
    except Exception as e:
        app.logger.error(f"Error during schema migration: {e}")

# Helper to calculate upcoming birthdays in next 30 days
def calculate_upcoming_birthdays(user_id):
    today = date.today()
    upcoming = []
    
    # Query non-deleted contacts with birthdays belonging to the user
    contacts = Contact.query.filter(Contact.user_id == user_id, Contact.deleted_at.is_(None), Contact.birthday.isnot(None)).all()
    
    for c in contacts:
        bdate = c.birthday
        # Calculate birthday in the current year
        try:
            this_year_birthday = bdate.replace(year=today.year)
        except ValueError:
            # Handle Feb 29 on non-leap years
            this_year_birthday = bdate.replace(year=today.year, day=28)
            
        if this_year_birthday < today:
            try:
                next_birthday = this_year_birthday.replace(year=today.year + 1)
            except ValueError:
                # Handle Feb 29
                next_birthday = this_year_birthday.replace(year=today.year + 1, day=28)
        else:
            next_birthday = this_year_birthday
            
        days_until = (next_birthday - today).days
        if 0 <= days_until <= 30:
            upcoming.append((c, days_until))
            
    upcoming.sort(key=lambda x: x[1])
    return [c.to_dict() for c, days in upcoming]

# Helper to delete avatar file from disk
def delete_avatar_file(avatar_url):
    if not avatar_url:
        return
    prefix = '/static/avatars/'
    if avatar_url.startswith(prefix):
        filename = avatar_url[len(prefix):]
        file_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                app.logger.info(f"Deleted avatar file: {file_path}")
            except Exception as e:
                app.logger.error(f"Error deleting avatar file {file_path}: {e}")

# Auto-purge function for contacts soft-deleted for more than 30 days
def purge_old_deleted_contacts():
    try:
        with app.app_context():
            # SQLite does not strictly enforce timezone math but comparison is supported
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            old_deleted = Contact.query.filter(
                Contact.deleted_at.isnot(None),
                Contact.deleted_at < thirty_days_ago
            ).all()
            count = len(old_deleted)
            for c in old_deleted:
                if c.avatar_url:
                    delete_avatar_file(c.avatar_url)
                db.session.delete(c)
            db.session.commit()
            if count > 0:
                app.logger.info(f"Auto-purged {count} trashed contacts older than 30 days.")
    except Exception as e:
        app.logger.error(f"Error during auto-purge: {e}")

# Standard vCard 3.0 Generation Helper
def generate_vcard_content(contacts):
    lines = []
    for contact in contacts:
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        lines.append(f"FN:{contact.name}")
        
        if contact.phone:
            lines.append(f"TEL;TYPE=CELL:{contact.phone}")
        if contact.email:
            lines.append(f"EMAIL;TYPE=INTERNET:{contact.email}")
        if contact.address:
            escaped_address = contact.address.replace(';', '\\;')
            lines.append(f"ADR;TYPE=HOME:;;{escaped_address};;;;")
        if contact.birthday:
            lines.append(f"BDAY:{contact.birthday.strftime('%Y-%m-%d')}")
            
        if contact.avatar_url:
            prefix = '/static/avatars/'
            if contact.avatar_url.startswith(prefix):
                filename = contact.avatar_url[len(prefix):]
                file_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'rb') as f:
                            encoded = base64.b64encode(f.read()).decode('utf-8')
                        ext = os.path.splitext(filename)[1].lower()
                        img_type = "JPEG" if ext in ['.jpg', '.jpeg'] else ext[1:].upper()
                        lines.append(f"PHOTO;TYPE={img_type};ENCODING=b:{encoded}")
                    except Exception as e:
                        app.logger.error(f"Error encoding photo for vcard: {e}")
                        
        lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"

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
                
            if orphaned_contacts:
                for contact in orphaned_contacts:
                    contact.user_id = default_user.id
                db.session.commit()
                app.logger.info(f"Assigned {len(orphaned_contacts)} orphaned contacts to user '{default_user.username}'.")
                
            if has_json_contacts:
                app.logger.info("Empty database detected. Seeding contacts from JSON.")
                for item in json_contacts_data:
                    name = item.get('name', '').strip()
                    if not name:
                        continue
                    
                    # Duplicate check for this user (excluding deleted ones)
                    existing = Contact.query.filter_by(user_id=default_user.id).filter(Contact.deleted_at.is_(None)).filter(db.func.lower(Contact.name) == name.lower()).first()
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
@app.route('/api/tags', methods=['GET'])
def get_tags():
    tags = Tag.query.filter_by(user_id=g.user.id).order_by(Tag.name.asc()).all()
    return jsonify({'tags': [t.to_dict() for t in tags]})

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    query_param = request.args.get('q', '').strip()
    sort_param = request.args.get('sort', 'name').strip()
    tag_param = request.args.get('tag', '').strip()

    # Query builder - scope by current user and exclude soft-deleted ones
    query = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None))

    # Filter by tag
    if tag_param:
        query = query.filter(Contact.tags.any(Tag.name == tag_param))

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
        query = query.order_by(Contact.favorite.desc(), db.func.lower(Contact.name).asc())

    filtered_contacts = query.all()
    
    # Calculate list of uppercase letters having contacts in database overall for the user
    all_contacts = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None)).all()
    initials = sorted(list(set(c.name[0].upper() for c in all_contacts if c.name)))
    upcoming_birthdays = calculate_upcoming_birthdays(g.user.id)
    
    # Calculate soft deleted trash count
    trash_count = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.isnot(None)).count()

    return jsonify({
        'contacts': [c.to_dict() for c in filtered_contacts],
        'total_count': len(filtered_contacts),
        'initials': initials,
        'upcoming_birthdays': upcoming_birthdays,
        'trash_count': trash_count
    })

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    data = request.get_json() or {}
    
    errors = validate_contact_data(data, is_patch=False)
    if errors:
        return jsonify({"errors": errors}), 400

    name = data.get('name', '').strip()
    
    # Duplicate name check for this user (excluding deleted ones)
    existing = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None)).filter(db.func.lower(Contact.name) == name.lower()).first()
    if existing:
        return jsonify({"errors": [f"A contact with the name '{name}' already exists."]}), 409

    phone = data.get('phone', '').strip() if data.get('phone') else None
    email = data.get('email', '').strip() if data.get('email') else None
    address = data.get('address', '').strip() if data.get('address') else None
    notes = data.get('notes', '').strip() if data.get('notes') else None
    favorite = bool(data.get('favorite', False))

    birthday = None
    if 'birthday' in data:
        bday_str = data.get('birthday')
        if bday_str:
            birthday = datetime.strptime(str(bday_str).strip(), '%Y-%m-%d').date()

    # Process tags (deduplicated)
    assigned_tags = []
    if 'tags' in data:
        tag_list = data.get('tags', [])
        seen = set()
        dedup_tags = []
        for x in tag_list:
            x_str = str(x).strip()
            if x_str and x_str.lower() not in seen:
                seen.add(x_str.lower())
                dedup_tags.append(x_str)
                
        for tname in dedup_tags:
            tag = Tag.query.filter_by(user_id=g.user.id, name=tname).first()
            if not tag:
                existing_count = Tag.query.filter_by(user_id=g.user.id).count()
                color = TAG_PALETTE[existing_count % len(TAG_PALETTE)]
                tag = Tag(user_id=g.user.id, name=tname, color=color)
                db.session.add(tag)
                db.session.commit()
            assigned_tags.append(tag)

    new_contact = Contact(
        name=name,
        phone=phone or None,
        email=email or None,
        address=address or None,
        notes=notes or None,
        favorite=favorite,
        user_id=g.user.id,
        birthday=birthday
    )
    new_contact.tags = assigned_tags

    db.session.add(new_contact)
    db.session.commit()

    return jsonify(new_contact.to_dict()), 201

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    return jsonify(contact.to_dict())

@app.route('/api/contacts/<int:contact_id>', methods=['PUT', 'PATCH'])
def update_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404

    data = request.get_json() or {}
    is_patch = (request.method == 'PATCH')
    
    errors = validate_contact_data(data, is_patch=is_patch)
    if errors:
        return jsonify({"errors": errors}), 400

    # If updating name, check duplicates (excluding current contact and deleted contacts)
    if 'name' in data:
        name = data.get('name', '').strip()
        existing = Contact.query.filter(
            Contact.user_id == g.user.id,
            Contact.deleted_at.is_(None),
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

    if 'birthday' in data:
        bday_str = data.get('birthday')
        if bday_str:
            contact.birthday = datetime.strptime(str(bday_str).strip(), '%Y-%m-%d').date()
        else:
            contact.birthday = None

    if 'tags' in data:
        assigned_tags = []
        tag_list = data.get('tags', [])
        seen = set()
        dedup_tags = []
        for x in tag_list:
            x_str = str(x).strip()
            if x_str and x_str.lower() not in seen:
                seen.add(x_str.lower())
                dedup_tags.append(x_str)
                
        for tname in dedup_tags:
            tag = Tag.query.filter_by(user_id=g.user.id, name=tname).first()
            if not tag:
                existing_count = Tag.query.filter_by(user_id=g.user.id).count()
                color = TAG_PALETTE[existing_count % len(TAG_PALETTE)]
                tag = Tag(user_id=g.user.id, name=tname, color=color)
                db.session.add(tag)
                db.session.commit()
            assigned_tags.append(tag)
        contact.tags = assigned_tags

    # Explicitly update timestamp
    contact.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    return jsonify(contact.to_dict())

# Soft delete route (moves to trash)
@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
    
    contact.deleted_at = datetime.now(timezone.utc)
    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Contact moved to Trash.", "id": contact.id})

# Toggle pin status
@app.route('/api/contacts/<int:contact_id>/favorite', methods=['POST'])
def toggle_favorite(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    contact.favorite = not contact.favorite
    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify(contact.to_dict())

# Soft delete bulk contacts route
@app.route('/api/contacts/bulk-delete', methods=['POST'])
def bulk_delete_contacts():
    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"errors": ["No contact IDs provided."]}), 400
        
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.user_id == g.user.id).filter(Contact.deleted_at.is_(None)).all()
    count = len(contacts)
    for c in contacts:
        c.deleted_at = datetime.now(timezone.utc)
        c.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({"message": f"Successfully moved {count} contacts to Trash."})

# Bulk tag route
@app.route('/api/contacts/bulk-tag', methods=['POST'])
def bulk_tag_contacts():
    data = request.get_json() or {}
    ids = data.get('ids', [])
    tname = str(data.get('tag', '')).strip()
    
    if not ids:
        return jsonify({"errors": ["No contact IDs provided."]}), 400
    if not tname:
        return jsonify({"errors": ["Tag name is required."]}), 400
        
    tag = Tag.query.filter_by(user_id=g.user.id, name=tname).first()
    if not tag:
        existing_count = Tag.query.filter_by(user_id=g.user.id).count()
        color = TAG_PALETTE[existing_count % len(TAG_PALETTE)]
        tag = Tag(user_id=g.user.id, name=tname, color=color)
        db.session.add(tag)
        db.session.commit()
        
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.user_id == g.user.id).filter(Contact.deleted_at.is_(None)).all()
    count = 0
    for c in contacts:
        if tag not in c.tags:
            c.tags.append(tag)
            count += 1
    db.session.commit()
    
    return jsonify({"message": f"Successfully added tag '{tname}' to {count} contacts."})

# CSV export route
@app.route('/api/contacts/export', methods=['GET'])
def export_contacts():
    try:
        query = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None))
        
        ids_param = request.args.get('ids', '').strip()
        if ids_param:
            ids = [int(x) for x in ids_param.split(',') if x.isdigit()]
            query = query.filter(Contact.id.in_(ids))

        contacts = query.order_by(db.func.lower(Contact.name).asc()).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['name', 'phone', 'email', 'address', 'notes', 'favorite', 'birthday', 'tags', 'created_at', 'updated_at'])
        
        for c in contacts:
            tags_str = ','.join([t.name for t in c.tags])
            writer.writerow([
                c.name,
                c.phone or '',
                c.email or '',
                c.address or '',
                c.notes or '',
                'true' if c.favorite else 'false',
                c.birthday.isoformat() if c.birthday else '',
                tags_str,
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

# vCard Export Endpoint (Single Contact)
@app.route('/api/contacts/<int:contact_id>/vcard', methods=['GET'])
def export_single_vcard(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    vcard_text = generate_vcard_content([contact])
    response = make_response(vcard_text)
    safe_name = "".join([c for c in contact.name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_name = safe_name.replace(' ', '_') or 'contact'
    response.headers["Content-Disposition"] = f"attachment; filename={safe_name}.vcf"
    response.headers["Content-Type"] = "text/vcard"
    return response

# vCard Export Endpoint (All or bulk select)
@app.route('/api/contacts/vcard/export', methods=['GET'])
def export_bulk_vcard():
    try:
        query = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None))
        
        ids_param = request.args.get('ids', '').strip()
        if ids_param:
            ids = [int(x) for x in ids_param.split(',') if x.isdigit()]
            query = query.filter(Contact.id.in_(ids))
            
        contacts = query.order_by(db.func.lower(Contact.name).asc()).all()
        
        vcard_text = generate_vcard_content(contacts)
        response = make_response(vcard_text)
        response.headers["Content-Disposition"] = "attachment; filename=contacts.vcf"
        response.headers["Content-Type"] = "text/vcard"
        return response
    except Exception as e:
        app.logger.error(f"vCard export error: {str(e)}")
        return jsonify({"errors": [f"Export failed: {str(e)}"]}), 500

# Soft-deleted trash contacts list route
@app.route('/api/contacts/trash', methods=['GET'])
def get_trash_contacts():
    contacts = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.isnot(None)).order_by(Contact.deleted_at.desc()).all()
    return jsonify({
        'contacts': [c.to_dict() for c in contacts],
        'total_count': len(contacts)
    })

# Restore soft-deleted contact
@app.route('/api/contacts/<int:contact_id>/restore', methods=['POST'])
def restore_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.isnot(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found in trash."]}), 404
        
    contact.deleted_at = None
    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(contact.to_dict()), 200

# Permanent Delete endpoint (hard delete + disk photo cleanup)
@app.route('/api/contacts/<int:contact_id>/permanent', methods=['DELETE'])
def permanent_delete_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.isnot(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found in trash."]}), 404
        
    if contact.avatar_url:
        delete_avatar_file(contact.avatar_url)
        
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact permanently deleted."}), 200

# CSV import route
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

            # Duplicate name check excludes deleted contacts
            existing = Contact.query.filter_by(user_id=g.user.id).filter(Contact.deleted_at.is_(None)).filter(db.func.lower(Contact.name) == name.lower()).first()
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

            # Parse birthday
            birthday_str = get_val('birthday')
            birthday = None
            if birthday_str:
                try:
                    birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Parse tags
            imported_tags = []
            tags_val = get_val('tags')
            if tags_val:
                tag_names = [t.strip() for t in tags_val.split(',') if t.strip()]
                for tname in tag_names:
                    tag = Tag.query.filter_by(user_id=g.user.id, name=tname).first()
                    if not tag:
                        existing_count = Tag.query.filter_by(user_id=g.user.id).count()
                        color = TAG_PALETTE[existing_count % len(TAG_PALETTE)]
                        tag = Tag(user_id=g.user.id, name=tname, color=color)
                        db.session.add(tag)
                        db.session.commit()
                    imported_tags.append(tag)

            new_contact = Contact(
                name=name,
                phone=phone if phone else None,
                email=email if email else None,
                address=address if address else None,
                notes=notes if notes else None,
                favorite=favorite,
                birthday=birthday,
                user_id=g.user.id
            )
            new_contact.tags = imported_tags
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

# Custom avatar upload/delete endpoints
@app.route('/api/contacts/<int:contact_id>/avatar', methods=['POST'])
def upload_avatar(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    if 'file' not in request.files:
        return jsonify({"errors": ["No file part in the request."]}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"errors": ["No selected file."]}), 400
        
    ext = os.path.splitext(filename)[1].lower() if 'filename' in locals() else os.path.splitext(file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        return jsonify({"errors": ["Invalid file type. Only JPG, PNG, and WEBP are allowed."]}), 400
        
    try:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 3 * 1024 * 1024:
            return jsonify({"errors": ["File size exceeds 3MB limit."]}), 400
    except Exception as e:
        return jsonify({"errors": [f"Error checking file size: {e}"]}), 400
        
    try:
        img = Image.open(file.stream)
        if ext in ['.jpg', '.jpeg'] and img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
            
        img.thumbnail((400, 400))
        unique_hash = uuid.uuid4().hex[:8]
        sanitized_ext = '.jpg' if ext in ['.jpg', '.jpeg'] else ext
        new_filename = f"avatar_{contact_id}_{unique_hash}{sanitized_ext}"
        
        os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)
        save_path = os.path.join(AVATAR_UPLOAD_FOLDER, new_filename)
        img.save(save_path)
        
        old_avatar = contact.avatar_url
        if old_avatar:
            delete_avatar_file(old_avatar)
            
        contact.avatar_url = f"/static/avatars/{new_filename}"
        contact.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify(contact.to_dict()), 200
    except Exception as e:
        app.logger.error(f"Image processing failed: {e}")
        return jsonify({"errors": [f"Image processing failed: {str(e)}"]}), 500


@app.route('/api/contacts/<int:contact_id>/avatar', methods=['DELETE'])
def remove_avatar(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=g.user.id).filter(Contact.deleted_at.is_(None)).first()
    if not contact:
        return jsonify({"errors": ["Contact not found."]}), 404
        
    if contact.avatar_url:
        delete_avatar_file(contact.avatar_url)
        contact.avatar_url = None
        contact.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
    return jsonify(contact.to_dict()), 200

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
    return render_template("index.html")

# Initialize database and migrations
with app.app_context():
    db.create_all()
    migrate_database_schema()
    migrate_if_needed()
    purge_old_deleted_contacts()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
