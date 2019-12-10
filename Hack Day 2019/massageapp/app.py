import base64

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session  # https://pythonhosted.org/Flask-Session
import msal
import app_config
from datetime import datetime, timedelta
import database
import requests
import uuid
import json
import os


def get_admin_auth_token():
    data = [
        ('client_id', app_config.CLIENT_ID),
        ('username', app_config.USERNAME),
        ('password', app_config.PASSWORD),
        ('scope', 'https://graph.microsoft.com/.default'),
        ('grant_type', 'password'),
    ]
    url = app_config.TENANT_AUTHORITY + '/oauth2/v2.0/token'

    response = json.loads(requests.post(
        url,
        data=data
    ).text)

    return response['access_token']


def set_appointment(admin_name, booking_datetime, user, wait_list_pop=False):
    # Send these headers with all API calls

    if not wait_list_pop:
        content = ("You have a Massage booked with " + admin_name + ", Enjoy! " +
                   "If you cannot make it to this appointment please cancel as soon as possible through the "
                   "webapp (Not Outlook) to give someone in the wait-list a chance to fill the slot."
                   )
    else:
        content = ("Someone couldn't make it to an appointment with " + admin_name + ", You have been Booked! " +
                   "If you cannot make it to this appointment please cancel as soon as possible through the "
                   "webapp (Not Outlook) to give someone else in the wait-list a chance to fill the slot."
                   )

    data = {
        "subject": "Massage Appointment with " + admin_name,
        "body": {
            "contentType": "HTML",
            "content": content
        },
        "start": {
            "dateTime": booking_datetime.isoformat(),
            "timeZone": "Eastern Standard Time"
        },
        "end": {
            "dateTime": (booking_datetime + timedelta(minutes=30)).isoformat(),
            "timeZone": "Eastern Standard Time"
        },
        "location": {
            "displayName": "Massage Room"
        },
        "attendees": [
            {
                "emailAddress": {
                    "address": user['email'],
                    "name": user['name']
                },
                "type": "required"
            }
        ]
    }

    url = app_config.ENDPOINT + '/' + app_config.USERNAME + '/events'
    response = requests.post(
        url,
        headers={'Authorization': 'Bearer ' + get_admin_auth_token(),
                 'Content-Type': 'application/json'
                 },
        json=data
    )
    event_id = (json.loads(response.text)['id'])
    return event_id


def cancel_appointment(event_id):
    url = app_config.ENDPOINT + '/' + app_config.USERNAME + '/events/' + event_id
    requests.delete(
        url,
        headers={'Authorization': 'Bearer ' + get_admin_auth_token(),
                 'Content-Type': 'application/json'
                 },
    )


def email_submit_form(selected_admin):
    selected_admin.get_submit_form()
    filename = selected_admin.name + '.csv'
    b64_content = base64.b64encode(open(filename, 'rb').read())
    attachment = [
        {
            '@odata.type': '#microsoft.graph.fileAttachment',
            'ContentBytes': b64_content.decode('utf-8'),
            'ContentType': "text/csv",
            'Name': filename
        }
    ]

    data = {
        "message": {
            "subject": "Submitted Massage Sign Up Sheet from " + selected_admin.name,
            "body": {
                "contentType": "Text",
                "content": "Here is this week's submitted form, " + submit_form_user["name"]
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": submit_form_user["email"]
                    }
                }
            ],
            "attachments": attachment,
        },
        "saveToSentItems": "false"
    }
    url = app_config.ENDPOINT + '/' + app_config.USERNAME + '/sendMail/'
    requests.post(
        url,
        headers={'Authorization': 'Bearer ' + get_admin_auth_token(),
                 'Content-Type': 'application/json'
                 },
        json=data
    )

    os.remove(selected_admin.name + ".csv")


app = Flask(__name__)
app.config.from_object(app_config)
Session(app)


def next_weekday(day, weekday):
    if day.weekday() == weekday:
        return day
    days_ahead = weekday - day.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return day + timedelta(days_ahead)


submit_form_user = {"name": "Adam Lawson", "email": "adam.lawson@irdeto.com", "status": ""}
admin_email_list = ["minoo.raki@irdeto.com", "gabriel.elkadiki@irdeto.com",
                    "adam.lawson@irdeto.com", " massageroomottawa@irdeto.com "
                    ]

db = database.Database(["Erin", "Julia"], next_weekday(datetime.today(), 3), next_weekday(datetime.today(), 4),
                       datetime(2019, 10, 3, 9, 00), datetime(2019, 10, 3, 15, 30))


