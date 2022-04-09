import pickle
import os.path
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import socket

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CAL_ID = "<your_calendar_id_here>"


def calendar_service():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)
    return service


def ufc_get_events():
    current_time = datetime.timestamp(datetime.now())
    ufc_link = "https://www.ufc.com"
    ufc_web = requests.get(ufc_link + "/events")

    soup = BeautifulSoup(ufc_web.text, "html.parser")

    # List of event dictionaries
    events_dict = []

    events_all = soup.findAll("div", {"class": "c-card-event--result__info"})
    for event in events_all:
        try:
            # Get timestamps
            main_time = int(
                event.find(
                    "div", {"class": "c-card-event--result__date tz-change-data"}
                )["data-main-card-timestamp"]
            )

            # Skip past events
            if main_time < current_time:
                continue

            main_time = datetime.fromtimestamp(main_time)

            early_time = event.find(
                "div", {"class": "c-card-event--result__date tz-change-data"}
            )["data-early-card-timestamp"]
            if early_time:
                prelim_time = datetime.fromtimestamp(int(early_time))
            else:
                prelim_time = datetime.fromtimestamp(
                    int(
                        event.find(
                            "div",
                            {"class": "c-card-event--result__date tz-change-data"},
                        )["data-prelims-card-timestamp"]
                    )
                )

            end_time = main_time + timedelta(hours=3)

            main_time = main_time.astimezone().isoformat()
            prelim_time = prelim_time.astimezone().isoformat()
            end_time = end_time.astimezone().isoformat()

            link = ufc_link + event.find("a", href=True)["href"]

            name = link.split("/")[-1]
            if ("fight" in name) or ("ufc" not in name):
                name = "UFC Fight Night"
            else:
                name = name.upper()

            events_dict.append(
                {
                    "name": name,
                    "link": link,
                    "prelim_time": prelim_time,
                    "main_time": main_time,
                    "end_time": end_time,
                }
            )
        except:
            continue

    return events_dict


def make_events(cal, ufc_events):
    # Get all future events and form a dictionary of form --> start_date_of_event: event ID
    existing_events = (
        cal.events()
        .list(
            calendarId=CAL_ID,
            timeMin=datetime.now().astimezone().isoformat(),
            pageToken=None,
        )
        .execute()
    )
    existing_events_dict = {}
    for ev in existing_events["items"]:
        start_date = datetime.fromisoformat(ev["start"]["dateTime"]).date()
        existing_events_dict[start_date] = ev["id"]

    for ufc in ufc_events:
        main_card = datetime.fromisoformat(ufc["main_time"])
        desc = (
            f"The main card starts at: {main_card.strftime('%I:%M %p (Pacific Time)')}"
        )
        event = {
            "summary": ufc["name"],
            "location": ufc["link"],
            "description": desc,
            "start": {"dateTime": ufc["prelim_time"]},
            "end": {"dateTime": ufc["end_time"]},
        }

        # Update events that exist or create event if it doesn't exist
        # If new event is on the same date as existing event, update existing event
        # Otherwise, create a new event
        new_start_date = datetime.fromisoformat(ufc["prelim_time"]).date()
        if id := existing_events_dict.get(new_start_date):
            cal.events().update(calendarId=CAL_ID, eventId=id, body=event).execute()
        else:
            cal.events().insert(calendarId=CAL_ID, body=event).execute()


def main():
    for _ in range(10):
        try:
            ufc_events = ufc_get_events()
            cal = calendar_service()
            make_events(cal, ufc_events)
        except (socket.timeout, requests.exceptions.ChunkedEncodingError):
            print(f"URL error occured. Retrying...")
        else:
            break


if __name__ == "__main__":
    print("Updating UFC Calendar...")
    main()
    print("UFC Calendar Updated!")
