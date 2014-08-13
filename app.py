import os

from flask import Flask
from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.heroku import Heroku
from flask.ext.sqlalchemy import SQLAlchemy

##################################################
#                    Setup
##################################################

app = Flask(__name__)
heroku = Heroku(app)
db = SQLAlchemy(app)
admin = Admin(app)

app.config['PROPAGATE_EXCEPTIONS'] = True

##################################################
#                    Models
##################################################

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    email = db.Column(db.String(120), unique=True)
admin.add_view(ModelView(User, db.session))

##################################################
#                    Routes
##################################################

@app.route('/')
def hello():
    return render_template('index.html')

##################################################
#                    Main
##################################################

if __name__ == '__main__':
    # Ensure all our tables are created
    db.create_all()

    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
