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
    connection = db.getdb()  # Connect to the database
    try:
        cursor = connection.cursor()
        # Query to fetch user details by email
        cursor.execute("SELECT id, email, password, name, surname, phone FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user: 
            # User not found
            return jsonify({'status': 'USER_NOT_REGISTERED', 'user': None})
        elif bcrypt.check_password_hash(user[2], password):
            # Password matches, login successful
            response = {
                'status': 'SUCCESS',
                'user': {
                    'id': user[0],
                    'email': user[1],
                    'name': user[3],
                    'surname': user[4],
                    'phone': user[5],  
                }
            }
            return jsonify(response)
        else:      
            # Password doesn't match
            return jsonify({'status': 'PSW_ERROR', 'user': None})
    except Exception as e:
        # Handle errors
        return jsonify({'status': 'ERROR', 'error': str(e), 'user': None})
    finally:
        cursor.close()  # Always close the cursor


@bp.route('/signup', methods=['POST'])
def signup():
    data = request.json

    name = data.get('name')
    surname = data.get('surname')
    phone = data.get('phone_number') 
    email = data.get('email')
    password = data.get('password')

    current_app.logger.info(f"Received data: {data}")

    # Check if all required fields are provided
    if not all([name, surname, phone, email, password]):
        return jsonify({'error': 'All fields are required'})
    connection = db.getdb()  # Get database connection
    cursor = connection.cursor()
    try:
        # Check if the email is already in use
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            return jsonify({'error': 'Email already in use'})

        # Hash the password for security
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        query = """
            INSERT INTO users (name, surname, phone, email, password) 
            VALUES (?, ?, ?, ?, ?)
        """
        params = (name, surname, phone, email, hashed_password)
        current_app.logger.info(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)

        user_id = cursor.lastrowid  # Get the ID of the newly inserted user

        # Insert a default balance for the new user
        query = """
            INSERT INTO balance (amount, ref_user) 
            VALUES (?, ?)
        """
        params = (100, user_id)
        current_app.logger.info(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)

        connection.commit()  # Commit the transaction
        return jsonify({'status': 'SUCCESS'})

    except Exception as e:
        current_app.logger.error(f"Error during sign up: {e}")
        return jsonify({'error': 'Internal server error'})
    finally:
        cursor.close()
        connection.close()  # Ensure connection is closed


@bp.route('/delete_user', methods=['POST'])
def delete_user():
    data = request.get_json()
    user = data.get('user')
    
    if not user:
        # No user provided
        return jsonify({'status': 'ERROR', 'message': 'Nessun utente fornito'})

    user_id = user.get('id')
    if not user_id:
        # No user ID provided
        return jsonify({'status': 'ERROR', 'message': 'ID utente non fornito'})

    connection = db.getdb()  
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()

        if cursor.rowcount == 0:
            # User not found in the database
            return jsonify({'status': 'ERROR', 'message': 'Utente non trovato'})

        return jsonify({'status': 'SUCCESS', 'message': f'Utente con ID {user_id} eliminato con successo'})
    except Exception as e:
        # Handle errors
        return jsonify({'status': 'ERROR', 'message': 'Errore durante l\'eliminazione dell\'utente'})
    finally:
        cursor.close()
        connection.close() 


@bp.route('/update_user', methods=['POST'])
def update_user():
    data = request.get_json()
    if not data:
        # No data received in the request
        return jsonify({'status': 'ERROR', 'message': 'Nessun dato ricevuto'})

    user_id = data.get('id')
    if not user_id:
        # No user ID provided
        return jsonify({'status': 'ERROR', 'message': 'ID utente non fornito'})

    new_name = data.get('name')
    new_surname = data.get('surname')
    new_phone = data.get('phone')

    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Prepare the fields to update
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
            # No fields provided for update
            return jsonify({'status': 'ERROR', 'message': 'Nessun campo da aggiornare'})
        
        # Build the update query dynamically
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(user_id)

        cursor.execute(update_query, tuple(update_values))
        connection.commit()

        if cursor.rowcount == 0:
            
            return jsonify({'status': 'ERROR', 'message': 'Utente non trovato'})

        return jsonify({'status': 'SUCCESS', 'message': f'Utente con ID {user_id} aggiornato con successo'})
    except Exception as e:
        connection.rollback()  # Rollback in case of error
        return jsonify({'status': 'ERROR', 'message': f'Errore durante l\'aggiornamento dell\'utente: {str(e)}'})
    finally:
        cursor.close()
        connection.close()


@bp.route('/update_saldo', methods=['POST'])
def update_saldo():
    data = request.get_json()
    if not data:
       
        return jsonify({'error': 'No data received'})

    user_id = data.get('user_id')
    importo = data.get('amount') 

    if not user_id or importo is None:
        # User ID or amount missing
        return jsonify({'error': 'User ID and amount are required'})

    try:
        importo = float(importo)  # Ensure the amount is a valid number
    except ValueError:
        # Invalid amount value
        return jsonify({'error': 'Invalid amount value'})

    success = aggiorna_saldo(user_id, importo)
    if not success:
        # Balance update failed
        return jsonify({'error': 'Failed to update balance'})

    return jsonify({'message': 'Balance updated successfully'})

def aggiorna_saldo(user_id, importo):
    try:
        balance_record = Balance.query.filter_by(ref_user=user_id).first()
        
        if balance_record:
            # Update the existing balance
            balance_record.amount += importo
        else:
            # Create a new balance record if not exists
            new_balance = Balance(amount=importo, ref_user=user_id)
            db.session.add(new_balance)

        db.session.commit()  # Commit the changes
        return True
    except SQLAlchemyError as e:
        db.session.rollback()  # Rollback in case of error
        print(f"Error updating balance: {e}")
        return False