@app.route("/")
def index():
    token = _get_token_from_cache(app_config.SCOPE)
    if not session.get("user") or not token:
        return redirect(url_for("login"))
    user = {"name": session['user']['name'], "email": session['user']['preferred_username']}
    return render_template('user_dashboard.html', user=user, db=db)


@app.route("/login")
def login():
    token = _get_token_from_cache(app_config.SCOPE)
    if not session.get("user") or not token:
        session["state"] = str(uuid.uuid4())
        auth_url = _build_msal_app().get_authorization_request_url(
            app_config.SCOPE,  # Technically we can use empty list [] to just sign in,
            # here we choose to also collect end user consent upfront
            state=session["state"],
            redirect_uri=url_for("authorized", _external=True))

        return render_template('login.html') % auth_url

    return redirect(url_for("index"))


@app.route("/admin")
def admin():
    token = _get_token_from_cache(app_config.SCOPE)
    if not session.get("user") or not token:
        return redirect(url_for("login"))

    if not session.get("user").get("preferred_username") in admin_email_list:
        return redirect(url_for("index"))

    user = {"name": session['user']['name'], "email": session['user']['preferred_username']}

    return render_template('admin.html', user=user, db=db)


@app.route("/getAToken")  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    if request.args['state'] != session.get("state"):
        return redirect(url_for("login"))
    cache = _load_cache()
    result = _build_msal_app(cache).acquire_token_by_authorization_code(
        request.args['code'],
        scopes=app_config.SCOPE,  # Misspelled scope would cause an HTTP 400 error here
        redirect_uri=url_for("authorized", _external=True))
    if "error" in result:
        return "Login failure: %s, %s" % (
            result["error"], result.get("error_description"))
    session["user"] = result.get("id_token_claims")
    _save_cache(cache)
    if session["user"]["preferred_username"] in admin_email_list:
        return redirect(url_for("admin"))
    if "@irdeto.com" not in session["user"]["preferred_username"]:
        session.clear()
        return redirect(url_for("login"))

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and its token cache from session
    return redirect(  # Also need to logout from Microsoft Identity platform
        "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
        "?post_logout_redirect_uri=" + url_for("index", _external=True))


@app.route('/update_booking', methods=['POST'])
def update_booking():
    token = _get_token_from_cache(app_config.SCOPE)
    if not session.get("user") or not token:
        return redirect(url_for("login"))

    if request.form.get('btn_update_1'):
        selected_admin = db.admin_1
    elif request.form.get('btn_update_2'):
        selected_admin = db.admin_2
    else:
        return redirect(url_for("admin"))

    _booking_time = request.form['bookingtime']
    _booking_name = request.form['username']
    time = datetime.strptime(_booking_time, '%H:%M')
    timestr = time.strftime("%I:%M %p")
    selected_admin.admin_update_booking(timestr, _booking_name)
    return redirect(url_for("admin"))


@app.route('/reset_data', methods=['POST'])
def reset_data():
    token = _get_token_from_cache(app_config.SCOPE)

    if not session.get("user") or not token:
        return redirect(url_for("login"))

    if request.form['reset'] == 'Submit ' + db.admin_1.name:
        selected_admin = db.admin_1
    elif request.form['reset'] == 'Submit ' + db.admin_2.name:
        selected_admin = db.admin_2
    else:
        return redirect(url_for("admin"))

    _start_time = request.form['starttime']
    _start_time_hour = int(_start_time.split(':')[0])
    _start_time_minute = int(_start_time.split(':')[1])
    _end_time = request.form['endtime']
    _end_time_hour = int(_end_time.split(':')[0])
    _end_time_minute = int(_end_time.split(':')[1])
    _date = request.form['date']
    _year = int(_date.split('-')[0])
    _month = int(_date.split('-')[1])
    _day = int(_date.split('-')[2])

    email_submit_form(selected_admin)
    os.remove(selected_admin.name + '.json')
    if selected_admin == db.admin_1:
        db.admin_1 = database.Admin(db.admin_1.name,
                                    datetime(_year, _month, _day, _start_time_hour, _start_time_minute),
                                    datetime(_year, _month, _day, _start_time_hour, _start_time_minute),
                                    datetime(_year, _month, _day, _end_time_hour, _end_time_minute))
    elif selected_admin == db.admin_2:
        db.admin_2 = database.Admin(db.admin_2.name,
                                    datetime(_year, _month, _day, _start_time_hour, _start_time_minute),
                                    datetime(_year, _month, _day, _start_time_hour, _start_time_minute),
                                    datetime(_year, _month, _day, _end_time_hour, _end_time_minute))

    return redirect(url_for("admin"))


