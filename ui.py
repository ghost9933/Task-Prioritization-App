import streamlit as st
from ics import Calendar
from datetime import datetime
import requests

# Dummy credentials for login
USER_CREDENTIALS = {'admin': 'password123'}

# Function to validate user login
def login(username, password):
    if USER_CREDENTIALS.get(username) == password:
        return True
    return False

# Session state to keep track of login status
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Function to log out
def logout():
    st.session_state['logged_in'] = False

# Login process
if not st.session_state['logged_in']:
    # Login Form
    st.title("🔐 Login to Access the Calendar App")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    login_btn = st.button("Login")
    
    if login_btn:
        if login(username, password):
            st.session_state['logged_in'] = True
            st.success("Successfully Logged In!")
            # Immediately update UI after successful login
        else:
            st.error("Invalid Username or Password!")
else:
    # Main App Content
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
                    "color": color
                })

    # Calendar view with event colors
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
                  eventResizableFromStart: true
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

    # Manual Task Entry
    myKey = 'show_manual_task_form'

    if myKey not in st.session_state:
        st.session_state[myKey] = False

    if st.button('Add a Task Manually'):
        st.session_state[myKey] = not st.session_state[myKey]

    if st.session_state[myKey]:
        st.subheader("Add a Task Manually")

        manual_task_name = st.text_input("Task Name")
        manual_task_priority = st.selectbox("Task Priority", ["Low", "Medium", "High"])
        manual_task_date = st.date_input("Task Date", datetime.now())
        manual_task_time = st.time_input("Task Time", datetime.now().time())

        if st.button("Add Manual Task"):
            manual_task_start = datetime.combine(manual_task_date, manual_task_time)
            tasks.append({
                "title": manual_task_name,
                "start": manual_task_start.isoformat(),
                "end": manual_task_start.isoformat(),
                "color": "green"  # Manual tasks are green by default
            })
            st.success(f"Manual Task '{manual_task_name}' added successfully!")

            sorted_tasks = sorted(tasks, key=lambda x: (x['start'], x['end']))

            st.write("### Updated Prioritized Task List:")
            for t in sorted_tasks:
                st.write(f"Task: {t['title']} | Start: {t['start']} | End: {t['end']}")
