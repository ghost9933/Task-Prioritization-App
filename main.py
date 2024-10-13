import streamlit as st
from datetime import datetime, date, timedelta
import requests
import json
import http.client
from ics import Calendar, Event
import base64
from pathlib import Path
from pymongo import MongoClient
import hashlib
import os
from urllib.parse import quote_plus  # To escape username and password
from dotenv import load_dotenv
import google.generativeai as genai

# ----------------------------
# Load Environment Variables
# ----------------------------
load_dotenv()  # Load variables from .env

# Retrieve environment variables
YOUR_DB_NAME = os.getenv("YOUR_DB_NAME")
YOUR_USERNAME = os.getenv("YOUR_USERNAME")
YOUR_PASSWORD = os.getenv("YOUR_PASSWORD")
YOUR_MONGODB_HOST = os.getenv("YOUR_MONGODB_HOST")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_SECRET = os.getenv("GEMINI_API_SECRET")

# ----------------------------
# Configure Gemini API
# ----------------------------
genai.configure(api_key=GEMINI_API_KEY)

# ----------------------------
# MongoDB Atlas Connection
# ----------------------------
MONGO_USERNAME = quote_plus(YOUR_USERNAME)  # MongoDB username
MONGO_PASSWORD = quote_plus(YOUR_PASSWORD)  # MongoDB password
MONGO_CLUSTER_URL = YOUR_MONGODB_HOST  # MongoDB cluster URL
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER_URL}/test?retryWrites=true&w=majority"
DB_NAME = YOUR_DB_NAME  # Database name
COLLECTION_NAME = "users"  # Collection to store users' credentials

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db[COLLECTION_NAME]

# ----------------------------
# Helper Functions
# ----------------------------