@app.route('/full_reset', methods=['POST'])
def full_reset():
    global db
    token = _get_token_from_cache(app_config.SCOPE)

    if not session.get("user") or not token:
        return redirect(url_for("login"))

    os.remove(db.admin_1.name + '.json')
    os.remove(db.admin_2.name + '.json')
    db = database.Database([db.admin_1.name, db.admin_2.name], next_weekday(datetime.today(), 3),
                           next_weekday(datetime.today(), 4), datetime(2019, 10, 3, 9, 00),
                           datetime(2019, 10, 3, 15, 30))
    return redirect(url_for("admin"))


@app.route('/book/<int:num>/<admin_name>', methods=['POST'])
def book(num, admin_name):
    token = _get_token_from_cache(app_config.SCOPE)

    if not session.get("user") or not token:
        return redirect(url_for("login"))

    user = {"name": session['user']['name'], "email": session['user']['preferred_username']}

    if admin_name == db.admin_1.name:
        selected_admin = db.admin_1
    elif admin_name == db.admin_2.name:
        selected_admin = db.admin_2
    else:
        return render_template('user_dashboard.html', user=user, db=db)
    booking, user["status"] = db.make_booking(selected_admin, int(num), user)
    if booking is not None:
        date = selected_admin.massage_date_raw
        time = datetime.strptime(booking['time'], '%I:%M %p')
        date_time = date.replace(hour=time.hour, minute=time.minute, second=0, microsecond=0)
        event_id = set_appointment(selected_admin.name, date_time, user)
        selected_admin.add_event_id(user, event_id)

    return render_template('user_dashboard.html', user=user, db=db)


@app.route('/cancel/<int:num>/<admin_name>/<user_type>', methods=['POST'])
def cancel(num, admin_name, user_type):
    token = _get_token_from_cache(app_config.SCOPE)

    if not session.get("user") or not token:
        return redirect(url_for("login"))

    user = {"name": session['user']['name'], "email": session['user']['preferred_username'], "status": ""}

    admin_cancel = True if user_type == "admin" else False
    if admin_name == db.admin_1.name:
        selected_admin = db.admin_1
    elif admin_name == db.admin_2.name:
        selected_admin = db.admin_2
    else:
        if admin_cancel:
            return redirect(url_for("admin"))
        return redirect(url_for("index"))

    booking = selected_admin.find_booking(user)
    if booking:
        event_id = booking['booked_by']['event_id']
    else:
        event_id = ""
    next_wait_list_user, user["status"] = db.cancel_booking(selected_admin, int(num), user, admin_cancel=admin_cancel)
    if not event_id == "":
        cancel_appointment(event_id)
    if next_wait_list_user is not None:
        if not next_wait_list_user["name"] == "":
            date = selected_admin.massage_date_raw
            time = datetime.strptime(booking['time'], '%I:%M %p')
            date_time = date.replace(hour=time.hour, minute=time.minute, second=0, microsecond=0)
            event_id = set_appointment(selected_admin.name, date_time, next_wait_list_user, wait_list_pop=True)
            selected_admin.add_event_id(next_wait_list_user, event_id)

    if admin_cancel:
        return redirect(url_for("admin"))

    return render_template('user_dashboard.html', user=user, db=db)


@app.route('/wait_list/<action>/<admin_name>', methods=['POST'])
def wait_list(admin_name, action):
    token = _get_token_from_cache(app_config.SCOPE)

    if not session.get("user") or not token:
        return redirect(url_for("login"))

    user = {"name": session['user']['name'], "email": session['user']['preferred_username']}

    if admin_name == db.admin_1.name:
        selected_admin = db.admin_1
    elif admin_name == db.admin_2.name:
        selected_admin = db.admin_2
    else:
        return render_template('user_dashboard.html', user=user, db=db)

    _, user["status"] = db.modify_wait_list(selected_admin, user, action=action)

    return render_template('user_dashboard.html', user=user, db=db)


@app.route('/clear_status', methods=['POST'])
def clear_user_status():
    return redirect(url_for("index"))


def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()


def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        app_config.CLIENT_ID, authority=app_config.AUTHORITY,
        client_credential=app_config.CLIENT_SECRET, token_cache=cache)


def _get_token_from_cache(scope=None):
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache)
    accounts = cca.get_accounts()
    if accounts:  # So all account(s) belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result


if __name__ == "__main__":
    app.run(host='0.0.0.0')
