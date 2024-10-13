# Databricks notebook source
# MAGIC %pip install google-generativeai
# MAGIC

# COMMAND ----------

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

# MAGIC %pip install --upgrade typing_extensions
# MAGIC %pip install openai==0.28

# COMMAND ----------

display(dbutils.fs.ls("/FileStore/shared_uploads/mxa3328@mavs.uta.edu"))


# COMMAND ----------

dbutils.fs.head("/FileStore/shared_uploads/mxa3328@mavs.uta.edu/input.ics")