def hash_password(password):
    """Hash a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

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
        conn.request("GET", "/api/v1/courses", headers=cls.get_headers(api_token))
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        return data  # Return raw JSON string

    @classmethod
    def extract_calendar_urls(cls, api_token):
        courses_data = cls.get_courses(api_token)

        if not courses_data:
            return []

        # Parse the JSON data
        courses = json.loads(courses_data)
        calendar_urls = [course['calendar']['ics'] for course in courses if 'calendar' in course and 'ics' in course['calendar']]
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
                st.error(f"Failed to fetch calendar from {url}: {response.status_code}")

        return events

class GeminiAPI:
    BASE_URL = "https://api.gemini.com/v1"  # Replace with actual Gemini API base URL

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    def get_headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def create_schedule(self, task_details):
        endpoint = f"{self.BASE_URL}/schedules"
        response = requests.post(endpoint, headers=self.get_headers(), json=task_details)
        response.raise_for_status()  # Raises HTTPError if the response was unsuccessful
        return response.json()

    def get_schedules(self):
        endpoint = f"{self.BASE_URL}/schedules"
        response = requests.get(endpoint, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

# Initialize GeminiAPI
gemini = GeminiAPI(api_key=GEMINI_API_KEY, api_secret=GEMINI_API_SECRET)

def set_bg_hack(main_bg):
    """Set background image for Streamlit app."""
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

def extract_events_from_content(content):
    """Extract events from ICS content."""
    gcal = Calendar(content)
    events = []
    for component in gcal.walk():
        if component.name == "VEVENT":
            events.append({
                'uid': str(component.get('UID')),
                'summary': str(component.get('SUMMARY')),
                'start': component.get('DTSTART').dt,
                'description': str(component.get('DESCRIPTION')),
                'url': str(component.get('URL')) if component.get('URL') else None,
            })
    return events

def serialize_event(event):
    """Serialize event for JSON compatibility."""
    return {
        'uid': event.get('uid'),
        'summary': event.get('summary'),
        'start': event['start'].isoformat() if isinstance(event['start'], (datetime, date)) else event['start'],
        'description': event.get('description'),
        'url': event.get('url')
    }

def generate_schedule_prompt(tasks):
    """Generate a structured prompt for Gemini API based on tasks."""
    prompt = (
        "I have a list of tasks with their descriptions and due dates. Please generate a weekly schedule that organizes these tasks efficiently. "
        "For each week, list the tasks, their priorities, and any dependencies. Highlight tasks that are due within the week and suggest optimal times for completion based on their descriptions.\n\n"
        "Here are my tasks:\n"
    )
    
    for idx, task in enumerate(tasks, 1):
        prompt += f"\n{idx}. **{task['summary']}**\n"
        prompt += f"   - **Description:** {task['description']}\n"
        prompt += f"   - **Due Date:** {task['start']}\n"
    
    prompt += "\nPlease provide the schedule in a clear, week-by-week format."
    return prompt

def generate_schedule_with_gemini(tasks):
    """Generate a weekly schedule report using Gemini API."""
    prompt = generate_schedule_prompt(tasks)
    
    try:
        response = gemini.create_schedule({"prompt": prompt})
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while generating the schedule: {e}")
        return None

def parse_schedule_report(report):
    """
    Parse the schedule report from Gemini and extract events.
    Assumes the report is in a consistent, parseable format.
    Example Format:
    Week 1:
    1. Task Title
       Description
       Due Date
    """
    events = []
    lines = report.split('\n')
    current_week = None
    for line in lines:
        if line.startswith("Week"):
            current_week = line.strip()
        elif line.strip().startswith('**') and current_week:
            # Extract task details
            title = line.strip().strip('**')
            # Next two lines are Description and Due Date
            desc_line = next((l for l in lines[lines.index(line)+1:] if l.strip()), None)
            due_line = next((l for l in lines[lines.index(line)+2:] if l.strip()), None)
            if desc_line and due_line:
                description = desc_line.split("**Description:**")[1].strip()
                due_date_str = due_line.split("**Due Date:**")[1].strip()
                try:
                    due_date = datetime.strptime(due_date_str, "%B %d, %Y")
                except ValueError:
                    due_date = datetime.today()
                event = Event()
                event.name = title
                event.begin = due_date
                event.description = description
                event.make_all_day()
                events.append(event)
    return events

def create_ics_file(events):
    """Create an ICS file from a list of ICS Event objects."""
    cal = Calendar()
    for event in events:
        cal.events.add(event)
    return cal

def get_download_link(cal):
    """Generate a download link for the ICS file."""
    c = cal.serialize()
    b64 = base64.b64encode(c.encode()).decode()
    href = f'<a href="data:text/calendar;base64,{b64}" download="schedule.ics">Download ICS File</a>'
    return href

# ----------------------------
# User Authentication Functions
# ----------------------------

def login(username, password):
    """Validate user login using MongoDB."""
    hashed_password = hash_password(password)
    user = users_collection.find_one({"username": username, "password": hashed_password})
    return user is not None

def register_user(username, password):
    """Register a new user using MongoDB."""
    if users_collection.find_one({"username": username}):
        return False  # User already exists
    hashed_password = hash_password(password)
    users_collection.insert_one({"username": username, "password": hashed_password})
    return True

# ----------------------------
# Streamlit UI Components
# ----------------------------

# Initialize Session State
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
    st.session_state['is_registering'] = False
    st.session_state['integration_complete'] = False
    st.session_state['integration_in_progress'] = False
    st.session_state['canvas_events'] = []  # Clear Canvas events
    st.session_state['gemini_tasks'] = []  # Clear Gemini tasks
    st.session_state['schedule_report'] = ""  # Clear schedule report
    st.success("You have been logged out.")

# Function to fetch Canvas calendar events using CanvasAPI class
def fetch_canvas_calendar(api_token):
    try:
        st.session_state['integration_in_progress'] = True
        events = CanvasAPI.get_calendar_events(api_token)

        if events:
            st.session_state['integration_complete'] = True
            st.session_state['canvas_events'] = events
            st.success("Canvas calendar integration successful! 🎉")
        else:
            st.warning("No calendar events found for the courses.")
    except Exception as e:
        st.error(f"Error fetching Canvas calendar events: {e}")
    finally:
        st.session_state['integration_in_progress'] = False

# Function to create Gemini Task
def create_gemini_task(tasks):
    """Create a schedule using Gemini API."""
    response = generate_schedule_with_gemini(tasks)
    if response:
        schedule_report = response.get('generated_content')  # Adjust based on actual response
        st.session_state['schedule_report'] = schedule_report
        st.success("Weekly schedule generated successfully!")
        
        # Parse the schedule report to extract events
        gemini_events = parse_schedule_report(schedule_report)
        st.session_state['gemini_events'] = gemini_events
        
        # Generate ICS file
        cal = create_ics_file(gemini_events)
        st.session_state['ics_file'] = cal

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
                st.experimental_rerun()  # Re-run the app to return to the login page
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
            st.experimental_rerun()  # Re-run the app to show the main page
        else:
            st.error("Invalid Username or Password!")

    if register_btn:
        st.session_state['is_registering'] = True  # Switch to the register page

# Display integrated assignments in List View
def display_task_list():
    canvas_tasks = st.session_state.get('canvas_events', [])
    gemini_tasks = st.session_state.get('gemini_tasks', [])

    if canvas_tasks or gemini_tasks:
        st.write("### Task List")

        if canvas_tasks:
            st.write("#### Canvas Tasks")
            for event in canvas_tasks:
                st.write(f"**Event:** {event['summary']}")
                st.write(f"**Start Date:** {event['start']}")
                st.write(f"**End Date:** {event['end']}")
                st.write("---")

        if gemini_tasks:
            st.write("#### Gemini Tasks")
            for task in gemini_tasks:
                st.write(f"**Title:** {task['summary']}")
                st.write(f"**Description:** {task['description']}")
                st.write(f"**Due Date:** {task['start']}")
                st.write("---")
    else:
        st.write("No tasks available to display.")

# Display integrated assignments in Calendar View
def display_integrated_calendars():
    tasks = []

    # Extract Canvas events
    canvas_events = st.session_state.get('canvas_events', [])
    for event in canvas_events:
        tasks.append({
            "title": event['summary'],
            "start": event['start'].isoformat(),
            "end": event['end'].isoformat(),
            "color": "red"  # Canvas events are red
        })

    # Extract Gemini tasks
    gemini_tasks = st.session_state.get('gemini_tasks', [])
    for task in gemini_tasks:
        tasks.append({
            "title": task['summary'],
            "start": task['start'],  # Assuming start is in ISO format
            "end": task['start'],    # Single day task
            "color": "blue"          # Gemini tasks are blue
        })

    # Add Gemini-generated schedule events
    gemini_events = st.session_state.get('gemini_events', [])
    for event in gemini_events:
        tasks.append({
            "title": event.name,
            "start": event.begin.isoformat(),
            "end": event.end.isoformat(),
            "color": "green"  # Gemini schedule events are green
        })

    if tasks:
        task_events_js = json.dumps(tasks)  # Properly format JSON

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
                editable: false,
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
        st.write("No tasks available to display on the calendar.")

# Function to display the generated schedule report
def display_schedule_report():
    schedule_report = st.session_state.get('schedule_report', "")
    if schedule_report:
        st.markdown("### Weekly Schedule Report")
        st.text(schedule_report)
        
        # If schedule report has been parsed into events, offer ICS download
        gemini_events = st.session_state.get('gemini_events', [])
        if gemini_events:
            cal = st.session_state.get('ics_file', None)
            if cal:
                download_link = get_download_link(cal)
                st.markdown(download_link, unsafe_allow_html=True)
    else:
        st.write("No schedule report available.")

def get_download_link(cal):
    """Generate a download link for the ICS file."""
    c = cal.serialize()
    b64 = base64.b64encode(c.encode()).decode()
    href = f'<a href="data:text/calendar;base64,{b64}" download="schedule.ics">Download ICS File</a>'
    return href

# ----------------------------
# Function to parse Gemini's schedule report
# ----------------------------

def parse_schedule_report(report):
    """
    Parse the schedule report from Gemini and extract events.
    Assumes the report is in a consistent, parseable format.
    Example Format:
    Week 1:
    1. Task Title
       Description
       Due Date
    Week 2:
    ...
    """
    events = []
    lines = report.split('\n')
    current_week = None
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("Week"):
            current_week = line
            idx += 1
            continue
        elif line.startswith('**') and current_week:
            # Extract task details
            title = line.strip().strip('**')
            # Ensure the next two lines exist
            if idx + 2 < len(lines):
                desc_line = lines[idx + 1].strip()
                due_line = lines[idx + 2].strip()
                
                # Extract description
                if desc_line.startswith('- **Description:**'):
                    description = desc_line.split('- **Description:**')[1].strip()
                else:
                    description = "No description provided."
                
                # Extract due date
                if due_line.startswith('- **Due Date:**'):
                    due_date_str = due_line.split('- **Due Date:**')[1].strip()
                    try:
                        due_date = datetime.strptime(due_date_str, "%B %d, %Y")
                    except ValueError:
                        due_date = datetime.today()
                else:
                    due_date = datetime.today()
                
                # Create an event
                event = Event()
                event.name = title
                event.begin = due_date
                event.description = description
                event.make_all_day()
                events.append(event)
                
                idx += 3
                continue
        idx += 1
    return events

# ----------------------------
# User Authentication Functions
# ----------------------------

def login(username, password):
    """Validate user login using MongoDB."""
    hashed_password = hash_password(password)
    user = users_collection.find_one({"username": username, "password": hashed_password})
    return user is not None

def register_user(username, password):
    """Register a new user using MongoDB."""
    if users_collection.find_one({"username": username}):
        return False  # User already exists
    hashed_password = hash_password(password)
    users_collection.insert_one({"username": username, "password": hashed_password})
    return True

# ----------------------------
# Streamlit UI Components
# ----------------------------

# Initialize Session State
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
    st.session_state['is_registering'] = False
    st.session_state['integration_complete'] = False
    st.session_state['integration_in_progress'] = False
    st.session_state['canvas_events'] = []  # Clear Canvas events
    st.session_state['gemini_tasks'] = []  # Clear Gemini tasks
    st.session_state['schedule_report'] = ""  # Clear schedule report
    st.session_state['gemini_events'] = []  # Clear Gemini events
    st.session_state['ics_file'] = None  # Clear ICS file
    st.success("You have been logged out.")

# Function to fetch Canvas calendar events using CanvasAPI class
def fetch_canvas_calendar(api_token):
    try:
        st.session_state['integration_in_progress'] = True
        events = CanvasAPI.get_calendar_events(api_token)

        if events:
            st.session_state['integration_complete'] = True
            st.session_state['canvas_events'] = events
            st.success("Canvas calendar integration successful! 🎉")
        else:
            st.warning("No calendar events found for the courses.")
    except Exception as e:
        st.error(f"Error fetching Canvas calendar events: {e}")
    finally:
        st.session_state['integration_in_progress'] = False

# Function to create Gemini Task
def create_gemini_task(tasks):
    """Create a schedule using Gemini API."""
    response = generate_schedule_with_gemini(tasks)
    if response:
        schedule_report = response.get('generated_content')  # Adjust based on actual response
        st.session_state['schedule_report'] = schedule_report
        st.success("Weekly schedule generated successfully!")
        
        # Parse the schedule report to extract events
        gemini_events = parse_schedule_report(schedule_report)
        st.session_state['gemini_events'] = gemini_events
        
        # Generate ICS file
        cal = create_ics_file(gemini_events)
        st.session_state['ics_file'] = cal

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
                st.experimental_rerun()  # Re-run the app to return to the login page
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
            st.experimental_rerun()  # Re-run the app to show the main page
        else:
            st.error("Invalid Username or Password!")

    if register_btn:
        st.session_state['is_registering'] = True  # Switch to the register page

# Display integrated assignments in List View
def display_task_list():
    canvas_tasks = st.session_state.get('canvas_events', [])
    gemini_tasks = st.session_state.get('gemini_tasks', [])

    if canvas_tasks or gemini_tasks:
        st.write("### Task List")

        if canvas_tasks:
            st.write("#### Canvas Tasks")
            for event in canvas_tasks:
                st.write(f"**Event:** {event['summary']}")
                st.write(f"**Start Date:** {event['start']}")
                st.write(f"**End Date:** {event['end']}")
                st.write("---")

        if gemini_tasks:
            st.write("#### Gemini Tasks")
            for task in gemini_tasks:
                st.write(f"**Title:** {task['summary']}")
                st.write(f"**Description:** {task['description']}")
                st.write(f"**Due Date:** {task['start']}")
                st.write("---")
    else:
        st.write("No tasks available to display.")

# Display integrated assignments in Calendar View
def display_integrated_calendars():
    tasks = []

    # Extract Canvas events
    canvas_events = st.session_state.get('canvas_events', [])
    for event in canvas_events:
        tasks.append({
            "title": event['summary'],
            "start": event['start'].isoformat(),
            "end": event['end'].isoformat(),
            "color": "red"  # Canvas events are red
        })

    # Extract Gemini tasks
    gemini_tasks = st.session_state.get('gemini_tasks', [])
    for task in gemini_tasks:
        tasks.append({
            "title": task['summary'],
            "start": task['start'],  # Assuming start is in ISO format
            "end": task['start'],    # Single day task
            "color": "blue"          # Gemini tasks are blue
        })

    # Add Gemini-generated schedule events
    gemini_events = st.session_state.get('gemini_events', [])
    for event in gemini_events:
        tasks.append({
            "title": event.name,
            "start": event.begin.isoformat(),
            "end": event.end.isoformat(),
            "color": "green"  # Gemini schedule events are green
        })

    if tasks:
        task_events_js = json.dumps(tasks)  # Properly format JSON

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
                editable: false,
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
        st.write("No tasks available to display on the calendar.")

# Function to display the generated schedule report
def display_schedule_report():
    schedule_report = st.session_state.get('schedule_report', "")
    if schedule_report:
        st.markdown("### Weekly Schedule Report")
        st.text(schedule_report)
        
        # If schedule report has been parsed into events, offer ICS download
        gemini_events = st.session_state.get('gemini_events', [])
        if gemini_events:
            cal = st.session_state.get('ics_file', None)
            if cal:
                download_link = get_download_link(cal)
                st.markdown(download_link, unsafe_allow_html=True)
    else:
        st.write("No schedule report available.")

def get_download_link(cal):
    """Generate a download link for the ICS file."""
    c = cal.serialize()
    b64 = base64.b64encode(c.encode()).decode()
    href = f'<a href="data:text/calendar;base64,{b64}" download="schedule.ics">Download ICS File</a>'
    return href

# ----------------------------
# Function to parse Gemini's schedule report
# ----------------------------

def parse_schedule_report(report):
    """
    Parse the schedule report from Gemini and extract events.
    Assumes the report is in a consistent, parseable format.
    Example Format:
    Week 1:
    1. Task Title
       Description
       Due Date
    Week 2:
    ...
    """
    events = []
    lines = report.split('\n')
    current_week = None
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("Week"):
            current_week = line
            idx += 1
            continue
        elif line.startswith('**') and current_week:
            # Extract task details
            title = line.strip().strip('**')
            # Ensure the next two lines exist
            if idx + 2 < len(lines):
                desc_line = lines[idx + 1].strip()
                due_line = lines[idx + 2].strip()
                
                # Extract description
                if desc_line.startswith('- **Description:**'):
                    description = desc_line.split('- **Description:**')[1].strip()
                else:
                    description = "No description provided."
                
                # Extract due date
                if due_line.startswith('- **Due Date:**'):
                    due_date_str = due_line.split('- **Due Date:**')[1].strip()
                    try:
                        due_date = datetime.strptime(due_date_str, "%B %d, %Y")
                    except ValueError:
                        due_date = datetime.today()
                else:
                    due_date = datetime.today()
                
                # Create an event
                event = Event()
                event.name = title
                event.begin = due_date
                event.description = description
                event.make_all_day()
                events.append(event)
                
                idx += 3
                continue
        idx += 1
    return events

def create_ics_file(events):
    """Create an ICS file from a list of ICS Event objects."""
    cal = Calendar()
    for event in events:
        cal.events.add(event)
    return cal

def get_download_link(cal):
    """Generate a download link for the ICS file."""
    c = cal.serialize()
    b64 = base64.b64encode(c.encode()).decode()
    href = f'<a href="data:text/calendar;base64,{b64}" download="schedule.ics">Download ICS File</a>'
    return href

# ----------------------------
# Main App Content
# ----------------------------

def show_main_content():
    st.title('🎯 PrioritizeMe AI')
    st.subheader('📅 Integrate Your Calendar and Gemini Scheduling')

    # Integration Options
    integrate_canvas = st.checkbox("Canvas")
    integrate_gemini = st.checkbox("Gemini")

    # Canvas Integration
    if integrate_canvas:
        canvas_token = st.text_input("Enter Canvas API Access Token", type="password")

    # Gemini Integration - Schedule Helper
    if integrate_gemini:
        with st.form("gemini_task_form"):
            st.write("### Add a Gemini Task")
            task_title = st.text_input("Task Title", placeholder="Enter task title")
            task_description = st.text_area("Task Description", placeholder="Enter task description")
            task_due_date = st.date_input("Due Date", min_value=date.today())
            submitted = st.form_submit_button("Add Task")

            if submitted:
                if not all([task_title, task_description, task_due_date]):
                    st.error("All task fields are required.")
                else:
                    task_details = {
                        "summary": task_title,
                        "description": task_description,
                        "start": task_due_date.isoformat()
                    }
                    # Collect all tasks into a list
                    if 'gemini_tasks' not in st.session_state:
                        st.session_state['gemini_tasks'] = []
                    st.session_state['gemini_tasks'].append(task_details)
                    st.success(f"Task '{task_title}' added successfully!")

        # Button to Generate Weekly Schedule
        if st.button("Generate Weekly Schedule"):
            if 'gemini_tasks' in st.session_state and st.session_state['gemini_tasks']:
                create_gemini_task(st.session_state['gemini_tasks'])
                display_schedule_report()
            else:
                st.warning("No tasks available to generate a schedule.")

    # Integration Button
    if st.button("Integrate"):
        if integrate_canvas:
            if canvas_token:
                fetch_canvas_calendar(canvas_token)
            else:
                st.error("Canvas API token is required.")

        if integrate_gemini:
            st.success("Gemini integration is ready! You can create tasks using the form above.")

    # Display Integrated Data
    if st.session_state.get('integration_complete') or integrate_gemini:
        st.session_state['view_option'] = st.radio("Choose a view:", ('List View', 'Calendar View'))

        if st.session_state['view_option'] == 'List View':
            display_task_list()
        else:
            display_integrated_calendars()

    # Display Schedule Report if available
    display_schedule_report()

    # If ICS file is generated, provide a download link
    ics_file = st.session_state.get('ics_file', None)
    if ics_file:
        download_link = get_download_link(ics_file)
        st.markdown(download_link, unsafe_allow_html=True)

    st.button("Logout", on_click=logout)

# Logic to switch between login, register, and main content
if not st.session_state['logged_in']:
    if st.session_state['is_registering']:
        show_register_page()
    else:
        show_login_page()
else:
    show_main_content()
