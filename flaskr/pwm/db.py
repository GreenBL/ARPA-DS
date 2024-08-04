from flask import current_app, g
import mysql.connector

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# This code will first check if the database connection exists in g and if it's connected. 
# If it doesn't exist or it's not connected, it will create a new connection using the 
# configuration values from the app.
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def getdb():
    if 'db' not in g or not g.db.is_connected():
        g.db = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_DATABASE']
        )
    return g.db

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# This code will first get the database connection from g and then call the db.close() method
# to close the connection if it's not None and it's connected.
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def close_db(e=None):
    db = g.pop('db', None)

    if db is not None and db.is_connected():
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)