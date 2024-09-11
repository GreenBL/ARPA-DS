from flask import (
    Blueprint, Flask, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)

from flask import Blueprint, abort, send_file
import barcode
import io
import os 
import string
import random
from . import db
from flask_bcrypt import Bcrypt
from decimal import Decimal, InvalidOperation
from datetime import timedelta 
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
import qrcode
import mysql.connector
from reportlab.pdfgen import canvas
from datetime import datetime


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

   
    if not all([name, surname, phone, email, password]):
        return jsonify({'status': 'All fields are required'})
    connection = db.getdb()
    cursor = connection.cursor()
    try:
    
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            return jsonify({'status': 'Email already in use'})


        query = """
            INSERT INTO users (name, surname, phone, email, password) 
            VALUES (%s, %s, %s, %s, %s)
        """
        params = (name, surname, phone, email, password)
        cursor.execute(query, params)

        user_id = cursor.lastrowid  

        # Insert a default balance for the new user
        query = """
            INSERT INTO balance (amount, ref_user) 
            VALUES (%s, %s)
        """
        params = (100, user_id)
        cursor.execute(query, params)

        # Insert into user_images with default image_id 1
        query = """
            INSERT INTO user_images (user_id, image_id)
            VALUES (%s, %s)
        """
        params = (user_id, 1)
        cursor.execute(query, params)

        connection.commit()  
        return jsonify({'status': 'SUCCESS'})

    except Exception as e:
        current_app.logger.error(f"Error during sign up: {e}")
        return jsonify({'status': 'Internal server error'})
    finally:
        cursor.close()
        connection.close() 


#OTTENERE I DATI DI UN UTENTE TRAMITE ID
@bp.route('/get_user_info', methods=['POST'])
def get_user_info():
    user_id = request.json.get('id')  
    connection = db.getdb()  
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, name, surname, phone, email
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'status': 'USER_NOT_FOUND', 'user': None})
        
        response = {
            'status': 'SUCCESS',
            'user': {
                
                'name': user[1],
                'surname': user[2],
                'phone': user[3],
                'email': user[4]
             
            }
        }
        return jsonify(response)
    except Exception as e:
        
        return jsonify({'status': 'ERROR', 'error': str(e), 'user': None})
    finally:
        cursor.close()  


