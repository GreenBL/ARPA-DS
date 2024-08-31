from flask import (
    Blueprint, Flask, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)

from flask import Blueprint, abort, send_file
import barcode
from barcode.writer import ImageWriter
import io
import string
import random
from . import db
from flask_bcrypt import Bcrypt
from decimal import Decimal
from datetime import timedelta, datetime 
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
import qrcode
import mysql.connector
from reportlab.pdfgen import canvas



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


@bp.route('/add_security_answer', methods=['POST'])
def add_security_answer():
    data = request.get_json()
    user_id = data.get('user_id')
    security_answer = data.get('security_answer')

    if not all([user_id, security_answer]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and Security Answer are required'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Add a security answer in the database
        cursor.execute("""
            UPDATE users 
            SET security_answer = %s 
            WHERE id = %s
        """, (security_answer, user_id))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change made'})

        return jsonify({'status': 'SUCCESS', 'message': 'Security answer updated successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()


@bp.route('/remove_security_answer', methods=['POST'])
def remove_security_answer():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Update security_answer to NULL in the database
        cursor.execute("""
            UPDATE users 
            SET security_answer = NULL 
            WHERE id = %s
        """, (user_id,))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change made'})

        return jsonify({'status': 'SUCCESS', 'message': 'Security answer removed successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()


@bp.route('/update_security_answer', methods=['POST'])
def update_security_answer():
    data = request.get_json()
    user_id = data.get('user_id')
    new_security_answer = data.get('security_answer')

    if not all([user_id, new_security_answer]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and new security answer are required'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Update security_answer in the database
        cursor.execute("""
            UPDATE users 
            SET security_answer = %s 
            WHERE id = %s
        """, (new_security_answer, user_id))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change made'})

        return jsonify({'status': 'SUCCESS', 'message': 'Security answer updated successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

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
        cursor.close()  
        connection.close() 


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


@bp.route('/associate_image', methods=['POST'])
def associate_image():
    try:
        # Get data from the request
        data = request.get_json()
        user_id = data.get('user_id')
        image_id = data.get('image_id')

        if not user_id or not image_id:
            return jsonify({'status': 'ERROR'})

        connection = db.getdb()  # Connect to the database
        cursor = connection.cursor()

        # Check if the user already has an image associated
        cursor.execute("SELECT * FROM user_images WHERE user_id = %s", (user_id,))
        association = cursor.fetchone()

        if association:
            # If the association exists, update the image associated with the user
            cursor.execute("UPDATE user_images SET image_id = %s WHERE user_id = %s", (image_id, user_id))
        else:
            # If the association does not exist, insert a new row
            cursor.execute("INSERT INTO user_images (user_id, image_id) VALUES (%s, %s)", (user_id, image_id))
        
        connection.commit()

        return jsonify({'status': 'SUCCESS'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



@bp.route('/load_films', methods=['GET'])
def load_films():
    try:
        connection = db.getdb() 
        cursor = connection.cursor(dictionary=True)

        
        cursor.execute("SELECT * FROM film")
        films = cursor.fetchall()

        
        films_list = [
            {
                "id": film["id"],
                "title": film["title"],
                "categories": film["categories"],
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"]
            }
            for film in films
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})

    except Exception as e:
      
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
       
        cursor.close()
        connection.close()



@bp.route('/movie_of_the_week', methods=['GET'])
def movie_of_the_week():
    try:
        
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

        # Calculate the current week (from Monday to Sunday)
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday of the current week
        end_of_week = start_of_week + datetime.timedelta(days=6)  # Sunday of the current week

        # Query to get movies with release_date in the current week
        query = """
            SELECT * FROM film
            WHERE release_date BETWEEN %s AND %s
        """
        cursor.execute(query, (start_of_week, end_of_week))
        films = cursor.fetchall()

       
        films_list = [
            {
                "id": film["id"],
                "title": film["title"],
                "categories": film["categories"],
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"].isoformat()  # Convert to ISO 8601 string
            }
            for film in films
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()


@bp.route('/select_seats', methods=['POST'])
def select_seats():
    data = request.get_json()
    
    user_id = data.get('user_id')
    film_id = data.get('film_id')
    theater_id = data.get('theater_id')
    screening_date = data.get('screening_date')
    screening_time = data.get('screening_time')
    selected_seats = data.get('selected_seats')  
    
    if not all([user_id, film_id, theater_id, screening_date, screening_time, selected_seats]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Check if the theater is full
        cursor.execute("SELECT seat_count, available, is_full FROM theater WHERE id = %s", (theater_id,))
        theater = cursor.fetchone()
        if not theater:
            return jsonify({'status': 'ERROR', 'message': 'Theater not found'})

        if theater['is_full']:
            return jsonify({'status': 'ERROR', 'message': 'Theater is fully booked'})

        # Retrieve seat IDs based on seat codes
        seat_placeholders = ', '.join(['%s'] * len(selected_seats))
        cursor.execute(f"""
            SELECT id, seat_code FROM seat 
            WHERE seat_code IN ({seat_placeholders}) AND theater_id = %s
        """, (*selected_seats, theater_id))
        seat_ids = {row['seat_code']: row['id'] for row in cursor.fetchall()}

        # Check if any selected seats are already occupied
        seat_ids_placeholder = ', '.join(['%s'] * len(seat_ids))
        cursor.execute(f"""
            SELECT seat_id FROM seat_status 
            WHERE seat_id IN ({seat_ids_placeholder}) AND is_occupied = TRUE
            AND theater_id = %s AND screening_date = %s AND screening_time = %s
        """, (*seat_ids.values(), theater_id, screening_date, screening_time))
        occupied_seat_ids = {row['seat_id'] for row in cursor.fetchall()}

        if occupied_seat_ids:
            return jsonify({'status': 'ERROR', 'message': 'Some seats are already occupied'})

        # Record the purchase without updating seat_status
        cursor.execute("""
            INSERT INTO purchases (user_id, film_id, theater_id, screening_date, screening_time, seat_count, seats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, film_id, theater_id, screening_date, screening_time, len(selected_seats), ','.join(selected_seats)))

        connection.commit()
        
        return jsonify({'status': 'SUCCESS', 'message': 'Seats reserved successfully. Complete payment to confirm booking.'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()




@bp.route('/buy_tickets', methods=['POST'])
def buy_tickets():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})
    
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Retrieve unpaid purchases
        cursor.execute("""
            SELECT id, seat_count, seats, theater_id, screening_date, screening_time 
            FROM purchases 
            WHERE user_id = %s AND paid = FALSE
        """, (user_id,))
        purchases = cursor.fetchall()
        
        if not purchases:
            return jsonify({'status': 'ERROR', 'message': 'No unpaid purchases found for the user'})
        
        # Calculate total seat count and total price
        seat_count_total = sum(purchase['seat_count'] for purchase in purchases)
        ticket_price = Decimal('8.00')
        total_price = ticket_price * seat_count_total
        
        # Check user balance
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s FOR UPDATE", (user_id,))
        balance_record = cursor.fetchone()
        
        if balance_record is None:
            return jsonify({'status': 'ERROR', 'message': 'No balance record found for the user'})
        
        current_amount = Decimal(balance_record['amount'])
        
        if total_price > current_amount:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient balance'})
        
        # Deduct amount from user balance
        new_amount = current_amount - total_price
        cursor.execute("UPDATE balance SET amount = %s WHERE ref_user = %s", (new_amount, user_id))
        
        # Mark purchases as paid
        purchase_ids = [purchase['id'] for purchase in purchases]
        format_strings = ','.join(['%s'] * len(purchase_ids))
        cursor.execute(f"""
            UPDATE purchases 
            SET paid = TRUE 
            WHERE id IN ({format_strings})
        """, tuple(purchase_ids))

        # Mark seats as occupied in seat_status
        for purchase in purchases:
            selected_seats = purchase['seats'].split(',')
            seat_ids = []
            
            # Get seat IDs
            seat_placeholders = ', '.join(['%s'] * len(selected_seats))
            cursor.execute(f"""
                SELECT id FROM seat 
                WHERE seat_code IN ({seat_placeholders}) AND theater_id = %s
            """, (*selected_seats, purchase['theater_id']))
            seat_ids = [row['id'] for row in cursor.fetchall()]

            # Update seat_status
            seat_status_updates = [(seat_id, purchase['theater_id'], purchase['screening_date'], purchase['screening_time']) for seat_id in seat_ids]
            cursor.executemany("""
                INSERT INTO seat_status (seat_id, theater_id, screening_date, screening_time, is_occupied)
                VALUES (%s, %s, %s, %s, TRUE)
                ON DUPLICATE KEY UPDATE is_occupied = TRUE
            """, seat_status_updates)
        
        # Check if the theater is now full and update it
        cursor.execute("""
            UPDATE theater SET available = available - %s WHERE id = %s
        """, (seat_count_total, purchases[0]['theater_id']))
        
        cursor.execute("SELECT available FROM theater WHERE id = %s", (purchases[0]['theater_id'],))
        available_seats = cursor.fetchone()['available']

        if available_seats == 0:
            cursor.execute("UPDATE theater SET is_full = TRUE WHERE id = %s", (purchases[0]['theater_id'],))
        
        # Update user's points
        cursor.execute("SELECT level, points FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})
        
        user_level = user_record['level'] or 0
        current_points = user_record['points'] or 0
        
        points_to_add = (total_price * 10) + user_level
        new_points = current_points + int(points_to_add)
        
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))
        
        connection.commit()
        
        return jsonify({'status': 'SUCCESS', 'message': 'Purchase successful, seats confirmed, balance and points updated'})
    
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        cursor.close()
        connection.close()



#PER OTTENERE LE INFO DEI SINGOLI BIGLIETTI SCELTI
@bp.route('/get_tickets', methods=['GET'])
def get_tickets():
    data = request.get_json()
    user = data.get('user')

    if not user:
        return jsonify({'status': 'ERROR', 'message': 'No user provided'})

    user_id = user.get('id')
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'No user ID provided'})

    connection = db.getdb()  
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT p.screening_date, p.screening_time, t.name AS theater_name, f.title AS film_title, p.seats
            FROM purchases p
            JOIN theater t ON p.theater_id = t.id
            JOIN film f ON p.film_id = f.id
            WHERE p.user_id = %s
        """, (user_id,))
        
        results = cursor.fetchall()

        if not results:
            return jsonify({'status': 'ERROR', 'message': 'No tickets found for this user'})

        tickets = []

        for result in results:
            screening_date = result[0]
            screening_time = result[1]
            theater_name = result[2]
            film_title = result[3]
            seats = result[4].split(',')

            if isinstance(screening_time, timedelta):
                total_seconds = int(screening_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                screening_time_str = f"{hours:02}:{minutes:02}"
            else:
                screening_time_str = screening_time.strftime("%H:%M")

            for seat in seats:
                ticket = {
                    'screening_date': screening_date.strftime("%Y-%m-%d"),
                    'screening_time': screening_time_str,
                    'theater': theater_name,
                    'film_title': film_title,
                    'seat': seat.strip()
                }
                tickets.append(ticket)

        return jsonify({'user_id': user_id, 'tickets': tickets})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()  
        connection.close()




@bp.route('/user_level_increase', methods=['POST'])
def user_level_increase():
    data = request.get_json()
    
    user_id = data.get('id')
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    try:
        cursor = connection.cursor()

        # Fetch the user's points and level
        cursor.execute("SELECT points, level FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'status': 'ERROR', 'message': 'User not found'})

        points, level = user

        if points >= 1000:
            # Update points to 0 and increment level
            update_query = """
                UPDATE users 
                SET points = 0, level = level + 1 
                WHERE id = %s
            """
            cursor.execute(update_query, (user_id,))
            connection.commit()

            return jsonify({'status': 'SUCCESS', 'message': 'Points reset and level incremented'})
        else:
            return jsonify({'status': 'ERROR', 'message': 'User has not reached 1000 points yet'})
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})
    finally:
        cursor.close()
        connection.close()



#VEDERE I POSTI GIA' OCCUPATI DI UNA DETERMINATA SALA
@bp.route('/occupied_seats', methods=['POST'])
def occupied_seats():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'ERROR', 'message': 'No data provided'})

    theater_id = data.get('theater_id')
    screening_date = data.get('screening_date')
    screening_time = data.get('screening_time')

    if not all([theater_id, screening_date, screening_time]):
        return jsonify({'status': 'ERROR', 'message': 'Theater ID, screening date, and screening time are required'})

    connection = db.getdb()
    try:
        cursor = connection.cursor(dictionary=True)  

        # Query to fetch occupied seats for the specified theater, date, and time
        query = """
            SELECT s.seat_code
            FROM seat_status ss
            JOIN seat s ON ss.seat_id = s.id
            WHERE s.theater_id = %s
              AND ss.is_occupied = TRUE
              AND ss.screening_date = %s
              AND ss.screening_time = %s
        """
        cursor.execute(query, (theater_id, screening_date, screening_time))
        occupied_seats = cursor.fetchall()

        # Format the result
        occupied_seats_list = [row['seat_code'] for row in occupied_seats]

        return jsonify({'status': 'SUCCESS', 'Occupied seats:': occupied_seats_list})
    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})
    finally:
        cursor.close()
        connection.close()



'''
#NON PRENDERE IN CONSIDERAZIONE
import random
import datetime
from flask import jsonify

def save_random_screening_dates(film_id, theater_id):
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        # Ottieni la data corrente e calcola l'inizio e la fine della settimana
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6)

        # Genera 3 date casuali all'interno della settimana corrente
        random_dates = random.sample([start_of_week + datetime.timedelta(days=i) for i in range(7)], 3)

        # Inserisci i giorni casuali nella tabella screening
        for random_date in random_dates:
            cursor.execute("""
                INSERT INTO screening (film_id, theater_id, scrining_start, date) 
                VALUES (%s, %s, %s, %s)
            """, (film_id, theater_id, '18:00:00', random_date))
        
        connection.commit()
        return jsonify({'status': 'SUCCESS', 'message': 'Random screening dates saved successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()


@bp.route('/save_random_dates', methods=['POST'])
def save_dates():
    data = request.get_json()
    film_id = data.get('film_id')
    theater_id = data.get('theater_id')

    if not film_id or not theater_id:
        return jsonify({'status': 'ERROR', 'message': 'Film ID and Theater ID are required'})

    return save_random_screening_dates(film_id, theater_id)


{
  "film_id": 1,
  "theater_id": 2
}

'''




@bp.route('/load_popular_movie', methods=['GET'])
def load_popular_movie():
    try:
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

       
        cursor.execute("SELECT film_id FROM popular_movie")
        popular_film_ids = cursor.fetchall()

        if not popular_film_ids:
            return jsonify({'status': 'SUCCESS', 'films': []})
        
        
        film_ids = [row['film_id'] for row in popular_film_ids]

        
        cursor.execute("SELECT * FROM film WHERE id IN (%s)" % ','.join(['%s'] * len(film_ids)), film_ids)
        films = cursor.fetchall()

        films_list = [
            {
                "id": film["id"],
                "title": film["title"],
                "categories": film["categories"],
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"],
                "vote": film["vote"]
            }
            for film in films
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



@bp.route('/films_by_category', methods=['POST'])
def films_by_category():
    
    data = request.get_json()

    # Check if the 'category' field is present
    category = data.get('category')
    if not category:
        return jsonify({'status': 'ERROR', 'message': 'Category parameter is required'})

    try:
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

        # Use LIKE to search for the category within the 'categories' column
        query = "SELECT * FROM film WHERE categories LIKE %s"
        pattern = f'%{category}%'
        cursor.execute(query, (pattern,))
        films = cursor.fetchall()

        films_list = [
            {
                "id": film["id"],
                "title": film["title"],
                "categories": film["categories"].split(','),
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"],
                "vote": film["vote"]
            }
            for film in films
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})


    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()




#PER GENERARE IL BARCODE DEL BIGLIETTO
def get_seat_id(ticket_id):
    connection = db.getdb()
    cursor = connection.cursor()
    
    query = """
    SELECT seat_id FROM seat_status WHERE id = %s
    """
    
    cursor.execute(query, (ticket_id,))
    result = cursor.fetchone()
    cursor.close()
    
    if result:
        return result[0]
    else:
        return None

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@bp.route('/barcodegen', methods=['GET'])
def generate_barcode():
    ticket_id = request.args.get('ticket_id')
    
    if not ticket_id:
        return abort(400, description="Missing 'ticket_id' in request parameters.")
    
    try:
        ticket_id = int(ticket_id)
    except ValueError:
        return abort(400, description="Invalid 'ticket_id' format. It should be an integer.")
    
    seat_id = get_seat_id(ticket_id)
    
    if seat_id is None:
        return abort(404, description="Ticket ID not found.")
    
    seat_id_str = str(seat_id)
    
    if len(seat_id_str) > 32: 
        return abort(400, description="Seat ID is too long. The total length must be 32 characters.") 
    
    random_part_length = 32 - len(seat_id_str) 
    random_part = generate_random_string(random_part_length)
    
    string_to_barcode = seat_id_str + random_part
    
    BarcodeClass = barcode.get_barcode_class('code128')
    
    try:
        barcode_instance = BarcodeClass(string_to_barcode, writer=ImageWriter())
    except ValueError as e:
        return abort(400, description=f"Error generating barcode: {e}")
    
    img_io = io.BytesIO()
    barcode_instance.write(img_io)
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')
#http://192.168.1.134:9000/pwm/barcodegen?ticket_id=3




#PER CREARE IL PDF
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def format_time(td):
    total_seconds = int(td.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}"

def draw_background(canvas, doc):
    # Get page dimensions
    page_width, page_height = A4
    
    # Define the size of the background image
    img_width = 300
    img_height = 300
    
    # Calculate the position to center the image horizontally
    x_position = (page_width - img_width) / 2
    
    space_below_title = 80  # Increase this value to move the image further down

    # Calculate the vertical position
    y_position = (page_height - img_height) - space_below_title
    
    # Draw the image
    canvas.drawImage(
        "C:/Users/auror/Downloads/Logo_.jpg",  
        x_position,  
        y_position,  
        img_width,   
        img_height,  
        mask='auto'
    )


def create_pdf_buffer(title, duration, theater_name, screening_date, screening_time, seat_details_text, qr_code_image):
    pdf_buffer = io.BytesIO()
    pdf = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    # Custom style for title
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Times-Roman',
        fontSize=36,
        textColor='blue',
        alignment=1,
    )

    # Custom style for conclusion
    conclusion_style = ParagraphStyle(
        'ConclusionStyle',
        parent=styles['Normal'],
        fontName='Times-Italic',
        fontSize=22,
        textColor='black',
        alignment=1,
    )

    # Custom style for details text (larger font size)
    details_style = ParagraphStyle(
        'DetailsStyle',
    parent=styles['Normal'],
    fontName='Helvetica',  
    fontSize=16,  
    textColor='black', 
    alignment=0, 
    leading=20,  
)
    
    # Create PDF elements
    elements = []

    # Register the canvas handler to add the background image
    pdf.build(elements, onFirstPage=draw_background, onLaterPages=draw_background)

   
    pdf_title = Paragraph("ARPA CINEMA", title_style)
    elements.append(pdf_title)
    elements.append(Spacer(1, 24))  # Add space between title and details

    # Details and QR code in a table
    details_text = f"""
    <para align=left>
    <b>FILM:</b> {title}<br/>
    <b>DURATA:</b> {duration}<br/>
    <b>SALA:</b> {theater_name}<br/>
    <b>GIORNO:</b> {screening_date}<br/>
    <b>ORARIO:</b> {screening_time}<br/>
    <b>POSTO:</b> {seat_details_text}
    </para>
    """
    details_paragraph = Paragraph(details_text, details_style) 
    table_data = [
        [details_paragraph, qr_code_image],
    ]
    table = Table(table_data, colWidths=[400, 100]) 
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 12))

    conclusion = Paragraph("Buona visione!", conclusion_style)
    elements.append(conclusion)

    # Build PDF
    pdf.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer

@bp.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    user_id = data.get('user_id')
    seat_code = data.get('seat_code')
    purchase_id = data.get('purchase_id')

    if not user_id or not seat_code or not purchase_id:
        return jsonify({"error": "Missing user_id, seat_code, or purchase_id"})

    connection = None
    cursor = None

    try:
    
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

      
        cursor.execute(
            "SELECT * FROM purchases WHERE id = %s AND user_id = %s", 
            (purchase_id, user_id)
        )
        purchase = cursor.fetchone()
        if not purchase:
            return jsonify({"error": "Purchase not found"})

        
        cursor.execute(
            "SELECT * FROM film WHERE id = %s", 
            (purchase['film_id'],)
        )
        film = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM theater WHERE id = %s", 
            (purchase['theater_id'],)
        )
        theater = cursor.fetchone()

       
        title = film['title']
        duration = film['duration']
        theater_name = theater['name']
        screening_date = purchase['screening_date']

       
        screening_time = purchase['screening_time']
        if isinstance(screening_time, timedelta):
            screening_time = format_time(screening_time)
        else:
            screening_time = datetime.strptime(screening_time, '%H:%M:%S').strftime('%H:%M')

      
        cursor.execute(
            "SELECT row_letter, seat_number FROM seat WHERE seat_code = %s AND theater_id = %s", 
            (seat_code, purchase['theater_id'])
        )
        seat = cursor.fetchone()
        if not seat:
            return jsonify({"error": "Seat not found"}), 404

        seat_details_text = f"FILA {seat['row_letter']} NUMERO {seat['seat_number']}"
        qr_data = f"https://example.com/purchase/{purchase_id}/{seat_code}"
        qr_img = generate_qr_code(qr_data)
        qr_code_image = Image(qr_img)
        qr_code_image.drawHeight = 100
        qr_code_image.drawWidth = 100

        pdf_buffer = create_pdf_buffer(title, duration, theater_name, screening_date, screening_time, seat_details_text, qr_code_image)

        return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=False, download_name=f'ticket_{seat_code}.pdf')

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)})

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

