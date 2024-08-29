from flask import (
    Blueprint, Flask, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db
import qrcode
import io
import os
from flask_bcrypt import Bcrypt
from decimal import Decimal
from datetime import timedelta, datetime 
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
    selected_seats = data.get('selected_seats')  # List of seat codes
    
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

        # Update seat_status table to mark seats as occupied
        seat_status_updates = [(seat_id, theater_id, screening_date, screening_time) for seat_id in seat_ids.values()]
        cursor.executemany("""
            INSERT INTO seat_status (seat_id, theater_id, screening_date, screening_time, is_occupied)
            VALUES (%s, %s, %s, %s, TRUE)
            ON DUPLICATE KEY UPDATE is_occupied = TRUE
        """, seat_status_updates)

        # Update theater's available seats
        cursor.execute("UPDATE theater SET available = available - %s WHERE id = %s", (len(selected_seats), theater_id))

        # Check if theater is now full
        cursor.execute("SELECT available FROM theater WHERE id = %s", (theater_id,))
        available_seats = cursor.fetchone()['available']

        if available_seats == 0:
            cursor.execute("UPDATE theater SET is_full = TRUE WHERE id = %s", (theater_id,))

        # Record the purchase
        cursor.execute("""
            INSERT INTO purchases (user_id, film_id, theater_id, screening_date, screening_time, seat_count, seats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, film_id, theater_id, screening_date, screening_time, len(selected_seats), ','.join(selected_seats)))

        connection.commit()
        
        return jsonify({'status': 'SUCCESS', 'message': 'Booking successful'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



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







@bp.route('/buy_tickets', methods=['POST'])
def buy_tickets():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})
    
    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Retrieve the total seat count for the user from the purchases table
        cursor.execute("""
            SELECT SUM(seat_count) 
            FROM purchases 
            WHERE user_id = %s
            AND screening_date = CURDATE()  -- Assuming the current date is used for the screening
        """, (user_id,))
        
        result = cursor.fetchone()
        
        if result is None:
            return jsonify({'status': 'ERROR', 'message': 'No purchase record found for the user for today'})
        
        seat_count_total = result[0] or 0  # Default to 0 if the result is None
        
        # Set the ticket price
        ticket_price = Decimal('8.00')
        total_price = ticket_price * seat_count_total

        # Retrieve the current amount for the user
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'ERROR', 'message': 'No balance record found for the user'})

        current_amount = Decimal(result[0])

        if total_price > current_amount:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient balance'})

        # Update the balance
        new_amount = current_amount - total_price
        cursor.execute("UPDATE balance SET amount = %s WHERE ref_user = %s", (new_amount, user_id))
        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Purchase successful, balance updated'})

    except ValueError as e:
        return jsonify({'status': 'ERROR', 'message': 'Error in processing the transaction: ' + str(e)})
    
    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': 'An error occurred: ' + str(e)})

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

        # Query per ottenere gli ID dei film dalla tabella popular_movie
        cursor.execute("SELECT film_id FROM popular_movie")
        popular_film_ids = cursor.fetchall()

        if not popular_film_ids:
            return jsonify({'status': 'SUCCESS', 'films': []})
        
        # Estrai gli ID dei film in una lista
        film_ids = [row['film_id'] for row in popular_film_ids]

        # Query per ottenere le informazioni dei film basati sugli ID ottenuti
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
    # Get JSON data from the request
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



from flask import Blueprint, abort, send_file
import barcode
from barcode.writer import ImageWriter
import io


@bp.route('/barcodegen/<format>/<string:stringToBarcode>', methods=['GET'])
def generate_barcode(format, stringToBarcode):
    # Get the barcode class based on the provided format
    try:
        BarcodeClass = barcode.get_barcode_class(format)
    except barcode.errors.BarcodeNotFoundError:
        return abort(400, description=f"Barcode format '{format}' is not supported.")
    
    # Generate the barcode
    try:
        barcode_instance = BarcodeClass(stringToBarcode, writer=ImageWriter())
    except ValueError as e:
        return abort(400, description=f"Error: {e}")
    
    # Save the barcode to an in-memory file
    img_io = io.BytesIO()
    barcode_instance.write(img_io)
    img_io.seek(0)
    
    # Return the image as a response
    return send_file(img_io, mimetype='image/png')