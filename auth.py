from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import flask_login
from datetime import datetime
from . import db
from . import model
from flask_login import current_user
import os
from flask import abort


bp = Blueprint("auth", __name__)


@bp.route("/signup")
def signup():
    return render_template("auth/signup.html")


@bp.route("/signup", methods=["POST"])
def signup_post():
    email = request.form.get("email")
    username = request.form.get("username")
    password = request.form.get("password")
    
    # Check that passwords are equal
    if password != request.form.get("password_repeat"):
        flash("Sorry, passwords are different")
        return redirect(url_for("auth.signup"))
    
    # Check if the email is already at the database
    query = db.select(model.User).where(model.User.email == email)
    user = db.session.execute(query).scalar_one_or_none()
    
    if user:
        flash("Sorry, the email you provided is already registered")
        return redirect(url_for("auth.signup"))
    
    # Hash the password and create a new user 
    password_hash = generate_password_hash(password)
    new_user = model.User(email=email, user_name = username, password_encrypted=password_hash, password_salt="")
    db.session.add(new_user)
    db.session.commit()

    flask_login.login_user(new_user)
    flash("You've successfully signed up!")
    return redirect(url_for("auth.signup2"))


@bp.route("/signup2")
def signup2():
    return render_template("auth/signup2.html")

@bp.route("/signup2", methods=["POST"])
def signup_post2():
    name = request.form.get("name")
    gender = request.form.get("gender")
    gender_interests = request.form.get("sexual_orentation")
    birthday = request.form.get("birthday")
    description = request.form.get("description")
    lower_age_range = request.form.get("lower_age_range")
    higher_age_range = request.form.get("higher_age_range")
    uploaded_files = request.files.getlist("photo")  # Obtén todas las fotos subidas

    if not all([name, gender, gender_interests, birthday, lower_age_range, higher_age_range]):
        flash("All fields must be filled!")
        return redirect(url_for("auth.signup2"))

    new_user_profile = model.UserProfile(
        user_id=current_user.user_id, 
        name=name,
        gender=gender,
        birthday=birthday,
        description=description,
    )
    db.session.add(new_user_profile)
    db.session.flush()  # Para obtener el ID del usuario

    if not uploaded_files or all(file.filename == '' for file in uploaded_files):
        # Si no se subieron fotos, asigna la predeterminada
        default_photo = model.Photo(
            file_extension="png",
            profile_id=new_user_profile.user_id,
            is_photo_profile=True
        )
        db.session.add(default_photo)
    else:
        # Procesar las fotos subidas
        for i, uploaded_file in enumerate(uploaded_files):
            if uploaded_file.filename != '':
                content_type = uploaded_file.content_type
                if content_type == "image/png":
                    file_extension = "png"
                elif content_type == "image/jpeg":
                    file_extension = "jpg"
                else:
                    abort(400, f"Unsupported file type {content_type}")

                photo = model.Photo(
                    file_extension=file_extension,
                    profile_id=new_user_profile.user_id,
                    is_photo_profile=(i == 0),  # La primera es la foto de perfil
                    is_default = False
                )
                db.session.add(photo)
                db.session.flush()  # Para obtener el ID de la foto

                # Guarda el archivo en el sistema
                photo_path = photo.photo_filename()
                uploaded_file.save(photo_path)

    new_matching_preferences = model.MatchingPreferences(
        user_id=current_user.user_id,
        user_profile=new_user_profile,
        gender_interests=gender_interests,
        lower_age_range=lower_age_range,
        higher_age_range=higher_age_range,
    )
    db.session.add(new_matching_preferences)
    db.session.commit()

    flash("You've successfully signed up!")
    return redirect(url_for("auth.login"))


@bp.route("/login")
def login():
    return render_template("auth/login.html")


@bp.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email")
    password = request.form.get("password")
    
    # Get the user with that email from the database
    query = db.select(model.User).where(model.User.email == email)
    user = db.session.execute(query).scalar_one_or_none()

    if user and check_password_hash(user.password_encrypted, password):
        # The user exists and the password is correct
        flask_login.login_user(user)
        flash("You've successfully logged in!")
        return redirect(url_for("main.index"))  # Redirect to the main page
    else:
        # Wrong email and/or password
        flash("Wrong email and/or password. Please try again.")
        return redirect(url_for("auth.login"))  # Redirect back to the login form


@bp.route("/logout")
@flask_login.login_required
def logout():
    # Log out the current user
    flask_login.logout_user()
    flash("You've successfully logged out!")
    return redirect(url_for("auth.login"))
