import streamlit as st
from datetime import datetime
import requests
import json
import http.client
from ics import Calendar
import base64
from pathlib import Path
from pymongo import MongoClient
import hashlib
from urllib.parse import quote_plus  # To escape username and password

# MongoDB Atlas connection details
MONGO_USERNAME = quote_plus("taskpriority123")  # Replace with your MongoDB username
MONGO_PASSWORD = quote_plus("SNL@12345678")  # Replace with your MongoDB password
MONGO_CLUSTER_URL = "taskprio.wjrwb.mongodb.net"  # Replace with your MongoDB cluster URL
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER_URL}/test?retryWrites=true&w=majority"
DB_NAME = "TaskPrio"  # Your database name
COLLECTION_NAME = "users"  # Collection to store users' credentials

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db[COLLECTION_NAME]

# Function to hash passwords before storing in the database
# def hash_password(password):
#     return hashlib.sha256(password.encode()).hexdigest()


class CanvasAPI:
    BASE_URL = "https://uta.instructure.com/api/v1"

    @staticmethod
    def get_headers(api_token):
        return {
            'Authorization': f'Bearer {api_token}',
        }

    @classmethod
    def get_courses(cls, api_token):
        conn = http.client.HTTPSConnection("uta.instructure.com")
        conn.request("GET", "/api/v1/courses", '', cls.get_headers(api_token))
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        return data  # Return raw JSON string

    @classmethod
    def extract_calendar_urls(cls, api_token):
        courses_data = cls.get_courses(api_token)

        if not courses_data:
            return []

        # Parse the JSON data
        courses = json.loads(courses_data)
        calendar_urls = [course['calendar']['ics'] for course in courses if 'calendar' in course]
        return calendar_urls

    @classmethod
    def get_calendar_events(cls, api_token):
        calendar_urls = cls.extract_calendar_urls(api_token)
        events = []

        for url in calendar_urls:
            response = requests.get(url)
            if response.status_code == 200:
                calendar = Calendar(response.text)
                events.extend(calendar.events)  # Collect events from each calendar
            else:
                print(f"Failed to fetch calendar from {url}: {response.status_code}")

        return events
# Function to set the background image
def set_bg_hack(main_bg):
    main_bg_ext = "jpg"
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: url(data:image/{main_bg_ext};base64,{main_bg}) no-repeat center center fixed;
            background-size: cover;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Load and encode the image file
main_bg = Path("calendar.jpg").read_bytes()
encoded_main_bg = base64.b64encode(main_bg).decode()

# Set the background image
set_bg_hack(encoded_main_bg)

