import streamlit as st
from ics import Calendar
from datetime import datetime
import requests

# Dummy credentials for users (simulating a database with a dictionary)
USER_CREDENTIALS = {'admin': 'password123'}

# User registration database (simulating a database with a list)
USER_DATABASE = []

# Function to validate user login
def login(username, password):
    return USER_CREDENTIALS.get(username) == password

# Function to register a new user (simulated by adding to a list for now)
def register_user(username, password):
    if username in USER_CREDENTIALS:
        return False  # User already exists
    USER_CREDENTIALS[username] = password  # Add to the simulated DB
    USER_DATABASE.append({'username': username, 'password': password})
    return True

# Session state to keep track of login status
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Session state to track if the user is registering
if 'is_registering' not in st.session_state:
    st.session_state['is_registering'] = False

# Function to log out
def logout():
    st.session_state['logged_in'] = False
    st.rerun()  # Rerun the app to refresh the page

# Register page
def show_register_page():
    st.title("🔐 Register a New Account")
    new_username = st.text_input("Choose a Username")
    new_password = st.text_input("Choose a Password", type="password")
    register_btn = st.button("Register")

    # Ensure that both fields are filled out
    if register_btn:
        if not new_username or not new_password:
            st.error("Both username and password are required.")
        else:
            if register_user(new_username, new_password):
                st.success("User registered successfully! Redirecting to login...")
                st.session_state['is_registering'] = False  # Switch back to login after successful registration
                st.rerun()  # Immediately refresh the page and go back to login
            else:
                st.error("Username already exists. Please choose a different username.")

# Login page
def show_login_page():
    st.title("🔐 Login to Access the Calendar App")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    login_btn = st.button("Login")
    register_btn = st.button("Register")  # Button to switch to the register page

    if login_btn:
        if login(username, password):
            st.session_state['logged_in'] = True
            st.success("Successfully Logged In!")
            st.rerun()  # Rerun the app to show the main page
        else:
            st.error("Invalid Username or Password!")

    if register_btn:
        st.session_state['is_registering'] = True  # Switch to the register page
        st.rerun()  # Refresh the page to switch to the registration form

# Main App Content (After login)
def show_main_content():
    st.title('🎯 Task Prioritization App')
    st.subheader('📅 Upload Your Calendar (.ics) File or Provide a URL')

    # Logout Button
    if st.button("Logout"):
        logout()

    # File upload section
    uploaded_file = st.file_uploader("Choose an .ics file", type="ics")
    ics_url = st.text_input("Or enter the URL of your .ics file")

    tasks = []

    def fetch_ics_from_url(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching .ics file from URL: {e}")
            return None

    # Parse the uploaded file or the URL
    if uploaded_file is not None or ics_url:
        if uploaded_file is not None:
            calendar_data = uploaded_file.read().decode("utf-8")
        else:
            calendar_data = fetch_ics_from_url(ics_url)

        if calendar_data:
            cal = Calendar(calendar_data)

            st.write("### Calendar Events:")

            for event in cal.events:
                task_name = event.name
                task_start = event.begin.datetime
                task_end = event.end.datetime
                task_description = event.description if event.description else "No description available"
                task_duration = (task_end - task_start).total_seconds() / 3600  # Duration in hours

                # Logic to determine the event source based on event name or description
                if "Canvas" in task_name:
                    event_source = "Canvas"
                    color = "red"
                elif "Outlook" in task_name:
                    event_source = "Outlook"
                    color = "blue"
                elif "Google" in task_name:
                    event_source = "Google"
                    color = "yellow"
                else:
                    event_source = "Other"
                    color = "green"  # Default color for other events

                tasks.append({
                    "title": task_name,
                    "start": task_start.isoformat(),
                    "end": task_end.isoformat(),
                    "description": task_description,
                    "duration": task_duration,
                    "color": color
                })

    # View option: List View or Calendar View
    view_option = st.radio("Choose a view", ('List View', 'Calendar View'))

    # List View
    if view_option == 'List View':
        st.write("### Detailed Task List")
        if tasks:
            for task in tasks:
                st.write(f"**Task:** {task['title']}")
                st.write(f"**Start:** {task['start']}")
                st.write(f"**End:** {task['end']}")
                st.write(f"**Duration:** {task['duration']:.2f} hours")
                st.write(f"**Description:** {task['description']}")
                st.write(f"**Event Source Color:** {task['color']}")
                st.write("---")
        else:
            st.write("No tasks available to display.")

    # Calendar View
    elif view_option == 'Calendar View':
        if tasks:
            task_events_js = str(tasks).replace("'", '"')

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

        else:
            st.write("No events to display. Please upload a file or provide a URL.")

# Logic to switch between login, register, and main content
if not st.session_state['logged_in']:
    if st.session_state['is_registering']:
        show_register_page()  # Show the registration page
    else:
        show_login_page()  # Show the login page
else:
    show_main_content()  # Show the main content after login
