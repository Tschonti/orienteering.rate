import os
import app
from flask import Flask
from flask_mail import Message, Mail
import logging
from logging import StreamHandler
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
	DEBUG = False
	TESTING = False
	CSRF_ENABLED = True
	SECRET_KEY = os.environ['SECRET_KEY']
	SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
	SECURITY_PASSWORD_SALT = os.environ['SECURITY_PASSWORD_SALT']
	BCRYPT_LOG_ROUNDS = 13
	WTF_CSRF_ENABLED = True
	DEBUG_TB_ENABLED = False
	DEBUG_TB_INTERCEPT_REDIRECTS = False
	LANGUAGES = ['en', 'hu']

	# mail settings
	MAIL_SERVER = 'smtp.googlemail.com'
	MAIL_PORT = 465
	MAIL_USE_TLS = False
	MAIL_USE_SSL = True

	# gmail authentication
	MAIL_USERNAME = os.environ['APP_MAIL_USERNAME']
	MAIL_PASSWORD = os.environ['APP_MAIL_PASSWORD']

	# mail accounts
	DEFAULT_MAIL_SENDER = 'orienteering.rate@gmail.com'


class ProductionConfig(Config):
	DEBUG = False


class StagingConfig(Config):
	DEVELOPMENT = True
	DEBUG = True


class DevelopmentConfig(Config):
	DEVELOPMENT = True
	DEBUG = True


class TestingConfig(Config):
	TESTING = True
	
# class HerokuConfig(ProductionConfig):
    # @classmethod
    # def init_app(cls, app):
        # ProductionConfig.init_app(app)
    # file_handler = StreamHandler()
    # file_handler.setLevel(logging.WARNING)
    # app.logger.addHandler(file_handler)
