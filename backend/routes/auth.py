from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from ..models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    
    if user and check_password_hash(user.password_hash, data['password']):
        login_user(user)
        return jsonify({
            'message': 'Logged in successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role
            }
        })
    
    return jsonify({'message': 'Invalid credentials'}), 401

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'})

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
    
    user = User(
        email=data['email'],
        username=data['username'],
        password_hash=generate_password_hash(data['password']),
        role=data.get('role', 'customer')
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role
        }
    })
