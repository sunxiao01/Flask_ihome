# coding=utf-8
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
from flask import make_response, current_app
from flask_wtf import csrf
from flask import Blueprint

html = Blueprint('html', __name__)

@html.route("/<regex('.*'):file_name>")
def html_file(file_name):
    if not file_name:
        file_name = 'index.html'

    file_name = 'html/' + file_name
    csrf_token = csrf.generate_csrf()
    response = make_response(current_app.send_static_file(file_name))
    response.set_cookie('csrf_token', csrf_token)

    return response