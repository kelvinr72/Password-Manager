"""

Authors: BitWizards(Kelvin Rodriguez, Shamar Barnes, Melissa Froh, Jeffrey Cauley, Jenna Rowan)
Project: CMSC 495 Capstone, Comprehensive Password Manager

Uses a flask environment to create a secure web application for generating and managing user's login
information for various applications. The user's can generate different passwords, and add, edit, 
delete, and modify their passwords in the integrated SQLAlchemy database. The user will need to 
verify their account information before accessing their information.

"""

from os import path
import base64
import secrets
import string
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required
from flask_login import logout_user, current_user, LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from Crypto.Cipher import AES
from Crypto.Cipher import DES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

# Gathered at login, used as encryption key
PASSWORD_KEY_AES = None
PASSWORD_KEY_DES = None
PASSWORD_KEY_RSA = None
PASSWORD_KEY_BLOWFISH = None


DB_NAME = "cmsc495.db"  # -- This is used when doing local testing.

bitwiz = Flask(__name__)
bitwiz.config['SECRET_KEY'] = 'WeAreVeryMagical1357913'
bitwiz.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
bitwiz.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Call the db
db = SQLAlchemy(bitwiz)


class User(UserMixin, db.Model):
    """Creates the User table in the database."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    encrypted_password = db.Column(db.String(200))
    salt = db.Column(db.String(50))
    password_recovery_question = db.Column(db.String(300))
    password_recovery_answer = db.Column(db.String(100))

    def __init__(self, username, encrypted_password, salt, password_recovery_question,
                 password_recovery_answer):
        self.username = username
        self.encrypted_password = encrypted_password
        self.salt = salt
        self.password_recovery_question = password_recovery_question
        self.password_recovery_answer = password_recovery_answer


class PasswordEntry(db.Model):
    """Creates the PasswordEntry table in the database."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    title = db.Column(db.String(100))
    app_user = db.Column(db.String(100))
    encrypted_password = db.Column(db.String(100))
    encryption_method = db.Column(db.String(100))
    associated_url = db.Column(db.String(100))
    notes = db.Column(db.String(400))
    date_created = db.Column(db.DateTime)
    date_modified = db.Column(db.DateTime)

    def __init__(self, user_id, title, app_user, encrypted_password, encryption_method, associated_url,
                 notes, date_created, date_modified):
        self.user_id = user_id
        self.title = title
        self.app_user = app_user
        self.encrypted_password = encrypted_password
        self.encryption_method = encryption_method
        self.associated_url = associated_url
        self.notes = notes
        self.date_created = date_created
        self.date_modified = date_modified


class PasswordGenerator(db.Model):
    """Creates the PasswordGenerator table in the database."""
    id = db.Column(db.Integer, primary_key=True)
    algorithim = db.Column(db.String(100))
    length = db.Column(db.Integer)
    useUppercase = db.Column(db.Boolean)
    useLowercase = db.Column(db.Boolean)
    useNumbers = db.Column(db.Boolean)
    useSpeicalChars = db.Column(db.Boolean)


class EncryptionHandler(db.Model):
    """Creates the EncryptionHandler table in the database."""
    id = db.Column(db.Integer, primary_key=True)
    algorithmType = db.Column(db.String(100))
    encryptionKey = db.Column(db.String(100))


with bitwiz.app_context():
    if not path.exists(DB_NAME):
        db.create_all()


def current_time():
    """Returns the current time formatted to year, month, date and time."""
    date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return date_time


def pad(data):
    """This function will pad the data to ensure it is a multiple of 16 bytes."""
    block_size = 16
    padding_length = block_size - (len(data) % block_size)
    padding = bytes([padding_length]) * padding_length
    return data + padding


def unpad(data):
    padding_length = data[-1]
    return data[:-padding_length]


def pad_des(data):
    """This function will pad the data to ensure it is a multiple of 8 bytes."""
    block_size = 8
    padding_length = block_size - (len(data) % block_size)
    padding = bytes([padding_length]) * padding_length
    return data + padding


