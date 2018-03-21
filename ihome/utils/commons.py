# coding=utf-8

from werkzeug.routing import BaseConverter
from flask import session, jsonify, g
from ihome.response_code import RET
import functools

class RegexConverter(BaseConverter):
    """自定义在路由中使用正则表达式进行提取参数的转换工具"""
    def __init__(self, url_map, *args):
        super(RegexConverter, self).__init__(url_map)
        self.regex = args[0]



def login_required(func_view):

    @functools.wraps(func_view)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id')
        if user_id is None:
            return jsonify(errno=RET.LOGINERR, errmsg='用户未登录')
        else:
            g.user_id = user_id
            return func_view(*args, **kwargs)
    return wrapper