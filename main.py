import datetime
from datetime import date, datetime, timezone
import dateutil.tz
from flask import abort, Blueprint, render_template, request, redirect, url_for, flash, session
from . import model, db
import flask_login
from flask_login import current_user
from werkzeug.utils import secure_filename
import os
from sqlalchemy.orm import aliased
from sqlalchemy import or_, and_
from .model import Chat, Restaurant, DateProposal, ProposalStatus, UserProfile
from flask import jsonify
from werkzeug.security import check_password_hash, generate_password_hash


bp = Blueprint("main", __name__)


@bp.route('/')
@flask_login.login_required
def index():
    today = date.today()

    current_user_profile = db.session.get(model.UserProfile, current_user.user_id)

    # Obtain matching preferences of current user
    matching_preferences = current_user_profile.matching_preferences
    db.session.refresh(current_user_profile.matching_preferences)

    # Convert age ranges into integers
    lower_age = int(matching_preferences.lower_age_range)
    higher_age = int(matching_preferences.higher_age_range)

    # Compute maximum and minimum birthday
    min_birthdate = date(today.year - higher_age, today.month, today.day)
    max_birthdate = date(today.year - lower_age, today.month, today.day)

    # Obbtain ids
    filtered_users = (
        db.session.query(model.UserProfile.user_id)
        .filter(
            model.UserProfile.user_id != current_user.user_id,  # Exclude actual user
            # Select by gender
            or_(
                (matching_preferences.gender_interests == model.SexualOrentation.Both),
                (matching_preferences.gender_interests == model.SexualOrentation.Man and model.UserProfile.gender == model.SexualOrentation.Man),
                (matching_preferences.gender_interests == model.SexualOrentation.Woman and model.UserProfile.gender == model.SexualOrentation.Woman),
            ),
            # Select by age range
            model.UserProfile.birthday.between(min_birthdate, max_birthdate)
        )
        .all()
    )

    if not filtered_users:
        return render_template('main/index.html', message="No users found.")

    filtered_user_ids = [user_id for user_id, in filtered_users]
    session['filtered_user_ids'] = filtered_user_ids

    # Ensure user_index is within valid range
    user_index = session.get('user_index', 0) % len(filtered_user_ids)
    displayed_user_id = filtered_user_ids[user_index]

    # Current displayed user
    displayed_user = db.session.get(model.UserProfile, displayed_user_id)

    age = today.year - displayed_user.birthday.year - (
        (today.month, today.day) < (displayed_user.birthday.month, displayed_user.birthday.day)
    )

    profile_photo = db.session.query(model.Photo).filter_by(
        profile_id=displayed_user.user_id,
        is_photo_profile=True
    ).first()

    # Check likes and blocks for the showed user of the loged user 
    is_liking = db.session.query(model.LikingAssociation).filter_by(
        user_likes_id=current_user.user_id,
        likes_user_id=displayed_user.user_id
    ).first()
    like_button = "dislike" if is_liking else "like"

    is_blocking = db.session.query(model.BlockedAssociation).filter_by(
        user_blocks_id=current_user.user_id,
        user_is_blocked_id=displayed_user.user_id
    ).first()
    block_button = "unblock" if is_blocking else "block"

    return render_template(
        'main/index.html',
        user_profile=displayed_user,
        age=age,
        user_index=user_index + 1,
        total_users=len(filtered_user_ids),
        block_button=block_button,
        like_button=like_button,
        profile_photo=profile_photo 
    )


@bp.route('/next_user', methods=['POST'])
@flask_login.login_required
def next_user():
    if 'filtered_user_ids' not in session or not session['filtered_user_ids']:
        flash("No users to display. Please adjust your matching preferences.")
        return redirect(url_for('main.index'))

    # Increment index of the user showed
    session['user_index'] = (session.get('user_index', 0) + 1) % len(session['filtered_user_ids'])
    return redirect(url_for('main.index'))