def encrypt_text(text_to_encrypt, algorithm_choice):
    """This function will encrypt the provided string with the chosen algorithm."""

    # the users message will be encrypted with the chosen algorithm
    if algorithm_choice == "AES":
        # AES encryption
        # Pad the message to ensure it is a multiple of 16 bytes
        padded_message = pad(text_to_encrypt.encode())
        # create a new AES object
        aes_object = AES.new(PASSWORD_KEY_AES, AES.MODE_ECB)
        # encrypt the message
        encrypted_message = aes_object.encrypt(padded_message)
        ciphertext = base64.b64encode(encrypted_message)
        return ciphertext

    elif algorithm_choice == "DES":
        # DES encryption
        # Pad the message to ensure it is a multiple of 8 bytes
        padded_message = pad_des(text_to_encrypt.encode())
        # create a new DES object
        des_object = DES.new(PASSWORD_KEY_DES, DES.MODE_ECB)
        # encrypt the message
        encrypted_message = des_object.encrypt(padded_message)
        ciphertext = base64.b64encode(encrypted_message)
        return ciphertext

    elif algorithm_choice == "Blowfish":
        # Blowfish encryption
        key = PASSWORD_KEY_BLOWFISH  # Replace with your Blowfish key
        iv = b'12345678'  # Initialization Vector (IV) - Change as needed

        # Create a Blowfish cipher object
        cipher = Cipher(algorithms.Blowfish(key), modes.CFB(iv))
        encryptor = cipher.encryptor()

        # Pad the message using PKCS7 padding
        padder = padding.PKCS7(64).padder()
        padded_message = padder.update(
            text_to_encrypt.encode()) + padder.finalize()

        # Encrypt the padded message
        encrypted_message = encryptor.update(
            padded_message) + encryptor.finalize()
        ciphertext = base64.b64encode(encrypted_message)

        return ciphertext


def decrypt_password(ciphertext, encrypted_algorithm_choice):
    """This function will decrypt the encrypted password with the chosen algorithm."""

    algorithm_choice = decrypt_algorithm_choice(encrypted_algorithm_choice)

    if algorithm_choice == "AES":

        # AES decryption
        aes_object = AES.new(PASSWORD_KEY_AES, AES.MODE_ECB)
        decrypted_bytes = aes_object.decrypt(base64.b64decode(ciphertext))
        password = unpad(decrypted_bytes).decode('utf-8')

        return password

    elif algorithm_choice == "DES":

        # DES decryption
        des_object = DES.new(PASSWORD_KEY_DES, DES.MODE_ECB)
        decrypted_bytes = des_object.decrypt(base64.b64decode(ciphertext))
        password = unpad(decrypted_bytes).decode('utf-8')

        return password

    elif algorithm_choice == "Blowfish":
        # Blowfish decryption
        key = PASSWORD_KEY_BLOWFISH  # Replace with your Blowfish key
        iv = b'12345678'  # Initialization Vector (IV) - Change as needed

        # Create a Blowfish cipher object
        cipher = Cipher(algorithms.Blowfish(key), modes.CFB(iv))
        decryptor = cipher.decryptor()

        # Decode the ciphertext
        encrypted_message = base64.b64decode(ciphertext)

        # Decrypt the message
        decrypted_message = decryptor.update(
            encrypted_message) + decryptor.finalize()

        # Unpad the decrypted message using PKCS7 unpadding
        unpadder = padding.PKCS7(64).unpadder()
        original_message = unpadder.update(
            decrypted_message) + unpadder.finalize()

        password = original_message.decode('utf-8')

        return password


def decrypt_algorithm_choice(encrypted_algorithm_choice):
    """
    This function will decrypt the encrypted algorithm choice 
    that was used with the stored password.

    It will do so by trying each decryption method until the
    correct one is found.
    """

    # Try AES decryption
    try:
        aes_object = AES.new(PASSWORD_KEY_AES, AES.MODE_ECB)
        decrypted_bytes = aes_object.decrypt(
            base64.b64decode(encrypted_algorithm_choice))
        algorithm_choice = unpad(decrypted_bytes).decode('utf-8')
        if algorithm_choice == "AES":
            return algorithm_choice
    except:
        pass

    print()  # TESTLINE

    # Try DES decryption
    try:
        des_object = DES.new(PASSWORD_KEY_DES, DES.MODE_ECB)
        decrypted_bytes = des_object.decrypt(
            base64.b64decode(encrypted_algorithm_choice))
        algorithm_choice = unpad(decrypted_bytes).decode('utf-8')
        if algorithm_choice == "DES":
            return algorithm_choice
    except:
        pass

    # # Try RSA decryption
    # cipher_rsa = PKCS1_OAEP.new(PASSWORD_KEY_RSA)
    # decrypted_bytes = cipher_rsa.decrypt(base64.b64decode(encrypted_algorithm_choice))
    # algorithm_choice = unpad(decrypted_bytes).decode('utf-8')
    # if algorithm_choice == "RSA":
    #     return algorithm_choice


login_manager = LoginManager()
login_manager.login_view = 'login'

# User Loader for Login Manaager


@login_manager.user_loader
def load_user(user_id):
    """Returns the user's id."""
    return User.query.get(user_id)