#AGGIUNGERE LA DOMANDA E RIPOSTA DI SICUREZZA
@bp.route('/add_security_question_and_answer', methods=['POST'])
def add_security_question_and_answer():
    data = request.get_json()
    user_id = data.get('user_id')
    security_question = data.get('security_question')
    security_answer = data.get('security_answer')

    # Check that all necessary fields are present and valid
    if user_id is None or security_question is None or security_answer is None:
        return jsonify({'status': 'ERROR', 'message': 'ID, Question, Answer required'})

    if not (0 <= security_question <= 5):
        return jsonify({'status': 'ERROR', 'message': 'Question must be 0-5'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Check if the user already has a security question and answer set
        cursor.execute("""
            SELECT security_question, security_answer 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()

        if result and result[0] is not None and result[1] is not None:
            return jsonify({'status': 'ERROR', 'message': 'Security Q&A already set'})

        # Update the security_question and security_answer in the database
        cursor.execute("""
            UPDATE users 
            SET security_question = %s, security_answer = %s 
            WHERE id = %s
        """, (security_question, security_answer, user_id))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change'})

        return jsonify({'status': 'SUCCESS', 'message': 'Updated successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': 'Error occurred'})

    finally:
        cursor.close()
        connection.close()



#RIMUOVERE LA DOMANDA E RISPOSTA DI SICUREZZA
@bp.route('/remove_security_question_and_answer', methods=['POST'])
def remove_security_question_and_answer():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Update security_question and security_answer to NULL in the database
        cursor.execute("""
            UPDATE users 
            SET security_question = NULL, security_answer = NULL 
            WHERE id = %s
        """, (user_id,))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change made'})

        return jsonify({'status': 'SUCCESS', 'message': 'Security question and answer removed successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()


#AGGIORNARE DOMANDA E RISPOSTA DI SICUREZZA
@bp.route('/update_security_question_and_answer', methods=['POST'])
def update_security_question_and_answer():
    data = request.get_json()
    user_id = data.get('user_id')
    new_security_question = data.get('security_question')
    new_security_answer = data.get('security_answer')

    # Validate the input data
    if user_id is None or new_security_question is None or new_security_answer is None:
        return jsonify({'status': 'ERROR', 'message': 'User ID, question, and answer are required'})

    if not (0 <= new_security_question <= 5):
        return jsonify({'status': 'ERROR', 'message': 'Question must be 0-5'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Update the security_question and security_answer in the database
        cursor.execute("""
            UPDATE users 
            SET security_question = %s, security_answer = %s 
            WHERE id = %s
        """, (new_security_question, new_security_answer, user_id))

        # Commit the changes
        connection.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'status': 'ERROR', 'message': 'User not found or no change made'})

        return jsonify({'status': 'SUCCESS', 'message': 'Security question and answer updated successfully'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()


#VERIFICARE SE UN UTENTE HA MESSO LA DOMANDA DI SICUREZZA
@bp.route('/check_security_question', methods=['POST'])
def check_security_question():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    cursor = connection.cursor()

    try:
        # Query to check if the user has a security question set
        cursor.execute("""
            SELECT security_question 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'ERROR', 'message': 'User not found'})

        if result[0] is not None:
            return jsonify({'status': 'SUCCESS', 'message': 'Security question is set'})
        else:
            return jsonify({'status': 'SUCCESS', 'message': 'No security question set'})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()


# TRAMITE EMAIL OTTENERE IL NUMERO DI DOMANDA E LA RISPOSTA DI SICUREZZA INSERITA DALL'UTENTE
@bp.route('/get_security_question_and_answer', methods=['POST'])
def get_security_question_and_answer():
    data = request.get_json()

    email = data.get('email')
    
    if not email:
        return jsonify({'status': 'ERROR', 'message': 'Missing email'})
    
    connection = db.getdb() 
    cursor = connection.cursor(dictionary=True)
    
    try:
      
        query = """
            SELECT id, security_question, security_answer
            FROM users
            WHERE email = %s
        """
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'status': 'ERROR', 'message': 'User not found'})
        
        
        user_id = user['id']
        security_question = user['security_question']
        security_answer = user['security_answer']
        
        return jsonify({
            'status': 'SUCCESS', 
            'user_id': user_id,
            'security_question': security_question, 
            'security_answer': security_answer
        })
    
    except Exception as e:
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


#MODIFICARE DATI PERSONALI UTENTE
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
@bp.route('/get_amount', methods=['POST']) 
def get_amount():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'Nessun ID utente fornito'})

    connection = db.getdb()  
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'ERROR', 'message': 'Profilo non trovato'})
        
        amount = result[0]

        return jsonify({'amount': amount})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



#per aggiornare il saldo con il valore aggiunto
@bp.route('/update_amount', methods=['POST'])
def update_amount():
    data = request.get_json()
    user_id = data.get('user_id')
    additional_amount = data.get('amount')

    if not user_id or additional_amount is None:
        return jsonify({'status': 'ERROR', 'message': 'User ID and amount are required'})

    try:
        # Convert the additional amount to a Double value
        additional_amount = float(additional_amount)
    except ValueError:
        return jsonify({'status': 'ERROR', 'message': 'Invalid amount value'})

    connection = db.getdb()
    cursor = connection.cursor()
    try:
        # Retrieve the current amount for the user
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            # Insert new balance record
            cursor.execute("INSERT INTO balance (amount, ref_user) VALUES (%s, %s)", (additional_amount, user_id))
            connection.commit()
            return jsonify({'status': 'SUCCESS', 'message': 'Balance created and amount set successfully'})

        current_amount = float(result[0])  # Ensure this is a float

        # Calculate the new amount
        new_amount = current_amount + additional_amount

        # Update the amount
        cursor.execute("UPDATE balance SET amount = %s WHERE ref_user = %s", (new_amount, user_id))
        connection.commit() 

        return jsonify({'status': 'SUCCESS', 'message': 'Amount updated successfully'})

    except Exception as e:
        connection.rollback()  # Rollback in case of error
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()



