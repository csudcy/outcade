import functools

from flask import redirect
from flask import request
from flask import session
from flask import url_for
from sqlalchemy.orm.exc import NoResultFound

class Auth(object):
    def __init__(self, db, exchange):
        self.db = db
        self.exchange = exchange

    def login(self, exchange, username, password):
        """
        Login the given user
        """
        if not exchange.test_login(username, password):
            return False

        # User is valid, find/create them in the DB
        try:
            # Find an existing user
            user = self.db.session.query(
                self.db.models.User
            ).filter(
                self.db.models.User.exchange_username == username
            ).one()
        except NoResultFound, ex:
            # Create a new user
            user = self.db.models.User(
                name=username,
                exchange_username=username,
                is_admin=(username == 'nlee'),
            )
            self.db.session.add(user)

        # Always update the users password to the one they're using now
        user.exchange_password = password
        self.db.session.commit()

        # Setup the session
        session.permanent = True
        session['user_id'] = user.id

        # We really are logged in!
        return True

    def logout(self):
        """
        Remove the current session
        """
        session.clear()

    def get_current_user(self):
        # Check there is a user in the session
        if session.get('user_id', None) is None:
            return None

        # Check the user is still valid
        try:
            user = self.db.session.query(
                self.db.models.User
            ).filter(
                self.db.models.User.id == session['user_id']
            ).one()
        except NoResultFound, ex:
            # User no longer exists in the database, they need to login again
            return None

        # Everything pass
        return user


    def authorised(self, func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            # Check if we have a logged in user
            current_user = self.get_current_user()
            if current_user is None:
                # Bad user, you're not logged in!
                return redirect(url_for('splash'))

            # Add the user on the request
            request.user = current_user

            # Run the original function
            return func(*args, **kwargs)
        return inner