'''
{
    "user_id": 1,
    "seat_code": "B2",
    "purchase_id": 1
}
'''



@bp.route('/select_popcorn', methods=['POST'])
def select_popcorn():
    data = request.get_json()

    user_id = data.get('user_id')
    popcorn_id = data.get('popcorn_id')

    if not all([user_id, popcorn_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        # Retrieve popcorn details
        cursor.execute("SELECT category, size, description, price FROM popcorn WHERE id = %s", (popcorn_id,))
        popcorn = cursor.fetchone()
        
        if not popcorn:
            return jsonify({'status': 'ERROR', 'message': 'Popcorn not found'})

        price_points = int(popcorn['price'])  # Use price as price_points

        # Insert into points_redeemed table
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, size, description, price_points, paid)
            VALUES (%s, 'popcorn', %s, %s, %s, %s, %s, %s)
        """, (user_id, popcorn_id, popcorn['category'], popcorn['size'], popcorn['description'], price_points, False))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Popcorn selected successfully.', 'total_points': price_points})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()




@bp.route('/select_drink', methods=['POST'])
def select_drink():
    data = request.get_json()

    user_id = data.get('user_id')
    drink_id = data.get('drink_id')

    if not all([user_id, drink_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        # Retrieve drink details
        cursor.execute("SELECT category, size, description, price FROM drinks WHERE id = %s", (drink_id,))
        drink = cursor.fetchone()
        
        if not drink:
            return jsonify({'status': 'ERROR', 'message': 'Drink not found'})

        price_points = int(drink['price'])  # Use price as price_points

        # Insert into points_redeemed table
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, size, description, price_points, paid)
            VALUES (%s, 'drink', %s, %s, %s, %s, %s, %s)
        """, (user_id, drink_id, drink['category'], drink['size'], drink['description'], price_points, False))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Drink selected successfully.', 'total_points': price_points})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