@bp.route("/profile/<int:user_id>")
@flask_login.login_required
def profile(user_id):
    user_profile = db.session.get(model.UserProfile, user_id)
    if not user_profile:
        flash("User profile not found.", "error")
        return redirect(url_for('main.index'))

    # Compute user age
    today = date.today()
    age = today.year - user_profile.birthday.year - (
        (today.month, today.day) < (user_profile.birthday.month, user_profile.birthday.day)
    )

    # Filter no profile photos
    user_photos = [
        {
            "id": photo.id,
            "file_extension": photo.file_extension
        }
        for photo in user_profile.photos if not photo.is_photo_profile
    ]

    # Actual photo index
    current_photo_index = session.get(f'current_photo_index_{user_id}', 0)
    if current_photo_index >= len(user_photos):
        current_photo_index = 0

    session[f'current_photo_index_{user_id}'] = current_photo_index

    current_photo = user_photos[current_photo_index] if user_photos else None

    current_user_profile = current_user.user_profile
    can_propose_date = False

    # Check users like each other
    if user_profile.user in current_user_profile.user.user_likes and current_user_profile.user in user_profile.user.user_likes:
        can_propose_date = True

    return render_template(
        'main/profile.html',
        user_profile=user_profile,
        current_photo=current_photo,
        user_photos=user_photos,
        age=age,
        can_propose_date=can_propose_date  # ATo show the button 
    )


@bp.route("/next_photo/<int:user_id>")
@flask_login.login_required
def next_photo(user_id):
    # Obtener el perfil del usuario
    user_profile = db.session.get(model.UserProfile, user_id)
    if not user_profile:
        flash("User profile not found.", "error")
        return redirect(url_for('main.index'))

    # Obtain user photos
    user_photos = [
        {
            "id": photo.id,
            "file_extension": photo.file_extension
        }
        for photo in user_profile.photos
    ]

    if not user_photos:
        flash("No photos available.", "error")
        return redirect(url_for('main.profile', user_id=user_id))

    # CUrrent index photo
    current_photo_index = session.get(f'current_photo_index_{user_id}', 0)
    current_photo_index = (current_photo_index + 1) % len(user_photos)

    # Save new index
    session[f'current_photo_index_{user_id}'] = current_photo_index

    return redirect(url_for('main.profile', user_id=user_id))


@bp.route('/edit_profile_photo/<int:user_id>', methods=['POST'])
@flask_login.login_required
def edit_profile_photo(user_id):
    user = model.User.query.get_or_404(user_id)
    user_profile = user.user_profile

    if 'new_profile_photo' in request.files:
        new_profile_photo = request.files['new_profile_photo']
        if new_profile_photo and new_profile_photo.filename != '':
            content_type = new_profile_photo.content_type
            if content_type in ['image/png', 'image/jpeg']:
                file_extension = 'png' if content_type == 'image/png' else 'jpg'

                # Delete profile picture
                old_profile_photo = next(
                    (photo for photo in user_profile.photos if photo.is_photo_profile), None
                )
                if old_profile_photo and not old_profile_photo.is_default:
                    old_path = old_profile_photo.photo_filename()
                    if old_path.exists():
                        old_path.unlink() 
                    db.session.delete(old_profile_photo) 

                # Save new profile picture
                photo = model.Photo(
                    file_extension=file_extension,
                    profile_id=user_profile.user_id,
                    is_photo_profile=True,
                    is_default=False
                )
                db.session.add(photo)
                db.session.flush()
                new_path = photo.photo_filename()
                new_profile_photo.save(new_path)
        else:
            # Default profile picture
            default_photo = next(
                (photo for photo in user_profile.photos if photo.is_photo_profile and photo.is_default), None
            )
            if not default_photo:
                default_photo = model.Photo(
                    file_extension='png',
                    profile_id=user_profile.user_id,
                    is_photo_profile=True,
                    is_default=True
                )
                db.session.add(default_photo)

    db.session.commit()
    flash('Profile photo updated successfully!')

    return redirect(url_for('main.edit_profile', user_id=user_id))


@bp.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_profile(user_id):
    user = model.User.query.get_or_404(user_id)
    user_profile = user.user_profile

    if request.method == 'POST':
        # Process changes in UserProfile
        if 'name' in request.form:
            user_profile.name = request.form['name']
        if 'gender' in request.form:
            user_profile.gender = request.form['gender']
        if 'birthday' in request.form:
            user_profile.birthday = request.form['birthday']
        if 'description' in request.form:
            user_profile.description = request.form['description']

        # Process changes in photos
        uploaded_files = request.files.getlist('photo')
        if uploaded_files:
            for i, uploaded_file in enumerate(uploaded_files):
                if uploaded_file.filename != '':
                    # Save new photos
                    content_type = uploaded_file.content_type
                    if content_type in ['image/png', 'image/jpeg']:
                        file_extension = 'png' if content_type == 'image/png' else 'jpg'
                        photo = model.Photo(
                            file_extension=file_extension,
                            profile_id=user_profile.user_id,
                            is_photo_profile=(i == 0)  # first photo profile picture
                        )
                        db.session.add(photo)
                        db.session.flush()
                        photo_path = photo.photo_filename()
                        uploaded_file.save(photo_path)

        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('main.profile', user_id=user_id))

    return render_template('main/edit_profile.html', user=user, user_profile=user_profile)