#CAMBIARE LA MAIL
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

#CAMBIARE PASSWORD
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


#PER CARICARE LE IMMAGINI DEL PROFILO NELL'APP
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



#LA SCELTA DELL'IMMAGINE PROFILO PER UN UTENTE
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



#PER OTTENERE L'IMMAGINE ASSOCIATA AD UN UTENTE
@bp.route('/get_user_image', methods=['POST'])
def get_user_image():
    user_id = request.json.get('user_id') 
    connection = db.getdb() 
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT images.image_url 
            FROM user_images 
            JOIN images ON user_images.image_id = images.id
            WHERE user_images.user_id = %s
        """, (user_id,))
        
        image = cursor.fetchone()
        
        if not image:
            
            return jsonify({'status': 'IMAGE_NOT_FOUND', 'image': None})
        
        # Image found, return the URL
        response = {
            'status': 'SUCCESS',
            'image_url': image[0]
        }
        return jsonify(response)
    except Exception as e:
        # Error handling
        return jsonify({'status': 'ERROR', 'error': str(e), 'image': None})
    finally:
        cursor.close() 




#CARICARE I FILM NELL'APP
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
                "release_date": film["release_date"].isoformat() if isinstance(film["release_date"], datetime) else str(film["release_date"]),
                "vote": float(film["vote"]) if film["vote"] is not None else None
            }
            for film in films
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()


#PER CARICARE I FILM IN HOME
@bp.route('/movie_of_the_week', methods=['GET'])
def movie_of_the_week():
    try:
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

        # Calcola la settimana corrente (dal lunedì alla domenica)
        today = datetime.today().date()  # Ottieni la data odierna
        start_of_week = today - timedelta(days=today.weekday())  # Lunedì della settimana corrente
        end_of_week = start_of_week + timedelta(days=6)  # Domenica della settimana corrente

        # Query per ottenere i film con data di rilascio nella settimana corrente
        query = """
            SELECT * FROM film
            WHERE release_date BETWEEN %s AND %s
        """
        cursor.execute(query, (start_of_week, end_of_week))
        films = cursor.fetchall()

        # Crea la lista di film
        films_list = [
            {
                "id": film["id"],
                "title": film["title"],
                "categories": film["categories"],
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"].isoformat() if isinstance(film["release_date"], datetime) else str(film["release_date"]),
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


#SELEZIONARE TUTTE LE INFO CHE COMPORRANNO UN BIGLIETTO E ACQUISTARLO
@bp.route('/select_seats_&_buy_tickets', methods=['POST'])
def select_seats_and_buy_tickets():
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
        connection.start_transaction()

        # Controllo se il teatro è pieno
        cursor.execute("SELECT seat_count, available, is_full FROM theater WHERE id = %s", (theater_id,))
        theater = cursor.fetchone()
        if not theater:
            return jsonify({'status': 'ERROR', 'message': 'Theater not found'})

        if theater['is_full']:
            return jsonify({'status': 'ERROR', 'message': 'Theater is fully booked'})

        # Recupero i posti occupati attualmente per la sala selezionata
        cursor.execute("""
            SELECT s.seat_code
            FROM seat_status ss
            JOIN seat s ON ss.seat_id = s.id
            WHERE s.theater_id = %s
              AND ss.is_occupied = TRUE
              AND ss.screening_date = %s
              AND ss.screening_time = %s
        """, (theater_id, screening_date, screening_time))
        occupied_seats = [row['seat_code'] for row in cursor.fetchall()]

        # Verifica se ci sono posti già occupati tra quelli selezionati dall'utente
        seat_placeholders = ', '.join(['%s'] * len(selected_seats))
        cursor.execute(f"""
            SELECT id, seat_code FROM seat 
            WHERE seat_code IN ({seat_placeholders}) AND theater_id = %s
        """, (*selected_seats, theater_id))
        seat_ids = {row['seat_code']: row['id'] for row in cursor.fetchall()}

        seat_ids_placeholder = ', '.join(['%s'] * len(seat_ids))
        cursor.execute(f"""
            SELECT seat_id FROM seat_status 
            WHERE seat_id IN ({seat_ids_placeholder}) AND is_occupied = TRUE
            AND theater_id = %s AND screening_date = %s AND screening_time = %s
        """, (*seat_ids.values(), theater_id, screening_date, screening_time))
        occupied_seat_ids = {row['seat_id'] for row in cursor.fetchall()}

        if occupied_seat_ids:
            return jsonify({'status': 'ERROR', 'message': 'Some seats are already occupied', 'occupied_seats': occupied_seats})

        # Calcola il prezzo totale
        seat_count_total = len(selected_seats)
        ticket_price = Decimal('8.00')
        total_price = ticket_price * seat_count_total
        
        # Verifica il saldo dell'utente
        cursor.execute("SELECT amount FROM balance WHERE ref_user = %s FOR UPDATE", (user_id,))
        balance_record = cursor.fetchone()
        
        if balance_record is None:
            return jsonify({'status': 'ERROR', 'message': 'No balance record found for the user'})
        
        current_amount = Decimal(balance_record['amount'])
        
        if total_price > current_amount:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient balance'})
        
        # Deduce l'importo dal saldo dell'utente
        new_amount = current_amount - total_price
        cursor.execute("UPDATE balance SET amount = %s WHERE ref_user = %s", (new_amount, user_id))
        
        # Registra l'acquisto
        cursor.execute("""
            INSERT INTO purchases (user_id, film_id, theater_id, screening_date, screening_time, seat_count, seats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, film_id, theater_id, screening_date, screening_time, seat_count_total, ','.join(selected_seats)))

        # Aggiorna lo stato dei posti
        seat_status_updates = [(seat_id, theater_id, screening_date, screening_time) for seat_id in seat_ids.values()]
        cursor.executemany("""
            INSERT INTO seat_status (seat_id, theater_id, screening_date, screening_time, is_occupied)
            VALUES (%s, %s, %s, %s, TRUE)
            ON DUPLICATE KEY UPDATE is_occupied = TRUE
        """, seat_status_updates)
        
        # Aggiorna la disponibilità del teatro
        cursor.execute("""
            UPDATE theater SET available = available - %s WHERE id = %s
        """, (seat_count_total, theater_id))
        
        cursor.execute("SELECT available FROM theater WHERE id = %s", (theater_id,))
        available_seats = cursor.fetchone()['available']

        if available_seats == 0:
            cursor.execute("UPDATE theater SET is_full = TRUE WHERE id = %s", (theater_id,))

        # Aggiorna i punti dell'utente
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



