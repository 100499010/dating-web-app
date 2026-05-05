# Dating Web App

A Flask-based dating web application developed as a university project for a Web Applications course.

The app allows users to create an account, manage their profile, set matching preferences, interact with other users, propose dates, and chat once a date has been accepted. It also includes administrator features for managing restaurant availability.

## Features

### User Authentication

- User registration, login and logout
- Age restriction for users over 18
- Duplicate email validation
- Account editing, including username, email and password

### User Profiles

- Profile creation after registration
- Editable user information
- Profile picture support
- Matching preferences based on gender, age range and orientation
- Public profile views for other users
- Support for multiple profile photos

### Matching and Interactions

- Home page showing potential matches according to user preferences
- Like and dislike functionality
- Block and unblock users
- View other users' profiles
- Super Date option to propose a date without requiring a mutual like

### Date Proposals

- Users can propose dates by selecting a restaurant and a date
- Restaurant availability checking
- Accepted, new and pending date proposal sections
- Users can accept, reject, ignore or reschedule proposals
- Blocked users cannot send date proposals to the user who blocked them

### Chats

- Chats are created once a date has been accepted
- Users can access conversations from their accepted dates
- Messages are displayed with sender information and timestamp

### Admin Features

- Administrator accounts have access to restaurant management
- Admin users can add restaurants with name, address and availability
- Restrictions are applied to prevent regular users from becoming admins through email changes

## Technologies Used

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- PyMySQL
- HTML
- CSS
- JavaScript
- Jinja2 templates

## Project Structure

```text
dating-web-app/
│
├── README.md
├── requirements.txt
├── requirements-no-versions.txt
│
└── dating/
    ├── __init__.py
    ├── auth.py
    ├── main.py
    ├── model.py
    │
    ├── templates/
    │   ├── auth/
    │   └── main/
    │
    └── static/
        ├── dating.css
        ├── dating.js
        └── photos/
