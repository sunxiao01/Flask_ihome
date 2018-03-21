# coding=utf-8
import logging
from logging.handlers import RotatingFileHandler

import redis
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CsrfProtect, CSRFProtect

from config import config, Config
from ihome.utils.commons import RegexConverter

# 创建数据库
db = SQLAlchemy()
# 使用wtf提供csrf保护机制
csrf = CSRFProtect()

# 创建redis对象
redis_store = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)

# 设置日志记录选项
# 设置日志记录等级
logging.basicConfig(level=logging.DEBUG)
# 创建日志记录器，指定日志保存的路径，每个日志文件的大小及保存日志文件的个数上限
file_log_handler = RotatingFileHandler('logs/log', maxBytes=1024*1024*100, backupCount=10)
# 创建日志记录的格式
formatter = logging.Formatter('%(levelname)s %(filename)s: %(lineno)d %(message)s')
# 为刚创建的日志记录器指定日志的记录格式
file_log_handler.setFormatter(formatter)
# 为全局的日志工具对象（应用程序实例app使用的）添加日后记录器
logging.getLogger().addHandler(file_log_handler)


def create_app(config_name):

    # 创建app应用
    app = Flask(__name__)
    # 从配置对象中为app设置配置参数信息
    app.config.from_object(config[config_name])
    # 关联数据库与应用
    db.init_app(app)
    # 为app提供csrf保护
    csrf.init_app(app)
    # 为app中的url_map路由添加正则表达式匹配
    app.url_map.converters['regex'] = RegexConverter

    # 使用Flask_session扩展包，用redis保存app的session数据
    Session(app)

    # 注册蓝图
    from web_page import html as html_blueprint
    app.register_blueprint(html_blueprint)

    from api_1_0 import api as api_1_0_blueprint
    app.register_blueprint(api_1_0_blueprint)

    return app