#OTTENERE LE DATE DEL FILM SCELTO TRAMITE FILM_ID
@bp.route('/get_screening_dates', methods=['POST'])
def get_screening_dates():
    data = request.get_json()
    
    film_id = data.get('film_id')
    
    if not film_id:
        return jsonify({'status': 'ERROR', 'message': 'Missing film_id'})
    
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)
    
    try:
       
        query = """
            SELECT date
            FROM screening
            WHERE film_id = %s
        """
        cursor.execute(query, (film_id,))
        screenings = cursor.fetchall()
        
        if not screenings:
            return jsonify({'status': 'ERROR', 'message': 'No screenings found for the selected film'})
        
      
        screening_dates = [
            {
                
                'date': screening['date'].isoformat()  
            } 
            for screening in screenings
        ]
        
        return jsonify({'status': 'SUCCESS', 'screening_dates': screening_dates})
    
    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        cursor.close()
        connection.close()



#OTTENERE GLI ORATI DEL FILM SCELTO TRAMITE FILM_ID
@bp.route('/get_screening_start', methods=['POST'])
def get_screening_start():
    data = request.get_json()
    
    film_id = data.get('film_id')
    screening_date = data.get('screening_date')  
   
    if not film_id or not screening_date:
        return jsonify({'status': 'ERROR', 'message': 'Missing film_id or screening_date'})
    
    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)
    
    try:
       
        query = """
            SELECT screening_start, theater_id
            FROM screening
            WHERE film_id = %s AND date = %s
        """
        cursor.execute(query, (film_id, screening_date))
        screenings = cursor.fetchall()
        
        if not screenings:
            return jsonify({'status': 'ERROR', 'message': 'No screenings found for the selected film on the specified date'})
        
        screening_start = [
            {
                'time': (datetime.min + screening['screening_start']).strftime('%H:%M'),
                'theater_id': screening['theater_id']
            }
            for screening in screenings
        ]
        
        return jsonify({'status': 'SUCCESS', 'screening_start': screening_start})
    
    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        cursor.close()
        connection.close()