@bitwiz.route('/register', methods=['POST', 'GET'])
def index_page():
    """Renders the index page and handles new user registration."""
    # username = None
    # password = None
    # salt = None
    # question = None
    # answer = None

    if request.method == 'POST':
        new_username = request.form.get('username')
        new_password = request.form.get('password')
        new_salt = request.form.get('salt')
        new_question = request.form.get('question')
        new_answer = request.form.get('answer')

        new_rec = User(new_username, new_password,
                       new_salt, new_question, new_answer)
        db.session.add(new_rec)
        db.session.commit()
        login_user(new_rec, remember=True)

        # TO DO -> FIGURE OUT WHAT PAGE SHOULD COME NEXT
        return redirect(url_for('userguide'))

    return render_template('index.html', timestamp=current_time(), title='CMST 495 - BitWizards')


@bitwiz.route('/PasswordGenerator', methods=['POST', 'GET'])
def passgeneration():
    """Renders the password generator page, and handles generating and populating random passwords."""
    temppassword = ""
    if request.method == 'POST':
        # Get values from checkbox and slider on password generator page
        uppercase = request.form.get('uppercase')
        lowercase = request.form.get('lowercase')
        numbers = request.form.get('numbers')
        symbols = request.form.get('symbols')
        length = int(request.form.get('length'))

        if uppercase is None and lowercase is None and numbers is None and symbols is None:
            flash('Please select at least one option before generating a password.')

        else:
            temppassword = generate_password(
                uppercase, lowercase, numbers, symbols, length)

    return render_template('PasswordGenerator.html', passwordOutput=temppassword,
                           timestamp=current_time(), title='CMST 495 - BitWizards')


def generate_password(uppercase, lowercase, numbers, symbols, length):
    """ Join characters to form random secure password using user specified characters,
    returns the password.

    Args:
        uppercase: Flag for if uppercase is included in the set of characters
        lowercase: Flag for if lowercase is included in the set of characters
        numbers: Flag for if digits are included in the set of characters
        symbols: Flag for if symbols are included in the set of characters
        length: The lenght of the password to be generated
    Returns:
        securepassword: A password formed using the secrets module to the specified length ans ascii set.

    """
    alphabet = ""
    if uppercase:
        alphabet += string.ascii_uppercase

    if lowercase:
        alphabet += string.ascii_lowercase

    if numbers:
        alphabet += string.digits

    if symbols:
        alphabet += string.punctuation

    securepassword = ''.join(secrets.choice(alphabet) for i in range(length))
    return securepassword


@bitwiz.route('/slider_update', methods=['POST', 'GET'])
def slider():
    """Handles the password generator slider value updating on new input from user."""
    received_data = request.data
    return received_data


@bitwiz.route('/', methods=['GET', 'POST'])
def login():
    """Renders the login page, and handles the user authentication."""
    if request.method == 'POST':
        # Get values entered in login

        username = request.form['username']
        password = request.form['password']

        # Set the global password key
        global PASSWORD_KEY_AES
        global PASSWORD_KEY_DES
        global PASSWORD_KEY_RSA
        global PASSWORD_KEY_BLOWFISH

        PASSWORD_KEY_AES = pad(str.encode(request.form['password']))
        PASSWORD_KEY_DES = pad_des(str.encode(request.form['password']))
        PASSWORD_KEY_RSA = pad(str.encode(
            request.form['password']))  # NEEDS ADJUSTMENT
        PASSWORD_KEY_BLOWFISH = str.encode(request.form['password'])

        log_user = User.query.filter_by(username=username).first()

        # Check for existing user before logging in
        if log_user:
            if log_user.encrypted_password == password:
                login_user(log_user, remember=True)
                return redirect(url_for('userguide'))
            else:
                flash('Incorrect Password')
        else:
            flash('User Not Found')

        # Add the logic for Login

    return render_template('login.html', timestamp=current_time(), title='CMST 495 - BitWizards')


@bitwiz.route('/pass_entry', methods=['GET', 'POST'])
@login_required
def pass_entry():
    """Renders the password entry page, and handles the management of the user's passwords."""
    if request.method == 'POST':
        app_desc_name = request.form['application']
        app_user = request.form['username']
        app_password = request.form['password']
        app_algorithm = request.form['algorithm']

        curruser_id = current_user.id

        enc_pass = encrypt_text(app_password, app_algorithm)
        enc_algorithm = encrypt_text(app_algorithm, app_algorithm)

        new_pass = PasswordEntry(curruser_id, app_desc_name, app_user,
                                 enc_pass, enc_algorithm, None, None, datetime.now(), datetime.now())
        db.session.add(new_pass)
        db.session.commit()

        return redirect(url_for('next_page', user_val=curruser_id))

    return render_template('PasswordEntry.html', timestamp=current_time(),
                           title='CMST 495 - BitWizards - Create Password')


@bitwiz.route('/PrivacyPolicy', methods=['GET', 'POST'])
def privacypage():
    """Renders the privacy page, which provides the user information about how information is stored securely."""
    return render_template('PrivacyPolicy.html', timestamp=current_time(), title='BitWizards Privacy Page')


