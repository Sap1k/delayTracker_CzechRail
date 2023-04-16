import sqlite3
from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, make_response


# Function to connect to DB and properly handle exceptions
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file, check_same_thread=False)
        print(sqlite3.version)
    except sqlite3.Error as e:
        print(e)
    finally:
        if conn:
            return conn
        else:
            return None


# Function to fetch data from the CzechRail database and put the relevant info in the db
def data_fetcher():
    # Set API URL and set request details for past and future arrivals
    API_URL = 'https://www.cd.cz/stanice/StaniceDetail.aspx/GetOPT'
    API_REQ = {'sr70': 5453289,  # Station ID for Teplice v Čechách
               'language': 'cs',  # Language, at a minimum en works too, didn't test further
               'isDeep': False,  # If True, returns departures, not arrivals
               'toHistory': False  # If True, returns trains departed in the last 24h
               }
    API_REQ_PAST = {'sr70': 5453289,  # Station ID for Teplice v Čechách
                    'language': 'cs',  # Language, at a minimum en works too, didn't test further
                    'isDeep': False,  # If True, returns departures, not arrivals
                    'toHistory': True  # If True, returns trains departed in the last 24h
                    }

    # Fetches data from CzechRail API and puts it into one concise list
    train_data_cur = requests.post(API_URL, json=API_REQ).json()['d']['Trains'][:10]
    train_data_past = requests.post(API_URL, json=API_REQ_PAST).json()['d']['Trains'][-3:]
    train_data = train_data_past + train_data_cur
    # Sets current time at the time the request got back
    cur_time = datetime.now().strftime('%H:%M')

    # Check whether the first 13 arrivals have arrived, if so, save them into database, incl. delays
    for train in train_data:
        # Parse expected arrival time into a datetime object
        if train['DTDelay'] == '':
            train_time = datetime.strptime(train['DT'], '%H:%M')
        else:
            train_time = datetime.strptime(train['DTDelay'], '%H:%M')

        # There surely is a way to do this more elegantly, but hey, it works :)
        train_cur_time = datetime.strptime(cur_time, '%H:%M')

        # Calculate a time difference in minutes between the current time and the expected arrival
        time_diff = train_time - train_cur_time
        time_diff = int(time_diff.total_seconds() / 60)

        # print(str(time_diff) + ' minut do odjezdu -- ' + str(train))

        # If time difference between the present and the expected arrival is +- 2 minutes, we can safely write the data
        # into the DB
        # Without this, sudden delay changes could cause a train to not get saved
        if -5 <= time_diff <= 2:
            # Build a planned departure string for DB, which requires datetime to adhere to ISO 8601
            planned_dep = f"{datetime.today().strftime('%Y-%m-%d')} {train['DT']}:00"
            # Check whether train hasn't already been inserted into DB
            c.execute('SELECT id FROM zpozdeni WHERE train_num = ? AND planned = ?',
                      [train['TrainNumber'], planned_dep])
            train_exists = c.fetchone()
            # If train has arrived and isn't yet present in the DB, insert it
            if train_exists is None:
                print(f"logging train {train['Name']} with an expected arrival of {train['DT']} and a "
                      f"{train['Delay']}m delay")
                c.execute('INSERT INTO zpozdeni (train_num, train_type, train_name, from_direction, delay, planned, '
                          'cd_url) VALUES (?, ?, ?, ?, ?, ?, ?)', [train['TrainNumber'], train['Type'], train['Name'],
                                                                   train['Destination'] + ', ' + train['Direction'],
                                                                   train['Delay'], planned_dep, train['URL']])
                con.commit()


# Connect to DB and create table if it hasn't yet been created
con = create_connection("zpozdeni.sqlite3")
c = con.cursor()

c.execute("CREATE TABLE IF NOT EXISTS zpozdeni (id INTEGER PRIMARY KEY NOT NULL, train_num INTEGER, train_type TEXT, "
          "train_name TEXT, from_direction TEXT, delay INTEGER, planned TEXT, cd_url TEXT, "
          "inserted TEXT DEFAULT (datetime('now', 'localtime')))")
con.commit()

# Calls data fetcher manually on startup, since it would otherwise wait a minute before first scan
data_fetcher()

# Add scheduled task to scrape CzechRail API every minute
scrape_task = BackgroundScheduler(daemon=True)
scrape_task.add_job(data_fetcher, 'interval', minutes=1)
scrape_task.start()

app = Flask(__name__)
# Strip whitespaces from Jinja generated HTML
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True


@app.route('/')
def view_delays():
    # Get data from form on main site
    date = request.args.get('date')
    time = request.args.get('time')

    # If no datetime has been selected, show the last 5 departures
    if (date is None and time is None) or (date == '' or time == ''):
        c.execute('SELECT * FROM zpozdeni ORDER BY id DESC LIMIT 5')
    else:
        datetime_db = f"{date} {time}:00"
        c.execute('SELECT * FROM zpozdeni WHERE inserted > ? ORDER BY id LIMIT 5', [datetime_db])
    last_delays = c.fetchall()

    # Calculate actual arrival based on planned arrival and delay
    real_arrivals = list()
    for arrival in last_delays:
        planned_arrival = datetime.strptime(arrival[6], '%Y-%m-%d %H:%M:%S')
        real_arrival = planned_arrival + timedelta(minutes=arrival[5])
        real_arrivals.append(datetime.strftime(real_arrival, '%H:%M'))


    # Send data to jinja, and by extension the user
    resp = make_response(render_template('main.html', trains=last_delays, datetime=[date, time],
                                         real_arrivals=real_arrivals))
    return resp


if __name__ == '__main__':
    app.run()
