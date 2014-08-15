from collections import namedtuple
import base64
import datetime
import json
import logging
import math
import os

from flask import abort
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask.ext.admin import Admin
from flask.ext.admin import helpers as h
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.heroku import Heroku
from flask.ext.migrate import Migrate, MigrateCommand
from flask.ext.script import Manager
from flask.ext.sqlalchemy import SQLAlchemy
from wtforms import ValidationError
import humanize
import simplecrypt
import wtforms as wtf

from service import utils
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
#                    Logging
##################################################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

for disabled_logger in ('pyexchange', ):
    dl = logging.getLogger(disabled_logger)
    dl.propagate = False


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
migrate = Migrate(app, db)

class Models(object):
    pass
db.models = Models()

def encrypt(dec):
    enc = simplecrypt.encrypt(
        app.config['SECRET_KEY'],
        dec,
    )
    return base64.b64encode(enc)


def decrypt(enc):
    dec = simplecrypt.decrypt(
        app.config['SECRET_KEY'],
        base64.b64decode(enc),
    )
    return dec.decode('utf8')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean(), nullable=False, default=False)
    sync_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    exchange_username = db.Column(db.String(100), nullable=False)
    exchange_password_encrypted = db.Column(db.String(200), nullable=False)
    exchange_last_sync_time = db.Column(db.DateTime())
    exchange_last_sync_status = db.Column(db.Text())
    cascade_username = db.Column(db.String(100), nullable=False)
    cascade_password_encrypted = db.Column(db.String(200), nullable=False)
    cascade_last_sync_time = db.Column(db.DateTime())
    cascade_last_sync_status = db.Column(db.Text())

    def __unicode__(self):
        return '{name} ({id})'.format(
            name=self.name,
            id=self.id,
        )

    def exchange_password_get(self):
        return decrypt(self.exchange_password_encrypted)
    def exchange_password_set(self, password):
        self.exchange_password_encrypted = encrypt(password)
    exchange_password = property(exchange_password_get, exchange_password_set)

    def cascade_password_get(self):
        return decrypt(self.cascade_password_encrypted)
    def cascade_password_set(self, password):
        self.cascade_password_encrypted = encrypt(password)
    cascade_password = property(cascade_password_get, cascade_password_set)

    @property
    def cascade_last_sync_error(self):
        if self.cascade_last_sync_status is None:
            return None
        return ('error' in self.cascade_last_sync_status)

    @property
    def exchange_last_sync_error(self):
        if self.exchange_last_sync_status is None:
            return None
        return ('error' in self.exchange_last_sync_status)

    @property
    def cascade_last_sync_diff(self):
        if self.cascade_last_sync_time is None:
            return None
        return datetime.datetime.now() - self.cascade_last_sync_time

    @property
    def exchange_last_sync_diff(self):
        if self.exchange_last_sync_time is None:
            return None
        return datetime.datetime.now() - self.exchange_last_sync_time

    @property
    def sync_status_summary(self):
        if not self.sync_enabled:
            # This user is not enabled for sync
            return 'disabled'

        if self.cascade_last_sync_error or self.exchange_last_sync_error:
            # At least one of that syncs errored
            # That's bad, mmmkay?
            return 'bad'

        # Work out how long ago we synced
        sync_diffs = [
            self.cascade_last_sync_diff,
            self.exchange_last_sync_diff,
        ]

        # Check the oldest sync
        if None in sync_diffs or max(*sync_diffs) > datetime.timedelta(hours=24):
            # If it's been more than a day or we've never synced
            # That's not great...
            return 'ok'

        # Otherwise, we're good
        return 'good'

    @property
    def sync_status_text(self):
        # Get the cascade status
        if self.cascade_last_sync_diff is None:
            cascade_status = 'Never synced'
        else:
            cascade_status = 'Synced {diff}'.format(
                diff=humanize.naturaltime(self.cascade_last_sync_diff),
            )
            if self.cascade_last_sync_error:
                cascade_status += ' (Errored!)'

        # Get the exchange status
        if self.exchange_last_sync_diff is None:
            exchange_status = 'Never synced'
        else:
            exchange_status = 'Synced {diff}'.format(
                diff=humanize.naturaltime(self.exchange_last_sync_diff),
            )
            if self.exchange_last_sync_error:
                exchange_status += ' (Errored!)'

        # Format it nicely
        output = 'Cascade: {cascade_status}\nExchange: {exchange_status}'.format(
            cascade_status=cascade_status,
            exchange_status=exchange_status,
        )

        # Check if this user should be syncing
        if not self.sync_enabled:
            output += '\nSync is disabled!'

        return output


db.models.User = User

class Event(db.Model):
    PeriodInfo = namedtuple('PeriodInfo', ['start', 'end', 'name'])
    PERIOD_INFO = {
        'AM': PeriodInfo(8, 14, 'Morning'),
        'PM': PeriodInfo(14, 20, 'Afternoon'),
        'AFD': PeriodInfo(8, 20, 'All Day'),
    }

    id = db.Column(db.Integer, primary_key=True)

    # These identify an event
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user = db.relationship('User', backref='events')
    day = db.Column(db.Date(), nullable=False)
    period = db.Column(db.String(10), nullable=False) #AM, PM, AFD
    event_type = db.Column(db.String(10), nullable=False) #BANK, REQUESTED, APPROVED
    updated = db.Column(db.Boolean(), nullable=False, default=True)
    deleted = db.Column(db.Boolean(), nullable=False, default=False)

    # This is how we find the event in outlook (they're really long)
    exchange_id = db.Column(db.String(200))

    # These keep track of whether we need to push updates into exchange
    last_update = db.Column(db.DateTime())
    last_push = db.Column(db.DateTime())

    def __unicode__(self):
        output = '{date} : {period}'.format(
            date=self.day.strftime('%d/%m/%Y'),
            period=self.period_info.name,
        )
        if self.event_type != 'APPROVED':
            output += ' ({status})'.format(
                status=self.event_type,
            )
        return output

    @property
    def period_info(self):
        if self.period in self.PERIOD_INFO:
            return self.PERIOD_INFO[self.period]
        return {
            'start': 8,
            'end': 20,
            'name': 'Unknown period - %s' % self.period,
        }

    @property
    def start(self):
        return datetime.datetime.combine(
            self.day,
            datetime.time(hour=self.period_info.start)
        )

    @property
    def end(self):
        return datetime.datetime.combine(
            self.day,
            datetime.time(hour=self.period_info.end)
        )

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

