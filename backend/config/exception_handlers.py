from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from utils.exception_handler import http_exception_handler, integrity_error_handler, sqlalchemy_error_handler, \
    general_exception_handler


def register_exception_handlers(app):

    app.add_exception_handler(HTTPException, http_exception_handler)  # handle all http exceptions and pass it to the http_exception_handler
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # handle all integrity errors and pass it to the integrity_error_handler
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # handle all sqlalchemy errors and pass it to the sqlalchemy_error_handler
    app.add_exception_handler(Exception, general_exception_handler)  # handle all other exceptions and pass it to the general_exception_handler
