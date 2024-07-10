import os
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import json
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='../frontend/templates')
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['JWT_SECRET_KEY'] = 'jwt_secret_key_here'

app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
jwt = JWTManager(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(60), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    active = db.Column(db.Boolean, nullable=False, default=True)
    loans = db.relationship('Loan', backref='user', lazy=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(60), nullable=False)
    author = db.Column(db.String(60), nullable=False)
    publication_year = db.Column(db.Integer, nullable=False)
    category = db.Column(db.Integer, nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    image_filename = db.Column(db.String(300), nullable=True)
    loans = db.relationship('Loan', backref='book', lazy=True)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    loan_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    

def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        if not user or user.role != 'admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_user():
    full_name = data.get('full_name')
    role = data.get('role', 'user')
    password = data.get('password')
    email = data.get('email')
    age = data.get('age')
    data = request.get_json()
    admin_password = data.get('admin_password')
    

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400

    if role == 'admin' and admin_password != '7732/16':
        return jsonify({'message': 'Invalid admin password'}), 403

    password_hash = generate_password_hash(password)
    new_user = User(email=email, password_hash=password_hash, full_name=full_name, age=age, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=email)
    return jsonify({'access_token': access_token}), 200

@app.route('/customers')
def customers():
    return render_template('customers.html')


@app.route('/add_book', methods=['POST'])
@jwt_required()
@admin_only
def add_book():
    data = request.form.get('data')

    if not data:
        return jsonify({"message": "Invalid data"}), 400

    try:
        data = json.loads(data)
    except ValueError:
        return jsonify({"message": "Invalid JSON"}), 400

    if 'title' not in data or 'author' not in data or 'publication_year' not in data or 'category' not in data:
        return jsonify({"message": "Missing data"}), 400

    title = data.get('title')
    author = data.get('author')
    publication_year = data.get('publication_year')
    category = data.get('category')

    existing_book = Book.query.filter_by(title=title, author=author, publication_year=publication_year).first()
    if existing_book:
        if existing_book.active:
            return jsonify({'message': 'Book already exists'}), 400
        else:
            existing_book.active = True
            db.session.commit()
            return jsonify({'message': 'Book reactivated successfully'}), 200

    image = request.files.get('image')
    if image and is_allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        filename = 'default.jpeg'

    new_book = Book(
        title=title,
        author=author,
        publication_year=publication_year,
        category=category,
        image_filename=filename
    )
    db.session.add(new_book)
    db.session.commit()

    return jsonify({'message': 'Book added successfully'}), 201

@app.route('/loan_book/<int:book_id>', methods=['POST'])
@jwt_required()
def loan_book(book_id):
    current_user_email = get_jwt_identity()
    book = Book.query.get(book_id)
    user = User.query.filter_by(email=current_user_email).first()

    if not book:
        return jsonify({'message': 'Book not found'}), 404

    if not book.is_available:
        return jsonify({'message': 'Book is not available'}), 400

    if not book.active:
        return jsonify({'message': 'Book is not active'}), 400

    loan_date = datetime.utcnow()
    return_date = loan_date + timedelta(days=10) if book.category == 1 else loan_date + timedelta(days=30)

    loan = Loan(user_id=user.id, book_id=book.id, loan_date=loan_date, return_date=return_date)
    db.session.add(loan)
    db.session.commit()

    book.is_available = False
    db.session.commit()

    return jsonify({'message': 'Book loaned successfully', 'return_date': return_date.strftime('%Y-%m-%d')}), 201

@app.route('/returns/<int:loan_id>', methods=['POST'])
@jwt_required()
def return_book(loan_id):
    current_user_email = get_jwt_identity()
    user = User.query.filter_by(email=current_user_email).first()

    loan = Loan.query.filter_by(id=loan_id, active=True).first()

    if not loan:
        return jsonify({'message': 'Active loan entry not found'}), 404

    if loan.user_id != user.id:
        return jsonify({'message': 'You did not loan this book'}), 403

    book = Book.query.get(loan.book_id)

    if not book:
        return jsonify({'message': 'Book not found'}), 404

    loan.active = False
    book.is_available = True
    db.session.commit()

    return jsonify({'message': 'Book returned successfully'}), 200

@app.route('/delete_book/<int:book_id>', methods=['DELETE'])
@jwt_required()
@admin_only
def delete_book(book_id):
    book = Book.query.get(book_id)

    if not book:
        return jsonify({'message': 'Book not found'}), 404

    book.active = False
    db.session.commit()

    return jsonify({'message': 'Book deleted successfully'}), 200

@app.route('/books', methods=['GET'])
def get_books():
    books = Book.query.filter_by(active=True).all()
    book_list = [{'id': book.id, 'title': book.title, 'author': book.author, 'publication_year': book.publication_year, 'category': book.category, 'is_available': book.is_available} for book in books]
    return jsonify(book_list), 200

@app.route('/uploads/<filename>', methods=['GET'])
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/users', methods=['GET'])
@jwt_required()
@admin_only
def get_users():
    users = User.query.all()
    user_list = [{'id': user.id, 'email': user.email, 'full_name': user.full_name, 'age': user.age, 'role': user.role, 'active': user.active} for user in users]
    return jsonify(user_list), 200

with app.app_context():
    db.create_all()



if __name__ == '__main__':
    app.run(debug=True)