#PER OTTENERE LE INFO DI TUTTI I BIGLIETTI COMPRATI DA UN USER 
@bp.route('/chronology', methods=['POST'])
def chronology():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'No user ID provided'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT p.id AS purchase_id, p.screening_date, p.screening_time, t.name AS theater_name, f.title AS film_title, f.url AS film_url, p.seats
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
            screening_date = result['screening_date']
            screening_time = result['screening_time']
            theater_name = result['theater_name']
            film_title = result['film_title']
            film_url = result['film_url']
            seats = result['seats'].split(',')
            purchase_id = result['purchase_id']

            
            screening_date_str = screening_date.isoformat()

           
            if isinstance(screening_time, timedelta):
                total_seconds = int(screening_time.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                screening_time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
            else:
             
                screening_time_str = str(screening_time)

            for seat in seats:
                ticket = {
                    'purchase_id': purchase_id,
                    'screening_date': screening_date_str,
                    'screening_time': screening_time_str,
                    'theater': theater_name,
                    'film_title': film_title,
                    'film_url': film_url,
                    'seat': seat.strip()
                }
                tickets.append(ticket)

        return jsonify({'status': 'SUCCESS', 'tickets': tickets})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()




#PER GENERARE IL QRCODE
@bp.route('/qrcodegen', methods=['GET'])
def generate_qr_code():
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
    
    string_to_qr = seat_id_str + random_part
    
    # Generate the QR code
    qr = qrcode.QRCode(
        version=1,  # controls the size of the QR code (1 is the smallest)
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,  # size of each box in the QR code
        border=4,  # thickness of the border
    )
    
    qr.add_data(string_to_qr)
    qr.make(fit=True)
    
    # Create an image from the QR code
    img = qr.make_image(fill="black", back_color="white")
    
    # Save the image to a BytesIO object
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    # Return the QR code as a PNG image
    return send_file(img_io, mimetype='image/png')


#OTTENERE PUNTI E LIVELLO ASSOCIATI AD UN UTENTE 
@bp.route('/get_user_points_and_level', methods=['POST'])
def get_user_points_and_level():
    data = request.get_json()

    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'Missing user_id'})
    
    connection = db.getdb() 
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Retrieve points and level for the given user_id
        query = """
            SELECT points, level
            FROM users
            WHERE id = %s
        """
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'status': 'ERROR', 'message': 'User not found'})
        
        # Fetch points and level
        points = user['points']
        level = user['level']
        
        return jsonify({
            'status': 'SUCCESS', 
            'points': points, 
            'level': level
        })
    
    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})
    
    finally:
        cursor.close()
        connection.close()