@bitwiz.route('/UserGuide', methods=['GET', 'POST'])
def userguide():
    """
    Renders the user guide page, which provides the user information about how to use the program.
    """
    return render_template('UserGuide.html', timestamp=current_time(), title='BitWizards User Guide')


@bitwiz.route('/master_reset', methods=['POST', 'GET'])
def master_reset():
    """Renders the ResetMasterPass page, and handles authentication for resetting the master password."""
    if request.method == 'POST':

        # Get values entered in login
        form_user = request.form['username']

        check_user = User.query.filter_by(username=form_user).first()

        if check_user:
            logged_user = check_user.username
            logged_question = check_user.password_recovery_question
            return redirect(url_for('answer_question', sendUser=logged_user, sendQuestion=logged_question))
        else:
            flash('User Not Found. Please try again.')

    return render_template('reset.html', timestamp=current_time(), title='Enter Username to Reset')


@bitwiz.route('/answer', methods=['POST', 'GET'])
def answer_question():
    """Renders the answer page, and handles updating the user's master password after verification."""
    if request.method == 'POST':

        form_user = request.form['sendUser']
        form_answer = request.form['security_answer']
        form_pass_1 = request.form['firstPassword']
        form_pass_2 = request.form['secondPassword']

        update_user = User.query.filter_by(username=form_user).first()

        if update_user:
            if update_user.password_recovery_answer == form_answer:
                if form_pass_1 == form_pass_2:
                    update_user.encrypted_password = form_pass_1
                    db.session.commit()
                    return redirect(url_for('next_page'))
                else:
                    flash('Passwords did not match. Try again.')
                    return redirect(url_for('master_reset'))
            else:
                flash('Incorrect Security Answer.')
                return redirect(url_for('master_reset'))
        else:
            flash('User does not exist')

    return render_template('answer.html', timestamp=current_time(), title='Enter New Password')


@bitwiz.route('/next', methods=['GET', 'POST'])
@login_required
def next_page():
    """Renders the next page, and shows decrypted password information."""
    user_record = User.query.filter_by(id=current_user.id).all()
    password_records = PasswordEntry.query.filter_by(
        user_id=current_user.id).all()

    plain_text = ""
    for record in password_records:
        encryption_method = record.encryption_method
        password = record.encrypted_password
        record.plain_text = decrypt_password(password, encryption_method)
        plain_text = record.plain_text

    return render_template('next.html', user_record=user_record,
                           password_records=password_records, plain_text=plain_text,
                           timestamp=current_time(), title='Database Lookup')


@bitwiz.route('/ModifyPassword', methods=['GET', 'POST'])
@login_required
def modify_password():
    """Renders the modify password page, and receives stored data the user selected to modify."""
    if request.method == 'GET':
        og_title = request.args.get('title')
        og_user = request.args.get('username')
        og_pass = request.args.get('password')
        og_id = request.args.get('record_id')

    if request.method == 'POST':

        mod_id = int(request.form.get('record_id'))
        mod_title = request.form.get('title')
        mod_user = request.form.get('username')
        mod_pass = request.form.get('password')
        mod_algo = request.form.get('algorithm')
        mod_url = request.form.get('url')
        mod_notes = request.form.get('notes')

        if 'modify' in request.form:
            encrypt_pass = encrypt_text(mod_pass, mod_algo)
            update_pass = PasswordEntry.query.filter_by(id=mod_id).first()

            if update_pass:
                update_pass.title = mod_title
                update_pass.app_user = mod_user
                update_pass.encrypted_password = encrypt_pass
                update_pass.associated_url = mod_url
                update_pass.notes = mod_notes
                update_pass.date_modified = datetime.now()

                db.session.commit()
                flash('Password entry modified successfully.')

        elif 'delete' in request.form:
            # Handle deletion logic here
            password_entry = PasswordEntry.query.get(mod_id)

            if password_entry:
                # Check if the password entry belongs to the currently logged-in user
                if password_entry.user_id == current_user.id:
                    # Delete the password entry from the database
                    db.session.delete(password_entry)
                    db.session.commit()
                    flash('Password entry deleted successfully.')
                else:
                    flash('Unauthorized to delete this password entry.')
            else:
                flash('Password entry not found.')

        return redirect(url_for('next_page'))

    return render_template('ModifyPassword.html', application=og_title, username=og_user, record_id=og_id,
                           password=og_pass, timestamp=current_time(), title='Modify Entry')


@bitwiz.route('/logout')
@login_required
def logout():
    """Calls helper function to log out, and redirects to the login page after session is terminated."""
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))


login_manager.init_app(bitwiz)

if __name__ == '__main__':
    bitwiz.run(debug=True)  # TESTLINE