class UserAdminView(AuthenticateModelView):
    column_list = (
        'name',
        'is_admin',
        'sync_enabled',
        'exchange_username',
        'exchange_last_sync_time',
        'exchange_last_sync_status',
        'cascade_username',
        'cascade_last_sync_time',
        'cascade_last_sync_status',
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
        ret = super(UserAdminView, self).on_model_change(form, model, is_created)

        # Check if we added any errors
        if len(form.exchange_password_new.errors) > 0 or len(form.cascade_password_new.errors):
            raise ValidationError()

        return ret

class UserSingleView(AuthenticateModelView):
    form_columns = (
        'name',
        'sync_enabled',
        'cascade_username',
        'cascade_password_new',
        'cascade_password_confirm',
    )
    form_extra_fields = {
        'cascade_password_new': wtf.PasswordField('Cascade Password'),
        'cascade_password_confirm': wtf.PasswordField('Cascade Password (Confirm)'),
    }

    def on_model_change(self, form, model, is_created):
        # Verify the cascade password
        set_cascade_password = check_password_fields(
            form.cascade_password_new,
            form.cascade_password_confirm,
            required=is_created,
        )
        if set_cascade_password:
            model.cascade_password = form.cascade_password_new.data

        # Continue with the normal validation
        ret = super(UserSingleView, self).on_model_change(form, model, is_created)

        # Check if we added any errors
        if len(form.cascade_password_new.errors):
            raise ValidationError()

        return ret


class EventView(AuthenticateModelView):
    column_list = (
        'user',
        'day',
        'period',
        'event_type',
        'updated',
        'deleted',
        'last_update',
        'last_push',
    )
    column_default_sort = 'day'


admin = Admin(app)
admin.add_view(UserAdminView(User, db.session))
admin.add_view(EventView(Event, db.session))
# Used for creating a form later
user_single_view = UserSingleView(User, db.session)


##################################################
#                    Routes
##################################################

@app.route('/', methods=['GET', 'POST'])
def splash():
    error = False
    if request.method == 'POST':
        # Login with the request parameters
        success = auth.login(
            exchange,
            request.form['username'],
            request.form['password'],
        )
        error = not success
    if auth.get_current_user() is not None:
        # User is logged in, redirect to the good stuff
        return redirect(url_for('outcade'))
    return render_template(
        'index.html',
        error=error,
    )

@app.route('/logout/', methods=['GET', 'POST'])
@auth.authorised
def logout():
    auth.logout()
    return redirect(url_for('splash'))

@app.route('/outcade/', methods=['GET', 'POST'])
@auth.authorised
def outcade():
    form = user_single_view.edit_form(request.user)
    updated = False
    if request.method == 'POST':
        # Update the form with posted values
        form.process(request.form)

        # Validate the form
        if form.validate():
            # Update the model
            updated = user_single_view.update_model(form, request.user)

    # Get a calendar
    now = datetime.date.today()
    event_calendar = utils.generate_calendar(
        db,
        request.user,
        now.year,
        now.month,
        6,
    )

    return render_template(
        'outcade.html',
        updated=updated,
        form=form,
        event_calendar=event_calendar,
        # Needed for flask-admin form render
        h=h,
    )

@app.route('/sync_cascade/', methods=['GET', 'POST'])
@auth.authorised
def sync_cascade():
    if not request.user.is_admin:
        return abort(403)
    result = cascade.sync()
    return json.dumps(result)

@app.route('/sync_exchange/', methods=['GET', 'POST'])
@auth.authorised
def sync_exchange():
    if not request.user.is_admin:
        return abort(403)
    result = exchange.sync()
    return json.dumps(result)


##################################################
#                    Main
##################################################

manager = Manager(app)
manager.add_command('db', MigrateCommand)

@manager.command
def production():
    """
    Run the server in production mode
    """
    # Turn off debug on live...
    app.debug = False

    # Upgrade the DB
    from flask.ext.migrate import upgrade
    upgrade()

    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

@manager.command
def sync_cascade():
    """
    Sync events from cascade
    """
    logger.info('Syncing cascade...')
    result = cascade.sync()
    logger.info('Syncing cascade done!')
    logger.info(json.dumps(result, indent=4))

@manager.command
def sync_exchange():
    """
    Sync events to exchange
    """
    logger.info('Syncing exchange...')
    result = exchange.sync()
    logger.info('Syncing exchange done!')
    logger.info(json.dumps(result, indent=4))

@manager.command
def sync():
    """
    Sync everything
    """
    logger.info('Syncing cascade...')
    result = cascade.sync()
    logger.info('Syncing exchange...')
    result = exchange.sync()
    logger.info('Syncing done!')


if __name__ == '__main__':
    manager.run()