# Apply custom styles
st.markdown(
    """
    <style>
    html, body, [class*="stText"], [class*="stMarkdown"], .stButton > button, .stTitle, .stSubheader, .stTextInput > label, .stCheckbox > div:first-child, h1, h2, h3, h4, h5, h6 {
        color: black !important;
        font-family: 'Arial', sans-serif !important;
    }
    input {
        background-color: rgba(255, 255, 255, 0.8) !important;
        color: black !important;
        font-size: 18px !important;
        padding: 10px !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
    }
    button {
        background-color: transparent !important;
        color: white !important;
        font-size: 18px !important;
        padding: 10px 20px !important;
        border: 2px solid white !important;
        border-radius: 8px !important;
    }
    button:hover {
        background-color: rgba(255, 255, 255, 0.1) !important;
    }
    .stCheckbox > div:first-child {
        color: black !important;
        font-size: 20px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to validate user login using MongoDB
# Debugging login function
def login(username, password):
    hashed_password = password

    # Debugging: Check what's being passed to the query
    print(f"Username: {username}")
    print(f"Hashed Password: {hashed_password}")

    user = users_collection.find_one({"username": username, "password": hashed_password})

    # Debugging: Check if the user was found
    print(f"User found: {user}")

    return user is not None

# Function to register a new user using MongoDB
def register_user(username, password):
    if users_collection.find_one({"username": username}):
        print("User already exists")  # Debugging: Check if the user already exists
        return False  # User already exists

    hashed_password = password

    # Debugging: Check what's being inserted
    print(f"Registering user with username: {username}, password: {hashed_password}")

    users_collection.insert_one({"username": username, "password": hashed_password})
    return True

# Session state to keep track of login status
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'is_registering' not in st.session_state:
    st.session_state['is_registering'] = False

if 'integration_complete' not in st.session_state:
    st.session_state['integration_complete'] = False

if 'integration_in_progress' not in st.session_state:
    st.session_state['integration_in_progress'] = False

if 'view_option' not in st.session_state:
    st.session_state['view_option'] = 'List View'

# Function to log out
def logout():
    st.session_state['logged_in'] = False
    st.session_state['integration_complete'] = False
    st.session_state['integration_in_progress'] = False
    st.session_state['canvas_events'] = []  # Clear events
    st.write("You have been logged out.")

# Function to fetch Canvas calendar events using CanvasAPI class
def fetch_canvas_calendar(api_token):
    try:
        st.session_state['integration_in_progress'] = True

        events = CanvasAPI.get_calendar_events(api_token)

        if events:
            st.session_state['integration_complete'] = True
            st.session_state['canvas_events'] = events
            st.success("Canvas calendar integration successful! 🎉")
            st.session_state['integration_in_progress'] = False
            st.rerun()  # Re-run the app to show the updated content
        else:
            st.warning("No calendar events found for the courses.")
    except Exception as e:
        st.error(f"Error fetching calendar events: {e}")
    finally:
        st.session_state['integration_in_progress'] = False

# Register page
def show_register_page():
    st.title("🔐 Register a New Account")
    new_username = st.text_input("Choose a Username", placeholder="Enter your username")
    new_password = st.text_input("Choose a Password", type="password", placeholder="Enter your password")
    register_btn = st.button("Register")

    if register_btn:
        if not new_username or not new_password:
            st.error("Both username and password are required.")
        else:
            if register_user(new_username, new_password):
                st.success("User registered successfully! Redirecting to login...")
                st.session_state['is_registering'] = False
                st.rerun()  # Re-run the app to return to the login page
            else:
                st.error("Username already exists. Please choose a different username.")

# Login page
def show_login_page():
    st.title("🔐 Login to PrioritizeMe")
    username = st.text_input("Username", placeholder="Enter your username")
    password = st.text_input("Password", type="password", placeholder="Enter your password")

    login_btn = st.button("Login")
    register_btn = st.button("Register")

    if login_btn:
        if login(username, password):
            st.session_state['logged_in'] = True
            st.session_state['username'] = username  # Store username in session
            st.success("Successfully Logged In!")
            st.rerun()  # Re-run the app to show the main page
        else:
            st.error("Invalid Username or Password!")

    if register_btn:
        st.session_state['is_registering'] = True  # Switch to the register page

# Main App Content
def show_main_content():
    st.title('🎯 PrioritizeMe AI')
    st.subheader('📅 Integrate Your Calendar')

    integrate_canvas = st.checkbox("Canvas")

    if integrate_canvas:
        st.markdown("[Need help with Canvas integration? Click here!](https://community.canvaslms.com/t5/Canvas-Basics-Guide/How-do-I-manage-API-access-tokens-in-my-user-account/ta-p/615312)", unsafe_allow_html=True)
        canvas_token = st.text_input("Enter Canvas API Access Token", type="password")

    if st.button("Integrate"):
        if integrate_canvas:
            if canvas_token:
                fetch_canvas_calendar(canvas_token)
            else:
                st.error("Canvas API token is required.")

    if st.session_state['integration_complete']:
        st.session_state['view_option'] = st.radio("Choose a view:", ('List View', 'Calendar View'))

        if st.session_state['view_option'] == 'List View':
            display_task_list()
        else:
            display_integrated_calendars()

    st.button("Logout", on_click=logout)

# Display integrated assignments in List View
def display_task_list():
    tasks = st.session_state.get('canvas_events', [])

    if tasks:
        st.write("### Task List")
        for event in tasks:
            st.write(f"**Event:** {event.name}")
            st.write(f"**Start Date:** {event.begin}")
            st.write(f"**End Date:** {event.end}")
            st.write("---")
    else:
        st.write("No tasks available to display.")

# Display integrated assignments in Calendar View
def display_integrated_calendars():
    tasks = []

    # Extract events from Canvas API response
    if 'canvas_events' in st.session_state:
        for event in st.session_state['canvas_events']:
            tasks.append({
                "title": event.name,
                "start": event.begin.isoformat(),
                "end": event.end.isoformat(),
                "color": "red"  # Canvas events are red
            })

    if tasks:
        task_events_js = str(tasks).replace("'", '"')

        # FullCalendar HTML/JS
        fullcalendar_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.css' rel='stylesheet' />
            <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.js'></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f0f2f6;
                    color: #333;
                }}
                #calendar {{
                    max-width: 900px;
                    margin: 40px auto;
                    padding: 0 10px;
                    background-color: white;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    border-radius: 8px;
                }}
            </style>
            <script>
            document.addEventListener('DOMContentLoaded', function() {{
                var calendarEl = document.getElementById('calendar');

                var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'dayGridMonth',
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay'
                }},
                events: {task_events_js},
                eventDisplay: 'block',
                editable: true,
                eventResizableFromStart: true,
                displayEventTime: true,
                eventTimeFormat: {{
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                }},
                slotMinTime: '00:00:00',
                slotMaxTime: '24:00:00'
                }});

                calendar.render();
            }});
            </script>
        </head>
        <body>
        <div id='calendar'></div>
        </body>
        </html>
        """

        st.components.v1.html(fullcalendar_html, height=600)

# Logic to switch between login, register, and main content
if not st.session_state['logged_in']:
    if st.session_state['is_registering']:
        show_register_page()
    else:
        show_login_page()
else:
    show_main_content()