@bp.route('/edit_matching_preferences/<int:user_id>', methods=['GET','POST'])
@flask_login.login_required
def edit_matching_preferences(user_id):
    user = model.User.query.get_or_404(user_id)
    user_profile = user.user_profile
    matching_preferences= user_profile.matching_preferences

    if request.method == 'POST':
        # Changes in MatchingPreferences
       # if 'gender_interests' in request.form:
        matching_preferences.gender_interests = request.form["gender_interests"]
        if 'lower_age_range' in request.form:
            matching_preferences.lower_age_range = request.form['lower_age_range']
        if 'higher_age_range' in request.form:
            matching_preferences.higher_age_range = request.form['higher_age_range']

        db.session.commit()
        flash('Matching Preferences updated successfully!')
        return redirect(url_for('main.index'))
    
    return render_template('main/edit_matching_preferences.html', matching_preferences=matching_preferences, user=user)


@bp.route('/edit_account/<int:user_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_account(user_id):
    user = model.User.query.get_or_404(user_id)

    if request.method == 'POST':
        password = request.form.get("password")

        if not check_password_hash(user.password_encrypted, password):
            flash("The current password is incorrect. Please try again.")
            return redirect(url_for('main.edit_account', user_id=user_id))

        new_password = request.form.get('new_password')
        new_password_rep = request.form.get('new_password_rep')

        # CHeck password match
        if new_password != new_password_rep:
            flash("Sorry, the new passwords don't match.")
            return redirect(url_for('main.edit_account', user_id=user_id))

        new_email = request.form.get('email')

        # Check change email based on the sufix
        current_email_is_admin = user.email.endswith('@admin.sobera')
        new_email_is_admin = new_email.endswith('@admin.sobera')

        if current_email_is_admin and not new_email_is_admin:
            flash("You cannot change from an @admin.sobera email to a non-@admin.sobera email.")
            return redirect(url_for('main.edit_account', user_id=user_id))

        if not current_email_is_admin and new_email_is_admin:
            flash("You cannot change to an @admin.sobera email.")
            return redirect(url_for('main.edit_account', user_id=user_id))

        # Update email
        if new_email:
            user.email = new_email

        # Update user name
        if 'user_name' in request.form:
            user.user_name = request.form['user_name']

        # Update new password
        if new_password:
            password_hash = generate_password_hash(new_password)
            user.password_encrypted = password_hash
            user.password_salt = "" 

        db.session.commit()
        flash('Account updated successfully!')
        return redirect(url_for('main.index', user_id=user_id))

    return render_template('main/edit_account.html', user=user)


@bp.route('/dates', methods=['GET'])
@flask_login.login_required
def view_dates():
    user_id = flask_login.current_user.user_id
    user_profile = db.session.get(UserProfile, user_id)

    # Check updates values from data base
    db.session.refresh(user_profile)

    # Accepted dates
    accepted_dates = [
        proposal for proposal in user_profile.sent_proposals
        if proposal.status == ProposalStatus.accepted
    ] + [
        proposal for proposal in user_profile.received_proposals
        if proposal.status == ProposalStatus.accepted
    ]

    # Ignored dates
    ignored_dates = [
        proposal for proposal in user_profile.received_proposals
        if proposal.status == ProposalStatus.ignored
    ]

    # Pending dates
    pending_dates = [
        proposal for proposal in user_profile.received_proposals
        if proposal.status == ProposalStatus.proposed
    ]

    # Rescheduled dates
    reschedule_dates = [
        proposal for proposal in user_profile.received_proposals
        if proposal.status == ProposalStatus.reschedule
    ]

    existing_chats = {}
    for date in accepted_dates:
        other_user_id = date.sender_profile.user_id if date.sender_profile.user_id != user_id else date.receiver_profile.user_id
        chat = db.session.query(Chat).filter(
            or_(
                and_(Chat.user1_id == user_id, Chat.user2_id == other_user_id),
                and_(Chat.user1_id == other_user_id, Chat.user2_id == user_id)
            )
        ).first()
        existing_chats[date.id] = chat  # None if no chat exists, or the chat instance if it does


    return render_template(
        'main/date.html',
        user_profile=user_profile,
        accepted_dates=accepted_dates,
        ignored_dates=ignored_dates,
        pending_dates=pending_dates,
        reschedule_dates=reschedule_dates,
        existing_chats = existing_chats
    )


@bp.route('/date_action/<int:date_id>', methods=['POST'])
@flask_login.login_required
def handle_date_action(date_id):
    action = request.form.get('action')
    response_message = request.form.get('response_message', '').strip()
    
    date = DateProposal.query.get_or_404(date_id)
    
    # Update date status
    if action == 'accept':
        date.status = ProposalStatus.accepted
    elif action == 'reject':
        date.status = ProposalStatus.rejected
    elif action == 'reschedule':
        return redirect(url_for('main.reschedule_date', date_id=date_id))
    elif action == 'ignore':
        date.status = ProposalStatus.ignored

    # Save message and time response
    if response_message:
        date.opt_text_response = response_message
    date.timestamp_answer = datetime.now()

    db.session.commit()
    flash("Successfull action.", "success")

    return redirect(url_for('main.view_dates'))


@bp.route('/propose_date/<int:user_id>', methods=['GET', 'POST'])
@flask_login.login_required
def propose_date(user_id):
    receiver = UserProfile.query.filter_by(user_id=user_id).first_or_404()
    restaurants = Restaurant.query.all()

    if request.method == 'POST':
        date_day = request.form.get('date_day')
        restaurant_id = request.form.get('restaurant_id')
        optional_message = request.form.get('optional_message', '').strip()

        restaurant = Restaurant.query.get_or_404(restaurant_id)
        target_date = date.fromisoformat(date_day)
        sender = flask_login.current_user

        # Checks future dates
        if target_date < date.today():
            flash('You cannot propose a date in the past.', 'danger')
            return redirect(url_for('main.propose_date', user_id=user_id))

        # Check if the receiver blocks the sender
        if (sender in receiver.user.user_blocks):
            # New date proposal automatically rejected
            proposal = DateProposal(
                date_day=target_date,
                status=ProposalStatus.rejected,
                timestamp_proposal = datetime.now(timezone.utc),
                opt_text_message=f"{optional_message} - Restaurant: {restaurant.name}" if optional_message else f"Restaurant: {restaurant.name}",
                sender_id=sender.user_profile.user_id,
                receiver_id=receiver.user_id,
                restaurant_id=restaurant.id
            )
            db.session.add(proposal)
            db.session.commit()
            return redirect(url_for('main.profile', user_id=receiver.user_id))

        # Check restaurant availability
        if restaurant.is_fully_booked(target_date):
            flash(f'Restaurant {restaurant.name} is fully booked on {target_date}.', 'danger')
            return redirect(url_for('main.propose_date', user_id=user_id))

        # Create a Date proposal
        proposal = DateProposal(
            date_day=target_date,
            status=ProposalStatus.proposed,
            timestamp_proposal = datetime.now(timezone.utc),
            opt_text_message=f"{optional_message} - Restaurant: {restaurant.name}" if optional_message else f"Restaurant: {restaurant.name}",
            sender_id=sender.user_profile.user_id,
            receiver_id=receiver.user_id,
            restaurant_id=restaurant.id
        )

        db.session.add(proposal)
        db.session.commit()

        flash('Date proposal sent successfully!', 'success')
        return redirect(url_for('main.profile', user_id=receiver.user_id))

    return render_template('main/propose_date.html', user_profile=receiver, restaurants=restaurants)


@bp.route('/reschedule_date/<int:date_id>', methods=['GET', 'POST'])
@flask_login.login_required
def reschedule_date(date_id):
    date_proposal = DateProposal.query.get_or_404(date_id)

    if flask_login.current_user.user_id != date_proposal.receiver_id:
        flash("NOt enough permissions to modify this date.", "danger")
        return redirect(url_for('main.view_dates'))

    restaurants = Restaurant.query.all()

    if request.method == 'POST':
        date_day = request.form.get('date_day')
        restaurant_id = request.form.get('restaurant_id')
        optional_message = request.form.get('optional_message', '')

        if not date_day or not restaurant_id:
            flash("Select a date and a restaurant.", "danger")
            return redirect(url_for('main.reschedule_date', date_id=date_id))

        restaurant = Restaurant.query.get_or_404(restaurant_id)
        target_date = datetime.fromisoformat(date_day)

        if target_date < datetime.today():
            flash("You cannot choose a date in the past.", "danger")
            return redirect(url_for('main.reschedule_date', date_id=date_id))

        if restaurant.is_fully_booked(target_date):
            flash(f"Restaurant {restaurant.name} is fully booked on the selected date.", "danger")
            return redirect(url_for('main.reschedule_date', date_id=date_id))

        # Update restaurant availability for previous date
        if date_proposal.status != ProposalStatus.rejected:
            old_restaurant = Restaurant.query.get(date_proposal.restaurant_id)
            if old_restaurant:
                old_restaurant.capacity += 1

        # Reduce restaurant availability
        if not restaurant.is_fully_booked(target_date):
            restaurant.capacity -= 1

        # Update the date
        date_proposal.date_day = target_date
        date_proposal.restaurant_id = restaurant_id
        date_proposal.status = ProposalStatus.reschedule

        # Change sender and receiver so the new proposal goes back to the original sender
        date_proposal.sender_id, date_proposal.receiver_id = date_proposal.receiver_id, date_proposal.sender_id

        if optional_message:
            date_proposal.opt_text_response = f"{optional_message} - RESCHEDULE"
        else:
            date_proposal.opt_text_response = "- RESCHEDULE"

        db.session.commit()

        flash("Date programmed with success.", "success")

        return redirect(url_for('main.view_dates'))

    return render_template(
        'main/propose_date.html',
        user_profile=date_proposal.sender_profile,
        restaurants=restaurants,
        change_date=True,
        date_proposal=date_proposal
    )


@bp.route('/view_restaurants/<int:user_id>')
@flask_login.login_required
def view_restaurants(user_id):
    restaurants = Restaurant.query.all()
    # Only admins can add new restaurants
    can_add_restaurant = current_user.email.endswith('@admin.sobera')

    return render_template('main/restaurants.html', restaurants=restaurants, user_id=user_id, can_add_restaurant=can_add_restaurant)


@bp.route('/check_availability/<int:restaurant_id>/<string:selected_date>', methods=['GET'])
@flask_login.login_required
def check_availability(restaurant_id, selected_date):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    target_date = datetime.fromisoformat(selected_date)
    
    # Use is_fully_booked method to check restaurant availability
    available = not restaurant.is_fully_booked(target_date)
    
    if available:
        # If availavility, calculate the number of free tables
        booked_dates = db.session.query(DateProposal).filter(
            DateProposal.restaurant_id == restaurant_id,
            DateProposal.date_day == target_date,
            DateProposal.status.in_([
                ProposalStatus.proposed,
                ProposalStatus.accepted,
                ProposalStatus.ignored,
                ProposalStatus.reschedule
            ])
        ).count()
        available_tables = restaurant.capacity - booked_dates
    else:
        available_tables = 0
    
    return jsonify({
        "available": available,
        "tables": available_tables
    })


@bp.route('/add_restaurant', methods=['GET', 'POST'])
@flask_login.login_required
def add_restaurant():
    # Only admin users can add new restaurants
    if not current_user.email.endswith('@admin.sobera'):
        flash('Access denied: You do not have permission to add restaurants.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        capacity = int(request.form.get('capacity'))

        if not name or not location or capacity <= 0:
            flash('Invalid data. Please complete all fields correctly.', 'danger')
            return redirect(url_for('main.add_restaurant'))

        new_restaurant = Restaurant(name=name, location=location, capacity=capacity)
        db.session.add(new_restaurant)
        db.session.commit()

        flash('Restaurant added successfully!', 'success')
        return redirect(url_for('main.view_restaurants', user_id=current_user.user_profile.user_id))

    return render_template('main/add_restaurant.html')


@bp.route("/block/<int:user_id>", methods=["POST"])
@flask_login.login_required
def block(user_id):
    user = db.session.get(model.User, user_id)

    if not user:
        abort(404, "User id {} doesn't exist.".format(user_id))
    
    if current_user.user_id==user.user_id or flask_login.current_user in user.user_is_blocked:
        abort(403, "User id {} cannot block itself or start blocking someone that is already blocking.".format(user_id))

    # Add the user to the list of blocked users
    user.user_is_blocked.append(flask_login.current_user)

    db.session.commit()

    return redirect(url_for('main.index'))


@bp.route("/like/<int:user_id>", methods=["POST"])
@flask_login.login_required
def like(user_id):
    user = db.session.get(model.User, user_id)

    if not user:
        abort(404, "User id {} doesn't exist.".format(user_id))
    
    if current_user.user_id==user.user_id or flask_login.current_user in user.likes_user:
        abort(403, "User id {} cannot like itself or start liking someone that is already liking.".format(user_id))

    # Add the user to the list of liked users  
    user.likes_user.append(flask_login.current_user)
    db.session.commit()

    return redirect(url_for('main.index'))


@bp.route("/unblock/<int:user_id>", methods=["POST"])
@flask_login.login_required
def unblock(user_id):
    user = db.session.get(model.User, user_id)

    if not user:
        abort(404, "User id {} doesn't exist.".format(user_id))
    
    if current_user.user_id==user.user_id or flask_login.current_user not in user.user_is_blocked:
        abort(403, "User id {} cannot unblock itself or start unblocking someone that is already unblocking.".format(user_id))

    # Remove the user to the list of blocked users
    user.user_is_blocked.remove(flask_login.current_user)
    db.session.commit()

    return redirect(url_for('main.index'))


@bp.route("/dislike/<int:user_id>", methods=["POST"])
@flask_login.login_required
def dislike(user_id):
    user = db.session.get(model.User, user_id)

    if not user:
        abort(404, "User id {} doesn't exist.".format(user_id))
    
    if current_user.user_id==user.user_id or flask_login.current_user not in user.likes_user:
        abort(403, "User id {} cannot dislike itself or start unliking someone that is already unliking.".format(user_id))

    # Remove the user to the list of liked users
    user.likes_user.remove(flask_login.current_user)
    db.session.commit()

    return redirect(url_for('main.index'))


@bp.route('/view_chats', methods=['GET'])
@flask_login.login_required
def view_chats(): 
    # Get chats 
    chats = (
        db.session.query(model.Chat)
        .outerjoin(model.Chat.texts)  
        .filter(or_(
            (model.Chat.user1_id == current_user.user_id), 
            (model.Chat.user2_id == current_user.user_id)))
        .all()
        )

    user_profile= []

    # To show last message 
    last_text=[]

    for chat in chats:
        lastest_text = (
            db.session.query(model.Text)
            .filter(model.Text.chat_id == chat.id)
            .order_by(model.Text.timestamp.desc())
            .first())    
        
        last_text.append(lastest_text)

        if chat.user1_id != current_user.user_id:
            user = db.session.get(model.UserProfile, chat.user1_id)
            user_profile.append(user)

        elif chat.user2_id != current_user.user_id:
            user = db.session.get(model.UserProfile, chat.user2_id)
            user_profile.append(user)   

    return render_template('main/list_chat.html', chats=chats,  last_text=last_text, user_profile=user_profile) 


@bp.route("/chat/<int:chat_id>/<int:user_id>")
@flask_login.login_required
def get_unique_chat(chat_id, user_id):
    chat = db.session.get(model.Chat, chat_id)
    selected_user = db.session.get(model.UserProfile, user_id)
 
    texts = (
        db.session.query(model.Text)
        .filter(
            model.Text.chat_id == chat_id)
        .order_by(model.Text.timestamp.asc())
        .all()
        )

    return render_template("main/chat.html", chat=chat, texts=texts, selected_user= selected_user)


@bp.route("/text/<int:user_id>", methods=["POST"]) 
@flask_login.login_required
def text_text(user_id):
    text_sended = request.form.get("text_sended")
    chat_id = request.form.get("chat_id")

    if not text_sended:
        flash("The contennt of the text cannot be empty.")
        return redirect(url_for("main.get_unique_chat"))

    new_text = model.Text(
        chat_id=chat_id ,
        sender=current_user, 
        text=text_sended,)

    db.session.add(new_text)
    db.session.commit()

    return redirect(url_for("main.get_unique_chat", chat_id=chat_id, user_id= user_id))


@bp.route('/create_chat/<int:user_id>', methods=['POST'])
@flask_login.login_required
def create_chat(user_id):

    existing = db.session.query(model.Chat).filter(
        or_(
            and_(model.Chat.user1_id == user_id, model.Chat.user2_id == current_user.user_id), 
            and_(model.Chat.user1_id == current_user.user_id, model.Chat.user2_id == user_id))
    ).first()

    if existing:
        return redirect(url_for("main.get_unique_chat", chat_id= existing.id, user_id= user_id))
    else:
        # Create a chat
        chat = model.Chat(user1_id=user_id, 
                          user2_id=current_user.user_id, )

        db.session.add(chat)
        db.session.commit()

        return redirect(url_for("main.get_unique_chat", chat_id= chat.id, user_id= user_id))