#LA SCELTA DI UN UTENTE DI SPENDERE I SUOI PUNTI PER SALIRE DI LIVELLO
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




#PER CARICARE I FILM IN PROMO NELLA HOME
@bp.route('/load_promo_movie', methods=['GET'])
def load_promo_movie():
    try:
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT film_id, url_promo, short_description, long_description FROM promo_film")
        promo_films = cursor.fetchall()

        if not promo_films:
            return jsonify({'status': 'SUCCESS', 'films': []})

        film_ids = [row['film_id'] for row in promo_films]

        cursor.execute("SELECT id, title, url FROM film WHERE id IN (%s)" % ','.join(['%s'] * len(film_ids)), film_ids)
        films = cursor.fetchall()

        films_list = [
            {
                "title": film["title"],
                "url": film["url"],  
                "promo_url": promo_film["url_promo"],  
                "short_description": promo_film["short_description"],
                "long_description": promo_film["long_description"]
            }
            for film, promo_film in zip(films, promo_films)
        ]

        return jsonify({'status': 'SUCCESS', 'films': films_list})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



#PER OTTENERE LE INFO DI UN SINGOLO FILM DELLA SEZIONE PROMO 
@bp.route('/promo_movie', methods=['POST'])
def get_promo_movie_by_promo_id():
    try:
        connection = db.getdb()
        cursor = connection.cursor(dictionary=True)

        data = request.get_json()
        promo_id = data.get('promo_id')

        if not promo_id:
            return jsonify({'status': 'ERROR', 'message': 'ID del promo non fornito'})

        query = """
            SELECT promo_film.url_promo, promo_film.short_description, promo_film.long_description, 
                   film.title, film.url
            FROM promo_film
            JOIN film ON promo_film.film_id = film.id
            WHERE promo_film.id = %s
        """
        cursor.execute(query, (promo_id,))
        promo_film = cursor.fetchone()

        if not promo_film:
            return jsonify({'status': 'ERROR', 'message': 'Promo film non trovato'})

        film_data = {
            "title": promo_film["title"],
            "url": promo_film["url"], 
            "promo_url": promo_film["url_promo"],  
            "short_description": promo_film["short_description"],
            "long_description": promo_film["long_description"]
        }

        return jsonify({'status': 'SUCCESS', 'film': film_data})

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()




#DISTRIBUIRE I FILM NELLE VARIE CATEGORIE NELL'APP
@bp.route('/films_by_category', methods=['POST'])
def films_by_category():
    data = request.get_json()

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
                "categories": film["categories"],
                "plot": film["plot"],
                "duration": film["duration"],
                "url": film["url"],
                "producer": film["producer"],
                "release_date": film["release_date"].isoformat() if film["release_date"] else None,  # Convert to ISO 8601 using isoformat()
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
    
