from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db

bp = Blueprint('dev', __name__, url_prefix='/dev')

@bp.route('/ack', methods=['GET'])
def ack():
    requester = request.remote_addr
    print(f"http request received from: {requester}")

    response = {
        'message': 'ACK'
    }
    return jsonify(response)

@bp.route('/signup', methods=['POST'])
def signup():
    # Get JSON data from request
    data = request.json
    
    # Retrieve individual fields from JSON data
    name = data.get('name')
    surname = data.get('surname')
    phone_number = data.get('phone_number')
    # date_birth = data.get('date_birth')  # Commented out
    # gender = data.get('gender')          # Commented out
    email = data.get('email')
    password = data.get('password')

    # Print each field
    print(f"Name: {name}")
    print(f"Surname: {surname}")
    print(f"Phone Number: {phone_number}")
    # print(f"Date of Birth: {date_birth}")  # Commented out
    # print(f"Gender: {gender}")            # Commented out
    print(f"Email: {email}")
    print(f"Password: {password}")

    # Connect to the database
    #connection = db.getdb()
    try:
        #cursor = connection.cursor()

        # Hash the password
        hashed_password = password  # Ideally, you should hash the password before storing it
        
        # Execute the query
        # Uncomment and use a proper query for inserting data into your database
        # cursor.execute("INSERT INTO users (name, surname, phone_number, date_birth, gender, email, password) VALUES (%s, %s, %s, %s, %s, %s, %s)", (name, surname, phone_number, date_birth, gender, email, hashed_password))
        
        # Commit the transaction
        # connection.commit()

        # Return success response
        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        # Return error response in case of an exception
        return jsonify({'error': str(e)}), 500
    
# Define a default user for testing
DEFAULT_USER = {
    'id': 1,
    'email': 'test@example.com',
    'name': 'Test User',
    'password': 'test'  # Assuming you have the hash
}

@bp.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    
    # For debugging, bypass the database logic
    # Check if the email and password match the default user
    if email == DEFAULT_USER['email'] and password==DEFAULT_USER['password']:
        response = {
            'status': 'SUCCESS',
            'id': DEFAULT_USER['id'],
            'email': DEFAULT_USER['email'],
            'name': DEFAULT_USER['name']
        }
        return jsonify(response)
    elif email == DEFAULT_USER['email']:
        return jsonify({'status': 'PSW_ERROR'})
    else:
        return jsonify({'status': 'USER_NOT_REGISTERED'})
