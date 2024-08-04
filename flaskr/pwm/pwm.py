from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db

bp = Blueprint('pwm', __name__, url_prefix='/pwm')

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


@bp.route('/img/<path:filename>')
def flask_img(filename):
    return current_app.send_static_file("img/"+filename)