# Get the absolute path to the static images directory
    base_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'ArpaLogo.jpg')

    # Check if the file exists before trying to open it
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"The file {base_path} does not exist.")

    # Draw the image
    canvas.drawImage(
        base_path,  
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
            return jsonify({"error": "Seat not found"})

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


#SELEZIONARE UN POPCORN E COMPRARLO
@bp.route('/select_popcorn_and_buy_item', methods=['POST'])
def select_popcorn_and_buy_item():
    data = request.get_json()

    user_id = data.get('user_id')
    popcorn_id = data.get('popcorn_id')

    if not all([user_id, popcorn_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
      
        cursor.execute("SELECT category, size, description, price FROM popcorn WHERE id = %s", (popcorn_id,))
        popcorn = cursor.fetchone()
        
        if not popcorn:
            return jsonify({'status': 'ERROR', 'message': 'Popcorn not found'})

        price_points = int(popcorn['price'])  # Use price as price_points
        
        # Retrieve user points
        cursor.execute("SELECT points FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})
        
        current_points = user_record['points']
        
        if price_points > current_points:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient points'})
        
   
        new_points = current_points - price_points
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))
        
        # Insert into points_redeemed table
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, size, description, price_points)
            VALUES (%s, 'popcorn', %s, %s, %s, %s, %s)
        """, (user_id, popcorn_id, popcorn['category'], popcorn['size'], popcorn['description'], price_points))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Combo selected and purchased successfully.', 'remaining_points': new_points})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()



#SELEZIONARE UN DRINK E COMPRARLO
@bp.route('/select_drink_and_buy_item', methods=['POST'])
def select_drink_and_buy_item():
    data = request.get_json()

    user_id = data.get('user_id')
    drink_id = data.get('drink_id')

    if not all([user_id, drink_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("SELECT category, size, description, price FROM drinks WHERE id = %s", (drink_id,))
        drink = cursor.fetchone()
        
        if not drink:
            return jsonify({'status': 'ERROR', 'message': 'Drink not found'})

        price_points = int(drink['price'])  # Use price as price_points

        # Retrieve user's current points
        cursor.execute("SELECT points FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})
        
        current_points = user_record['points']
        
        # Check if user has enough points
        if price_points > current_points:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient points'})
        
        # Deduct points and update the user's points
        new_points = current_points - price_points
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))
       
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, size, description, price_points)
            VALUES (%s, 'drink', %s, %s, %s, %s, %s)
        """, (user_id, drink_id, drink['category'], drink['size'], drink['description'], price_points))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Item selected and purchased successfully.', 'remaining_points': new_points})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': f'An error occurred: {str(e)}'})

    finally:
        cursor.close()
        connection.close()



#SELEZIONARE UNA COMBO E COMPRARLA
@bp.route('/select_combo_and_buy_item', methods=['POST'])
def select_combo_and_buy_item():
    data = request.get_json()

    user_id = data.get('user_id')
    combo_id = data.get('combo_id')

    if not all([user_id, combo_id]):
        return jsonify({'status': 'ERROR', 'message': 'Missing required data'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

       
        cursor.execute("SELECT category, menu, description, price FROM combo WHERE id = %s", (combo_id,))
        combo = cursor.fetchone()

        if not combo:
            return jsonify({'status': 'ERROR', 'message': 'Combo not found'})

        price_points = int(combo['price'])

        cursor.execute("SELECT points FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()

        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})

        current_points = user_record['points']

        if price_points > current_points:
            return jsonify({'status': 'ERROR', 'message': 'Insufficient points'})

        # Deduct the points from the user's account
        new_points = current_points - price_points
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))

       
        cursor.execute("""
            INSERT INTO points_redeemed (user_id, item_type, item_id, category, menu, description, price_points)
            VALUES (%s, 'combo', %s, %s, %s, %s, %s)
        """, (user_id, combo_id, combo['category'], combo['menu'], combo['description'], price_points))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': 'Combo selected and purchased successfully.', 'total_points': price_points})

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



