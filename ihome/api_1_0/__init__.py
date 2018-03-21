# coding=utf-8

from flask import Blueprint

api = Blueprint('api', __name__, url_prefix='/api/v1.0/')

from . import register
from . import users

# @api.after_request
# def after_request():
#     """
#     设置默认的响应报文格式为application/json
#     如果默认为text格式则改为application/json
#     """