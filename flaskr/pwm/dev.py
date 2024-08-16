from flask import (
    Blueprint, flash, g, redirect, render_template, 
    request, session, url_for, jsonify, current_app
)
from . import db

bp = Blueprint('dev', __name__, url_prefix='/dev')

@bp.route('/ack', methods=['GET'])
def ack():
    requester = request.remote_addr
    print(f"http request received from: {requester}")

    response = {
        'message': 'ACK'
    }
    return jsonify(response)