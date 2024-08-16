from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db
from flask_bcrypt import Bcrypt

bp = Blueprint('pwm', __name__, url_prefix='/pwm')
bcrypt = Bcrypt()


@bp.route('/user', methods=['GET'])
def user():
    if request.method == 'GET':
        connection = db.getdb()
        resp = []
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM User")

            users = cursor.fetchall()
            for user in users:
                resp.append({'id': user['idUser'],
                             'username': user['username'], 
                             'password': user['password'], 
                             'nome': user['nome'],
                             'cognome': user['cognome']
                             })            

        except db.IntegrityError:
            resp.append({'error': 'Error retrieving users'})
        finally:        
            cursor.close()
    return jsonify(resp)




@bp.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    connection = db.getdb()
    resp = {}
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE idUser = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            resp = {'id': user['idUser'],
                    'username': user['username'], 
                    'password': user['password'], 
                    'nome': user['nome'],
                    'cognome': user['cognome']
                    }
        else:
            resp = {'error': 'User not found'}
    except db.IntegrityError:
        resp = {'error': 'Error retrieving user'}
    finally:
        cursor.close()
    return jsonify(resp)


@bp.route('/user', methods=['POST'])
def create_user():
    username = request.json.get('username')
    password = request.json.get('password')
    nome = request.json.get('nome')
    cognome = request.json.get('cognome')
    connection = db.getdb()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO User (username, password, nome, cognome) VALUES (%s, %s, %s, %s)", (username, password, nome, cognome))
        connection.commit()
        user_id = cursor.lastrowid
        resp = {'id': user_id, 'username': username, 'password': password}
    except db.IntegrityError:
        resp = {'error': 'Error creating user'}
    finally:
        cursor.close()
    return jsonify(resp)


@bp.route('/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    username = request.json.get('username')
    password = request.json.get('password')
    nome = request.json.get('nome')
    cognome = request.json.get('cognome')
    connection = db.getdb()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET username = %s, password = %s, nome = %s, congnome = %s,WHERE idUser = %s", (username, password, nome, cognome, user_id))
        connection.commit()
        resp = {'id': user_id, 'username': username, 'password': password}
    except db.IntegrityError:
        resp = {'error': 'Error updating user'}
    finally:
        cursor.close()
    return jsonify(resp)


@bp.route('/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    connection = db.getdb()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM User WHERE idUser = %s", (user_id,))
        connection.commit()
        resp = {'message': 'User deleted successfully'}
    except db.IntegrityError:
        resp = {'error': 'Error deleting user'}
    finally:
        cursor.close()
    return jsonify(resp)



########################################################
@bp.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    connection = db.getdb()
    
    try:
        cursor = connection.cursor()
        # Querying the users table
        cursor.execute("SELECT id, email, password, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'status': 'USER_NOT_REGISTERED'})
        elif bcrypt.check_password_hash(user[2], password):
            response = {
                'status': 'SUCCESS',
                'id': user[0],
                'email': user[1],
                'name': user[3]
            }
            return jsonify(response)
        else:
            return jsonify({'status': 'PSW_ERROR'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        cursor.close()


    

@bp.route('/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    surname = data.get('surname')
    phone_number = data.get('phone_number')
    date_birth = data.get('date_birth')
    gender = data.get('gender')
    email = data.get('email')
    password = data.get('password')

    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Hash della password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Esecuzione della query
        cursor.execute("INSERT INTO users (name, surname, phone_number, date_birth, gender, email, password) VALUES (%s, %s, %s, %s, %s, %s, %s)", (name, surname, phone_number, date_birth, gender, email, hashed_password))
        
        connection.commit()
        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
