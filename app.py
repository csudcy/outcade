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
    is_admin = db.Column(db.Boolean(), default=False)
    exchange_username = db.Column(db.String(100), nullable=False)
    exchange_password = db.Column(db.String(100), nullable=False)
    cascade_username = db.Column(db.String(100))
    cascade_password = db.Column(db.String(100))
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

    # This is how we find the event in outlook
    exchange_id = db.Column(db.String(100))
    exchange_subject = db.Column(db.String(100))

    # These keep track of whether we need to push updates into exchange
    last_update = db.Column(db.DateTime())
    last_push = db.Column(db.DateTime())
db.models.Event = Event


##################################################
#                    Setup admin
##################################################

admin = Admin(app)
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Event, db.session))


##################################################
#                    Services
##################################################

exchange = Exchange(
    'https://outlook.artsalliancemedia.com/EWS/Exchange.asmx',
    'aam'
)
cascade = Cascade('aam')
auth = Auth(db, exchange)


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


##################################################
#                    Main
##################################################

if __name__ == '__main__':
    # Ensure all our tables are created
    db.create_all()

    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
