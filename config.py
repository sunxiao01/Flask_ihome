# coding=utf-8
import redis

class Config:

    SECRET_KEY = 'TQ6uZxn+SLqiLgVimX838/VplIsLbEP5jV7vvZ+Ohqw='

    # 配置SQLALCHEMY所需要的参数
    SQLALCHEMY_DATABASE_URI = 'mysql://root:mysql@localhost/ihome'
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    # 创建redis实例用的参数
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = 6379

    # Flask-session所用到的参数
    SESSION_TYPE = 'redis'
    SESSION_USE_SINGER = True
    SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    PERMANENT_SESSION_LIFETIME = 86400


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    pass


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}