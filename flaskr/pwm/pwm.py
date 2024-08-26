from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db
from flask_bcrypt import Bcrypt
from decimal import Decimal
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
        elif user[2] == password:
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
    phone = data.get('phone') 
    email = data.get('email')
    password = data.get('password')

    # Check if all required fields are provided
    if not all([name, surname, phone, email, password]):
        return jsonify({'status': 'All fields are required'})
    connection = db.getdb()  # Get database connection
    cursor = connection.cursor()
    try:
        # Check if the email is already in use
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            return jsonify({'status': 'Email already in use'})

        query = """
            INSERT INTO users (name, surname, phone, email, password) 
            VALUES (%s, %s, %s, %s, %s)
        """
        params = (name, surname, phone, email, password)
        cursor.execute(query, params)

        user_id = cursor.lastrowid  # Get the ID of the newly inserted user

        # Insert a default balance for the new user
        query = """
            INSERT INTO balance (amount, ref_user) 
            VALUES (%s, %s)
        """
        params = (100, user_id)
        cursor.execute(query, params)

        connection.commit()  # Commit the transaction
        return jsonify({'status': 'SUCCESS'})

    except Exception as e:
        current_app.logger.error(f"Error during sign up: {e}")
        return jsonify({'status': 'Internal server error'})
    finally:
        cursor.close()
        connection.close() 


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


#per caricare il saldo dell'utente loggato
@bp.route('/get_amount', methods=['GET'])
def get_amount():
    data = request.get_json()
    user = data.get('user')
    
    if not user:
        # No user provided
        return jsonify({'status': 'ERROR', 'message': 'No user provided'})

    user_id = user.get('id')
    if not user_id:
        # No user ID provided
        return jsonify({'status': 'ERROR', 'message': 'No user ID provided'})

    connection = db.getdb()  
    cursor = connection.cursor()
    try:
        # Query to get the balance associated with the user ID
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'ERROR', 'message': 'Profile not found'})
        
        amount = result[0]  # Get the balance from the query result

        return jsonify({'id': user_id, 'amount': amount})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()  # Close the cursor
        connection.close()  # Close the database connection


#per aggiornare il saldo con il valore aggiunto
@bp.route('/update_amount', methods=['POST'])
def update_amount():
    data = request.get_json()
    user_id = data.get('id')
    additional_amount = data.get('amount')

    if not user_id or additional_amount is None:
        return jsonify({'status': 'ERROR', 'message': 'User ID and amount are required'})

    try:
        # Convert the additional amount to a Decimal value
        additional_amount = Decimal(str(additional_amount))
    except (ValueError, InvalidOperation):
        return jsonify({'status': 'ERROR', 'message': 'Invalid amount value'})

    connection = db.getdb()
    cursor = connection.cursor()
    try:
        # Retrieve the current amount for the user
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            
            cursor.execute("INSERT INTO balance (amount, ref_user) VALUES (%s, %s)", (additional_amount, user_id))
            connection.commit()
            return jsonify({'status': 'SUCCESS', 'message': 'Balance created and amount set successfully'})

        current_amount = result[0] 

        # Calculate the new amount
        new_amount = current_amount + additional_amount

        # Update the amount
        query = "UPDATE balance SET amount = %s WHERE ref_user = %s"
        cursor.execute(query, (new_amount, user_id))
        connection.commit() 

        return jsonify({'status': 'SUCCESS', 'message': 'Amount updated successfully'})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()  



@bp.route('/edit_email', methods=['POST'])
def edit_email():
    data = request.get_json()
    if not data:
       
        return jsonify({'status': 'ERROR'})

    user_id = data.get('id')
    if not user_id:
     
        return jsonify({'status': 'ERROR'})

    new_email = data.get('email')
    
    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Prepare the fields to update
        update_fields = []
        update_values = []

        if new_email:
            update_fields.append("email = %s")
            update_values.append(new_email)
        
       
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(user_id)

        cursor.execute(update_query, tuple(update_values))
        connection.commit()

        if cursor.rowcount == 0:
            
            return jsonify({'status': 'ERROR'})

        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR'})
    finally:
        cursor.close()
        connection.close()


@bp.route('/edit_password', methods=['POST'])
def edit_password():
    data = request.get_json()
    if not data:
       
        return jsonify({'status': 'ERROR'})

    user_id = data.get('id')
    if not user_id:
     
        return jsonify({'status': 'ERROR'})

    new_password = data.get('password')
    
    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Prepare the fields to update
        update_fields = []
        update_values = []

        if new_password:
            update_fields.append("password = %s")
            update_values.append(new_password)
        
       
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(user_id)

        cursor.execute(update_query, tuple(update_values))
        connection.commit()

        if cursor.rowcount == 0:
            
            return jsonify({'status': 'ERROR'})

        return jsonify({'status': 'SUCCESS'})
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR'})
    finally:
        cursor.close()
        connection.close()

@bp.route('/load_images', methods=['GET'])
def load_images():
    try:
        connection = db.getdb()  # Connect to the database
        cursor = connection.cursor(dictionary=True)

        # Query to retrieve all images
        cursor.execute("SELECT id, image_url FROM images")
        images = cursor.fetchall()

        # Format the result
        images_list = [{"id": img["id"], "url": img["image_url"]} for img in images]

        return jsonify({'status': 'SUCCESS', 'images': images_list})

    except Exception as e:
        # Error handling
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        # Close the connection
        cursor.close()
        connection.close()