#OTTENERE LE INFORMAZIONI DI TUTTI I PREMI RISCATTATI DA QUELL'UTENTE 
@bp.route('/get_items', methods=['POST'])
def get_items():
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
            WHERE user_id = %s
        """, (user_id,))
        
        records = cursor.fetchall()
        
        if not records:
            return jsonify({'status': 'ERROR', 'message': 'No items found for this user'})

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



#SELEZIONARE UNO SCONTO TRA  'free_ticket' O 'ticket_discount'
@bp.route('/select_discounts', methods=['POST'])
def select_discounts():
    data = request.get_json()
    user_id = data.get('user_id')
    reward_type = data.get('reward_type')  # 'free_ticket' or 'ticket_discount'

    if not all([user_id, reward_type]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and reward type are required'})

    if reward_type not in ['free_ticket', 'ticket_discount']:
        return jsonify({'status': 'ERROR', 'message': 'Invalid reward type'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Retrieve user details
        cursor.execute("SELECT points, free_ticket_count, ticket_discounts FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})

        current_points = user_record['points']

        # Check if the user has enough points
        if reward_type == 'free_ticket':
            if current_points < 1000:
                return jsonify({'status': 'ERROR', 'message': 'Insufficient points for free ticket'})
            # Update the free ticket count
            cursor.execute("UPDATE users SET free_ticket_count = free_ticket_count + 1 WHERE id = %s", (user_id,))
        elif reward_type == 'ticket_discount':
            if current_points < 700:
                return jsonify({'status': 'ERROR', 'message': 'Insufficient points for ticket discount'})
            # Update the ticket discount count
            cursor.execute("UPDATE users SET ticket_discounts = ticket_discounts + 1 WHERE id = %s", (user_id,))

       
        points_to_deduct = 1000 if reward_type == 'free_ticket' else 700
        new_points = current_points - points_to_deduct
        cursor.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': f'{reward_type.replace("_", " ").title()} successfully redeemed'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()


#PER OTTENERE IL NUMERO DI  'free_ticket' O 'ticket_discount' POSSEDUTI DA UN UTENTE
@bp.route('/get_rewards', methods=['POST'])
def get_rewards():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'ERROR', 'message': 'User ID is required'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        # Retrieve user rewards
        cursor.execute("""
            SELECT free_ticket_count, ticket_discounts
            FROM users
            WHERE id = %s
        """, (user_id,))
        
        user_record = cursor.fetchone()
        
        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})
        
        # Extract reward counts
        free_ticket_count = user_record['free_ticket_count']
        ticket_discounts = user_record['ticket_discounts']

        return jsonify({
            'free_ticket_count': free_ticket_count,
            'ticket_discounts': ticket_discounts,
            'status': 'SUCCESS'
        })

    except Exception as e:
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()


#APPLICARE/USARE UNO SCONTO TRA  'free_ticket' O 'ticket_discount'
@bp.route('/use_reward', methods=['POST'])
def use_reward():
    data = request.get_json()
    user_id = data.get('user_id')
    reward_type = data.get('reward_type')  # Should be either 'free_ticket' or 'ticket_discount'

    if not all([user_id, reward_type]):
        return jsonify({'status': 'ERROR', 'message': 'User ID and reward type are required'})

    if reward_type not in ['free_ticket', 'ticket_discount']:
        return jsonify({'status': 'ERROR', 'message': 'Invalid reward type'})

    connection = db.getdb()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Retrieve user rewards
        cursor.execute("SELECT free_ticket_count, ticket_discounts FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user_record = cursor.fetchone()

        if user_record is None:
            return jsonify({'status': 'ERROR', 'message': 'User record not found'})

        # Check and update reward based on the type
        if reward_type == 'free_ticket':
            if user_record['free_ticket_count'] <= 0:
                return jsonify({'status': 'ERROR', 'message': 'No free tickets available'})
            # Decrement the free_ticket_count
            cursor.execute("UPDATE users SET free_ticket_count = free_ticket_count - 1 WHERE id = %s", (user_id,))
        elif reward_type == 'ticket_discount':
            if user_record['ticket_discounts'] <= 0:
                return jsonify({'status': 'ERROR', 'message': 'No ticket discounts available'})
            # Decrement the ticket_discounts
            cursor.execute("UPDATE users SET ticket_discounts = ticket_discounts - 1 WHERE id = %s", (user_id,))

        connection.commit()

        return jsonify({'status': 'SUCCESS', 'message': f'{reward_type.replace("_", " ").title()} successfully used'})

    except Exception as e:
        connection.rollback()
        return jsonify({'status': 'ERROR', 'message': str(e)})

    finally:
        cursor.close()
        connection.close()
        


