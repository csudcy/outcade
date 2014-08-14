import json
import os

from flask import abort
from flask import Flask
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.heroku import Heroku
from flask.ext.sqlalchemy import SQLAlchemy
from wtforms import ValidationError
import wtforms as wtf

from service.auth import Auth
from service.cascade import Cascade
from service.exchange import Exchange


##################################################
#                    Config
##################################################

if 'DATABASE_URL' not in os.environ:
    # Looks like we're running locally
    os.environ['DATABASE_URL'] = 'postgres://postgres:postgres@localhost:5432/outcade'


##################################################
#                    Setup
##################################################

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'This is the secret key for Outcade.'
heroku = Heroku(app)


##################################################
#                    Database
##################################################

db = SQLAlchemy(app)

class Models(object):
    pass
db.models = Models()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean(), nullable=False, default=False)
    exchange_username = db.Column(db.String(100), nullable=False)
    exchange_password = db.Column(db.String(100), nullable=False)
    exchange_last_sync_time = db.Column(db.DateTime())
    exchange_last_sync_status = db.Column(db.Text())
    cascade_username = db.Column(db.String(100), nullable=False)
    cascade_password = db.Column(db.String(100), nullable=False)
    cascade_last_sync_time = db.Column(db.DateTime())
    cascade_last_sync_status = db.Column(db.Text())
db.models.User = User

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # These identify an event
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user = db.relationship('User', backref='events')
    start = db.Column(db.DateTime(), nullable=False)
    end = db.Column(db.DateTime(), nullable=False)
    deleted = db.Column(db.Boolean(), nullable=False, default=False)

    # This is how we find the event in outlook
    exchange_id = db.Column(db.String(100))
    exchange_subject = db.Column(db.String(100))

    # These keep track of whether we need to push updates into exchange
    last_update = db.Column(db.DateTime())
    last_push = db.Column(db.DateTime())
db.models.Event = Event


##################################################
#                    Services
##################################################

exchange = Exchange(
    db,
    'https://outlook.artsalliancemedia.com/EWS/Exchange.asmx',
    'aam'
)
cascade = Cascade(db, 'arts')
auth = Auth(db, exchange)

##################################################
#                    Setup admin
##################################################

def check_password_fields(f_new, f_confirm, required=False):
    """
    Check if the given password fields match
    """
    if f_new.data or f_confirm.data:
        # A new password has been entered
        if f_new.data != f_confirm.data:
            # Passwords dont match
            f_new.errors.append('Passwords don\'t match')
        else:
            return True
    elif required:
        # This is required (probably a new item), we have to have passwords set
        f_new.errors.append('You must enter a password')

    return False

class AuthenticateModelView(ModelView):
    def is_accessible(self):
        user = auth.get_current_user()
        if user:
            return user.is_admin
        return False

admin = Admin(app)
class UserView(AuthenticateModelView):
    column_exclude_list = (
        'exchange_password',
        'cascade_password',
    )
    form_columns = (
        'name',
        'is_admin',
        'exchange_username',
        'exchange_password_new',
        'exchange_password_confirm',
        'cascade_username',
        'cascade_password_new',
        'cascade_password_confirm',
    )
    form_extra_fields = {
        'exchange_password_new': wtf.PasswordField('Exchange Password'),
        'exchange_password_confirm': wtf.PasswordField('Exchange Password (Confirm)'),
        'cascade_password_new': wtf.PasswordField('Cascade Password'),
        'cascade_password_confirm': wtf.PasswordField('Cascade Password (Confirm)'),
    }

    def on_model_change(self, form, model, is_created):
        # Verify the exchange password
        set_exchange_password = check_password_fields(
            form.exchange_password_new,
            form.exchange_password_confirm,
            required=is_created,
        )
        if set_exchange_password:
            model.exchange_password = form.exchange_password_new.data

        # Verify the cascade password
        set_cascade_password = check_password_fields(
            form.cascade_password_new,
            form.cascade_password_confirm,
            required=is_created,
        )
        if set_cascade_password:
            model.cascade_password = form.cascade_password_new.data

        # Continue with the normal validation
        ret = super(UserView, self).on_model_change(form, model, is_created)

        # Check if we added any errors
        if len(form.exchange_password_new.errors) > 0 or len(form.cascade_password_new.errors):
            raise ValidationError()

        return ret
admin.add_view(UserView(User, db.session))
admin.add_view(AuthenticateModelView(Event, db.session))


##################################################
#                    Routes
##################################################

@app.route('/', methods=['GET'])
def splash():
    if auth.get_current_user() is not None:
        # User is already logged in, redirect to the good stuff
        return redirect(url_for('outcade'))
    return render_template('index.html')

@app.route('/login/', methods=['POST'])
def login():
    # Get the request parameters

    success = auth.login(
        exchange,
        request.form['username'],
        request.form['password'],
    )

    # Test the login details
    if success:
        # Valid username & password, save everything to the session
        return redirect(url_for('outcade'))
    # Otherwise, invalid
    return redirect(url_for('splash', error=True))

@app.route('/logout/', methods=['GET', 'POST'])
@auth.authorised
def logout():
    auth.logout()
    return redirect(url_for('splash'))

@app.route('/outcade/', methods=['GET', 'POST'])
@auth.authorised
def outcade():
    return render_template('outcade.html')

@app.route('/sync_cascade/', methods=['GET', 'POST'])
@auth.authorised
def sync_cascade():
    result = cascade.sync()
    return json.dumps(result)

@app.route('/sync_exchange/', methods=['GET', 'POST'])
@auth.authorised
def sync_exchange():
    result = exchange.sync()
    return json.dumps(result)


##################################################
#                    Main
##################################################

if __name__ == '__main__':
    # Ensure all our tables are created
    db.create_all()

    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
