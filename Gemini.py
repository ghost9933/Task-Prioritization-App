# Databricks notebook source
print("1")

# COMMAND ----------

# Gemini Prompt code
import os
import google.generativeai as genai
from datetime import datetime, date
from icalendar import Calendar

# Set your API key
API_KEY = os.getenv("API_KEY") 
api_key = API_KEY
genai.configure(api_key=api_key)    

def extract_events_from_content(content):
    gcal = Calendar.from_ical(content)
    
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
    return {
        'uid': event.get('uid'),
        'summary': event.get('summary'),
        'start': event['start'].isoformat() if isinstance(event['start'], (datetime, date)) else event['start'],
        'description': event.get('description'),
        'url': event.get('url')
    }

def generate_content_with_gemini(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# Sample usage
def main():
    # Read the file content directly from DBFS
    file_path = "/FileStore/shared_uploads/mxa3328@mavs.uta.edu/input.ics"
    ics_content = dbutils.fs.head(f"dbfs:{file_path}")

    # Extract events from the content
    events = extract_events_from_content(ics_content)

    # Prepare the prompt from extracted events
    prompt = "Here are my events for the week:\n" + "\n".join([f"{event['summary']} on {event['start']}" for event in events])

    # Call the Gemini API
    response = generate_content_with_gemini(prompt)
    
    # Output the response
    print("Response from Gemini API:")
    print(response)

if __name__ == "__main__":
    main()


# COMMAND ----------

# import statements
import os
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
import google.generativeai as genai
from icalendar import Calendar
from datetime import datetime

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_URI"] = "your_mongodb_connection_string"
mongo = PyMongo(app)

# Configure API key for Gemini
os.environ["API_KEY"] = 'ENTER_YOUR_API_KEY'
genai.configure(api_key=os.environ["API_KEY"])


# user registration 
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if mongo.db.users.find_one({"username": username}):
        return jsonify({"error": "User already exists!"}), 400

    mongo.db.users.insert_one({"username": username, "password": password})
    return jsonify({"message": "User registered successfully!"}), 201

#user login 
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = mongo.db.users.find_one({"username": username, "password": password})
    if user:
        return jsonify({"message": "Login successful!"}), 200
    return jsonify({"error": "Invalid username or password!"}), 401

# ICS Upload endpoint
@app.route('/upload_ics', methods=['POST'])
def upload_ics():
    file = request.files['file']
    ics_content = file.read()  # Read the content of the uploaded ICS file

    events = extract_events_from_content(ics_content)
    serialized_events = [serialize_event(event) for event in events]
    
    # Process the events with Gemini API
    prompt = make_prompt_from_events(serialized_events)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)

    return jsonify({"response": response.text}), 200



# COMMAND ----------

import os
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
import google.generativeai as genai
from icalendar import Calendar
from datetime import datetime
from urllib.parse import quote_plus

# Flask application setup
app = Flask(__name__)

# MongoDB configuration
username = quote_plus('your_username')  # Replace with your MongoDB username
password = quote_plus('your_password')  # Replace with your MongoDB password
host = 'your_mongodb_host'  # Replace with your MongoDB host
db_name = 'your_db_name'  # Replace with your database name

app.config["MONGO_URI"] = f"mongodb://{username}:{password}@{host}/{db_name}?retryWrites=true&w=majority"
mongo = PyMongo(app)

# Configure API key for Gemini
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

def extract_events_from_content(content):
    gcal = Calendar.from_ical(content)
    
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
    return {
        'uid': event.get('uid'),
        'summary': event.get('summary'),
        'start': event['start'].isoformat() if isinstance(event['start'], (datetime)) else event['start'],
        'description': event.get('description'),
        'url': event.get('url')
    }

def generate_content_with_gemini(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# User Registration Endpoint
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if mongo.db.users.find_one({"username": username}):
        return jsonify({"error": "User already exists!"}), 400

    mongo.db.users.insert_one({"username": username, "password": password})
    return jsonify({"message": "User registered successfully!"}), 201

# User Login Endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = mongo.db.users.find_one({"username": username, "password": password})
    if user:
        return jsonify({"message": "Login successful!"}), 200
    return jsonify({"error": "Invalid username or password!"}), 401

# ICS File Upload Endpoint
@app.route('/upload_ics', methods=['POST'])
def upload_ics():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    ics_content = file.read()  # Read the content of the uploaded ICS file

    # Extract events from the content
    events = extract_events_from_content(ics_content)

    # Prepare the prompt from extracted events
    prompt = "Here are my events for the week:\n" + "\n".join([f"{event['summary']} on {event['start']}" for event in events])

    # Call the Gemini API
    response = generate_content_with_gemini(prompt)

    return jsonify({"response": response}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)  # Run the Flask app


# COMMAND ----------

# MAGIC %pip install flask_ngrok

# COMMAND ----------

import os
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_ngrok import run_with_ngrok  # Import run_with_ngrok
import google.generativeai as genai
from icalendar import Calendar
from datetime import datetime
from urllib.parse import quote_plus

# Flask application setup
app = Flask(__name__)
run_with_ngrok(app)  # Start ngrok when the app runs

# MongoDB configuration
username = quote_plus('your_username')  # Replace with your MongoDB username
password = quote_plus('your_password')  # Replace with your MongoDB password
host = 'your_mongodb_host'  # Replace with your MongoDB host
db_name = 'your_db_name'  # Replace with your database name

app.config["MONGO_URI"] = f"mongodb://{username}:{password}@{host}/{db_name}?retryWrites=true&w=majority"
mongo = PyMongo(app)

# Configure API key for Gemini
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

def extract_events_from_content(content):
    gcal = Calendar.from_ical(content)
    
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
    return {
        'uid': event.get('uid'),
        'summary': event.get('summary'),
        'start': event['start'].isoformat() if isinstance(event['start'], (datetime)) else event['start'],
        'description': event.get('description'),
        'url': event.get('url')
    }

def generate_content_with_gemini(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# User Registration Endpoint
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if mongo.db.users.find_one({"username": username}):
        return jsonify({"error": "User already exists!"}), 400

    mongo.db.users.insert_one({"username": username, "password": password})
    return jsonify({"message": "User registered successfully!"}), 201

# User Login Endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = mongo.db.users.find_one({"username": username, "password": password})
    if user:
        return jsonify({"message": "Login successful!"}), 200
    return jsonify({"error": "Invalid username or password!"}), 401

# ICS File Upload Endpoint
@app.route('/upload_ics', methods=['POST'])
def upload_ics():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    ics_content = file.read()  # Read the content of the uploaded ICS file

    # Extract events from the content
    events = extract_events_from_content(ics_content)

    # Prepare the prompt from extracted events
    prompt = "Here are my events for the week:\n" + "\n".join([f"{event['summary']} on {event['start']}" for event in events])

    # Call the Gemini API
    response = generate_content_with_gemini(prompt)

    return jsonify({"response": response}), 200

if __name__ == "__main__":
    app.run()  # Run the Flask app


# COMMAND ----------

# MAGIC %sh
# MAGIC wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
# MAGIC unzip ngrok-stable-linux-amd64.zip
# MAGIC

# COMMAND ----------

# MAGIC %sh
# MAGIC ./ngrok  authtoken 2nNdbTCmBA69oASV3rERoSQCd3U_5aswdeAsarQ3gY9N88Yed

# COMMAND ----------

# MAGIC %sh
# MAGIC ./ngrok http 5000
# MAGIC

# COMMAND ----------