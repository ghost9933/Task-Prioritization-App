from icalendar import Calendar
from datetime import datetime
import pytz

def parse_ics(file_path):
    try:
        with open(file_path, 'rb') as f:
            gcal = Calendar.from_ical(f.read())
    except Exception as e:
        print(f"Failed to read the .ics file: {e}")
        return []

    events = []
    for component in gcal.walk():
        if component.name == "VEVENT":
            try:
                uid = component.get('uid')
                summary = component.get('summary')
                description = component.get('description')

                # Handle timezone: Assume UTC if no timezone info is present

                event = {
                    'uid': uid,
                    'summary': summary,
                    'description': description
                }
                events.append(event)
            except Exception as e:
                print(f"Failed to parse an event: {e}")
                continue

    return events

if __name__ == "__main__":
    # Replace 'your_calendar.ics' with the path to your .ics file
    ics_path = 'events.ics'
    events = parse_ics(ics_path)

    if not events:
        print("No events found or failed to read the calendar.")
    else:
        for event in events:
            print(f"Event UID: {event['uid']}")
            print(f"Summary: {event['summary']}")
            print(f"Description: {event['description']}")
            print("-" * 40)
