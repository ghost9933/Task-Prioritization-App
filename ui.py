import streamlit as st
from datetime import datetime
import requests
import json
import http.client
from ics import Calendar


# CanvasAPI class for handling API requests
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


# Dummy credentials for users (simulating a database with a dictionary)
USER_CREDENTIALS = {'admin': 'password123'}

# Function to validate user login
def login(username, password):
    return USER_CREDENTIALS.get(username) == password

# Function to register a new user (simulated by adding to a list for now)
def register_user(username, password):
    if username in USER_CREDENTIALS:
        return False  # User already exists
    USER_CREDENTIALS[username] = password  # Add to the simulated DB
    return True

# Session state to keep track of login status
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Session state to track if the user is registering
if 'is_registering' not in st.session_state:
    st.session_state['is_registering'] = False

# Session state to track if the user has completed integration
if 'integration_complete' not in st.session_state:
    st.session_state['integration_complete'] = False

# Session state to track if integration is in progress
if 'integration_in_progress' not in st.session_state:
    st.session_state['integration_in_progress'] = False

# Session state to store view preference (list or calendar)
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
    new_username = st.text_input("Choose a Username")
    new_password = st.text_input("Choose a Password", type="password")
    register_btn = st.button("Register")

    if register_btn:
        if not new_username or not new_password:
            st.error("Both username and password are required.")
        else:
            if register_user(new_username, new_password):
                st.success("User registered successfully! Redirecting to login...")
                st.session_state['is_registering'] = False
                st.rerun()  # Re-run the app to return to the login page

# Login page
def show_login_page():
    st.title("🔐 Login to Access the Calendar App")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

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
    st.title('🎯 Task Prioritization App')

    st.subheader('📅 Integrate Your Calendar')

    integrate_canvas = st.checkbox("Canvas")
    integrate_google = st.checkbox("Google Calendar")

    if integrate_canvas:
        canvas_token = st.text_input("Enter Canvas API Access Token", type="password")

    if integrate_google:
        st.write("Google Calendar Sign-In (Coming Soon)")

    # Integration logic
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
