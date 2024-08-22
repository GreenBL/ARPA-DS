from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db
from flask_bcrypt import Bcrypt

bp = Blueprint('pwm', __name__, url_prefix='/pwm')
bcrypt = Bcrypt()


@bp.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    connection = db.getdb()
    
    try:
        cursor = connection.cursor()
        # Querying the users table including phone_number and surname
        cursor.execute("SELECT id, email, password, name, surname, phone_number FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            # User not found
            return jsonify({'status': 'USER_NOT_REGISTERED', 'user': None})
        elif bcrypt.check_password_hash(user[2], password):
            # Successful login
            response = {
                'status': 'SUCCESS',
                'user': {
                    'id': user[0],
                    'email': user[1],
                    'name': user[3],
                    'surname': user[4],
                    'phone_number': user[5],
                   # 'password': user[2] 
                }
            }
            return jsonify(response)
        else:
            # Incorrect password
            return jsonify({'status': 'PSW_ERROR', 'user': None})
    
    except Exception as e:
        # Internal server error
        return jsonify({'status': 'ERROR', 'error': str(e), 'user': None}), 500
    
    finally:
        cursor.close()




@bp.route('/signup', methods=['POST'])
def signup():
    data = request.json
    
    # Estrarre i dati dal JSON
    
    name = data.get('name')
    surname = data.get('surname')
    phone_number = data.get('phone_number')
    email = data.get('email')
    password = data.get('password')
    
    # Gestire eventuali campi mancanti
    if not all([name, surname, phone_number, email, password]):
        return jsonify({'error': 'All fields are required'}), 400
    
    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Verifica se l'email è già in uso
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            return jsonify({'error': 'Email already in use'}), 400

        # Hash della password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Esecuzione della query per inserire l'utente nel database
        cursor.execute(
            """
            INSERT INTO users (name, surname, phone_number, email, password) 
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, surname, phone_number, email, hashed_password)
        )
        
        connection.commit()
        return jsonify({'status': 'SUCCESS'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        cursor.close()
        connection.close()



@bp.route('/update_profile/<int:users_id>', methods=['PUT'])
def update_profile(users_id):
    data = request.json
    new_phone_number = data.get('phone_number')
    new_email = data.get('email')
    new_password = data.get('password')
    new_name = data.get('name')  # New field for first name
    new_surname = data.get('surname')  # New field for last name

    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Ensure at least one field is provided for update
        if not any([new_phone_number, new_email, new_password, new_name, new_surname]):
            return jsonify({'error': 'No fields to update'}), 400

        # Build the dynamic update query based on provided fields
        update_fields = []
        update_values = []

        if new_phone_number:
            update_fields.append("phone_number = %s")
            update_values.append(new_phone_number)

        if new_email:
            update_fields.append("email = %s")
            update_values.append(new_email)

        if new_password:
            # Hash the new password
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            update_fields.append("password = %s")
            update_values.append(hashed_password)

        if new_name:
            update_fields.append("name = %s")
            update_values.append(new_name)

        if new_surname:
            update_fields.append("surname = %s")
            update_values.append(new_surname)

        update_values.append(users_id)

        # Create and execute the update query
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"


        cursor.execute(update_query, update_values)
        
        connection.commit()

        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@bp.route('/delete_user', methods=['POST'])
def delete_user():
    data = request.get_json()
    user = data.get('user')
    
    if not user:
        return jsonify({'status': 'ERROR', 'message': 'Nessun utente fornito'}), 400

    user_id = user.get('id')
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'ID utente non fornito'}), 400

    connection = db.getdb()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'Utente non trovato'}), 404

        return jsonify({'status': 'SUCCESS', 'message': f'Utente con ID {user_id} eliminato con successo'})
    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': 'Errore durante l\'eliminazione dell\'utente'}), 500
    finally:
        cursor.close()
        connection.close()

