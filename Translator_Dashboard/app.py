from flask import Flask, render_template, url_for, redirect, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
import pymysql
from datetime import timedelta
import os
import boto3
import json
pymysql.install_as_MySQLdb()


#CA_CERT = os.environ['CA_CERT']

class AWSClient:
    def get_database_credentials(self):
        secret = self.get_secret()
        secret_dict = json.loads(secret)
        return secret_dict.get('username'), secret_dict.get('port'), secret_dict.get('database'), secret_dict.get('host')


    def get_secret(self):
        secret_name = "HighTimesDB"
        region_name = os.environ['AWS_REGION'] 
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response['SecretString']
        except Exception as e:
            raise e

    def make_token(self):
        rds_client = boto3.client('rds')

        username, port, database, endpoint = self.get_database_credentials()

        database_token = rds_client.generate_db_auth_token(
            DBHostname=endpoint,
            Port=port,
            DBUsername=username,
            Region=os.environ['AWS_REGION']
            )

        return database_token 

def create_app():
    aws = AWSClient()

    username, port, database, host = aws.get_database_credentials()

    token = aws.make_token()

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{username}:{token}@{host}/{database}?ssl=1&ssl_ca=/home/ubuntu/Translator_Dashboard/certs/AmazonRootCA1.pem"
    app.config['SECRET_KEY'] = 'thisisasecretkey'
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=14)

    db = SQLAlchemy()
    db.init_app(app)
    bcrypt = Bcrypt(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    return app, db, login_manager, bcrypt

app, db, login_manager, bcrypt = create_app()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)



class LoginForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')



@app.route('/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash('User does not exist. Please contact admin.', 'danger')
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                remember_me = True if request.form.get("remember") else False
                login_user(user, remember=remember_me)
                return redirect(url_for('dashboard'))
            else:
                flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/translations', methods=['GET', 'POST'])
@login_required
def translations():
    return render_template('final.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)