@bp.route('/select_combo', methods=['POST'])
def select_combo():
    data = request.get_json()

    user_id = data.get('user_id')
    combo_id = data.get('combo_id')

    if not all([user_id, combo_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        # Retrieve combo details
        cursor.execute("SELECT category, menu, description, price FROM combo WHERE id = %s", (combo_id,))
        combo = cursor.fetchone()
        
        if not combo:
            return jsonify({'status': 'ERROR', 'message': 'Combo not found'})

        price_points = int(combo['price']) 

      
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, menu, description, price_points, paid)
            VALUES (%s, 'combo', %s, %s, %s, %s, %s, %s)
        """, (user_id, combo_id, combo['category'], combo['menu'], combo['description'], price_points, False))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Combo selected successfully.', 'total_points': price_points})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



@bp.route('/cancel_selection', methods=['POST'])
def cancel_selection():
    data = request.get_json()
    
    user_id = data.get('user_id')
    record_id = data.get('record_id') 
    
    if not all([user_id, record_id]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and Record ID are required'})
    
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)
    
    try:
       
        connection.start_transaction()
        
       
        cursor.execute("""
            SELECT id, price_points, paid 
            FROM points_redeemed 
            WHERE user_id = %s AND id = %s
        """, (user_id, record_id))  
        record = cursor.fetchone()
        
        if not record:
            connection.rollback()
            return jsonify({'status': 'ERROR', 'message': 'Record not found'})
        
        if record['paid']:
            connection.rollback()
            return jsonify({'status': 'ERROR', 'message': 'Cannot cancel a paid item'})
        
        # Delete the record
        cursor.execute("""
            DELETE FROM points_redeemed 
            WHERE user_id = %s AND id = %s
        """, (user_id, record_id))  
        
        
        cursor.execute("UPDATE users SET points = points + %s WHERE id = %s", (record['price_points'], user_id))
        
        connection.commit()
        
        return jsonify({'status': 'SUCCESS', 'message': 'Selection canceled successfully, points refunded'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        try:
            
            cursor.fetchall()
        except Exception:
            pass
        
        cursor.close()
        connection.close()



@bp.route('/buy_items_from_points_redeemed', methods=['POST'])
def buy_items_from_points_redeemed():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})
    
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Retrieve unpaid items
        cursor.execute("""
            SELECT id, item_type, item_id, category, size, menu, description, price_points 
            FROM points_redeemed 
            WHERE user_id = %s AND paid = FALSE
        """, (user_id,))
        items = cursor.fetchall()
        
        if not items:
            return jsonify({'status': 'ERROR', 'message': 'No unpaid items found for the user'})
        
        # Calculate total points needed
        total_points = sum(item['price_points'] for item in items)
        
        
        cursor.execute("SELECT points FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})
        
        current_points = user_record['points']
        
        if total_points > current_points:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient points'})
        
       
        new_points = current_points - total_points
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))
        
        
        item_ids = [item['id'] for item in items]
        format_strings = ','.join(['%s'] * len(item_ids))
        cursor.execute(f"""
            UPDATE points_redeemed 
            SET paid = TRUE 
            WHERE id IN ({format_strings})
        """, tuple(item_ids))

        connection.commit()
        
        return jsonify({'status': 'SUCCESS', 'message': 'Items purchased successfully, points deducted'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        cursor.close()
        connection.close()

#PER OTTENERE LE INFO DEL SINGOLO PREMIO ACQUISTATO 
@bp.route('/get_item_info', methods=['POST'])
def get_item_info():
    data = request.get_json()
    user_id = data.get('user_id')
    record_id = data.get('record_id')  

    if not all([user_id, record_id]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and Record ID are required'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT item_type, category, size, menu, description, price_points 
            FROM points_redeemed 
            WHERE user_id = %s AND id = %s AND paid = TRUE
        """, (user_id, record_id))
        
        record = cursor.fetchone()
        
        if not record:
            return jsonify({'status': 'ERROR', 'message': 'No purchased item found or item not paid'})

        # Prepare the item information
        item_info = {key: value for key, value in record.items() if value is not None}

        # Generate QR Code
        qr_data = '\n'.join([f"{key.replace('_', ' ').title()}: {value}" for key, value in item_info.items()])
        img_buffer = generate_qr_code(qr_data)
        
        # Save QR code image to a temporary file
        img_path = 'item_qr_code.png'
        with open(img_path, 'wb') as f:
            f.write(img_buffer.getvalue())

        return jsonify({
            'status': 'SUCCESS',
            'item_info': item_info,
            'qr_code_url': f'/download_qr_code/{record_id}'  
        })

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()

def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer




@bp.route('/chronology', methods=['POST'])
def chronology():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT item_type, category, size, menu, description, price_points
            FROM points_redeemed
            WHERE user_id = %s AND paid = TRUE
        """, (user_id,))
        
        records = cursor.fetchall()
        
        if not records:
            return jsonify({'status': 'ERROR', 'message': 'No paid items found for this user'})

        # Filter out null values from each record
        filtered_records = []
        for record in records:
            filtered_record = {key: value for key, value in record.items() if value is not None}
            filtered_records.append(filtered_record)

        return jsonify({
            'status': 'SUCCESS',
            'items': filtered_records
        })

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()