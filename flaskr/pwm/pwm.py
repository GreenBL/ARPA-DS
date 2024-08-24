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
        cursor.execute("SELECT id, email, password, name, surname, phone FROM users WHERE email = %s", (email,))
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
                    'phone': user[5],
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

    # Extract fields from the request data
    name = data.get('name')
    surname = data.get('surname')
    phone = data.get('phone_number')  # Ensure this matches the request payload
    email = data.get('email')
    password = data.get('password')

    # Log the received data for debugging
    current_app.logger.info(f"Received data: {data}")

    # Check if all required fields are present
    if not all([name, surname, phone, email, password]):
        return jsonify({'error': 'All fields are required'}), 400

    connection = db.getdb()  # Adjusted to the actual function name
    cursor = connection.cursor()

    try:
        # Check if the email is already in use
        query = "SELECT id FROM users WHERE email = ?"
        current_app.logger.info(f"Executing query: {query} with params: {email}")
        cursor.execute(query, (email,))
        if cursor.fetchone() is not None:
            return jsonify({'error': 'Email already in use'}), 400

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Insert the user into the database
        query = """
            INSERT INTO users (name, surname, phone, email, password) 
            VALUES (?, ?, ?, ?, ?)
        """
        params = (name, surname, phone, email, hashed_password)
        current_app.logger.info(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)

        # Get the user ID of the newly created user
        user_id = cursor.lastrowid

        # Insert a record into the balance table with a default amount
        query = """
            INSERT INTO balance (amount, ref_user) 
            VALUES (?, ?)
        """
        params = (100, user_id)
        current_app.logger.info(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)

        connection.commit()
        return jsonify({'status': 'SUCCESS'})

    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error during sign up: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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



@bp.route('/update_user', methods=['POST'])
def update_user():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'ERROR', 'message': 'Nessun dato ricevuto'}), 400

    user_id = data.get('id')
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'ID utente non fornito'}), 400

    new_name = data.get('name')
    new_surname = data.get('surname')
    new_phone = data.get('phone')

    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Aggiorna solo i campi forniti
        update_fields = []
        update_values = []

        if new_name:
            update_fields.append("name = %s")
            update_values.append(new_name)
        if new_surname:
            update_fields.append("surname = %s")
            update_values.append(new_surname)
        if new_phone:
            update_fields.append("phone = %s")
            update_values.append(new_phone)

        if not update_fields:
            return jsonify({'status': 'ERROR', 'message': 'Nessun campo da aggiornare'}), 400

        # Crea la query dinamica
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(user_id)

        cursor.execute(update_query, tuple(update_values))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'Utente non trovato'}), 404

        return jsonify({'status': 'SUCCESS', 'message': f'Utente con ID {user_id} aggiornato con successo'})
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'Errore durante l\'aggiornamento dell\'utente: {str(e)}'}), 500
    finally:
        cursor.close()
        connection.close()



@bp.route('/update_saldo', methods=['POST'])
def update_saldo():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400

    user_id = data.get('user_id')
    importo = data.get('amount')  # Make sure this key matches what is sent

    if not user_id or importo is None:
        return jsonify({'error': 'User ID and amount are required'}), 400

    try:
        importo = float(importo)
    except ValueError:
        return jsonify({'error': 'Invalid amount value'}), 400

    success = aggiorna_saldo(user_id, importo)
    if not success:
        return jsonify({'error': 'Failed to update balance'}), 500

    return jsonify({'message': 'Balance updated successfully'}), 200

def aggiorna_saldo(user_id, importo):
    try:
        balance_record = Balance.query.filter_by(ref_user=user_id).first()
        
        if balance_record:
            balance_record.amount += importo
        else:
            new_balance = Balance(amount=importo, ref_user=user_id)
            db.session.add(new_balance)

        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error updating balance: {e}")
        return False

