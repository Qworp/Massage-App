from datetime import timedelta, datetime
import os.path
import json
import csv


class Database:
    def __init__(self, name_list, massage_date_1, massage_date_2, begin_time, end_time):
        self.admin_1 = Admin(name_list[0], massage_date_1, begin_time, end_time)
        self.admin_2 = Admin(name_list[1], massage_date_2, begin_time, end_time)

    def next_weekday(self, day, weekday):
        if day.weekday() == weekday:
            return day + timedelta(7)
        days_ahead = weekday - day.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        return day + timedelta(days_ahead)

    def find_booking(self, user):
        booking = self.admin_1.find_booking(user)
        if booking is not None:
            booking['admin'] = self.admin_1.name
            return booking

        booking = self.admin_2.find_booking(user)
        if booking is not None:
            booking['admin'] = self.admin_2.name
            return booking

        return None

    def make_booking(self, admin, index, user):
        if not self.admin_1.user_has_booking(user) and not self.admin_2.user_has_booking(user):
            if not admin.is_time_passed(index):
                if admin.can_user_book(index):
                    wait_list_index = self.admin_1.is_in_wait_list(user)
                    if wait_list_index is not None:
                        self.admin_1.modify_wait_list(user, action="remove", index=wait_list_index)

                    wait_list_index = self.admin_2.is_in_wait_list(user)
                    if wait_list_index is not None:
                        self.admin_2.modify_wait_list(user, action="remove", index=wait_list_index)

                    user_status = "You Have Been Booked!"
                    return admin.make_booking(index, user), user_status
                else:
                    user_status = "That Time Slot is Taken!"
                    return None, user_status
            else:
                user_status = "You Have Tried To Book A Past Time Slot!"
                return None, user_status
        else:
            user_status = "You Already Have a Booking!"
            return None, user_status

    def cancel_booking(self, admin, index, user, admin_cancel=False):
        if (self.admin_1.user_has_booking(user) or self.admin_2.user_has_booking(user)) or admin_cancel:
            if not admin.is_time_passed(index) or admin_cancel:
                if admin.can_user_cancel(index, user, admin_cancel=admin_cancel):
                    return admin.cancel_booking(index), "Your Booking has been Cancelled"
                else:
                    return None, "You Cannot Cancel This Booking!"
            else:
                return None, "You Have Tried To Cancel A Past Time Slot!"
        else:
            return None, "You Have No Booking To Cancel!"

    def get_wait_list_status(self, user):
        ret_1 = self.admin_1.get_wait_list_status(user)
        ret_2 = self.admin_2.get_wait_list_status(user)
        if ret_1:
            return ret_1
        elif ret_2:
            return ret_2
        else:
            return "You are not Booked or in any Wait List Currently"

    def modify_wait_list(self, admin, user, action="add"):
        if not self.admin_1.user_has_booking(user) and not self.admin_2.user_has_booking(user):
            index_1 = self.admin_1.is_in_wait_list(user)
            index_2 = self.admin_2.is_in_wait_list(user)
            if action == "add":
                if index_1 is None and index_2 is None:
                    user_status = "You have been Added to the Wait List for " + admin.name
                    return admin.modify_wait_list(user, action=action), user_status
                else:
                    user_status = "You are Already on a Wait List!"
                    return None, user_status
            elif action == "remove":
                if admin == self.admin_1 and index_1 is not None:
                    user_status = "You have been Removed from Wait List for " + admin.name
                    return admin.modify_wait_list(user, action=action, index=index_1), user_status
                elif admin == self.admin_2 and index_2 is not None:
                    user_status = "You have been Removed from Wait List for " + admin.name
                    return admin.modify_wait_list(user, action=action, index=index_2), user_status
                else:
                    user_status = "You are Not on this Wait List!"
                    return None, user_status

        else:
            if action == "add":
                user_status = "You Cannot be Added to a Wait List because a Booking Exists! Cancel Your Booking First"
                return None, user_status

            elif action == "remove":
                user_status = "You are Not on this Wait List and a Booking Already Exists!"
                return None, user_status


class Admin:
    def __init__(self, name, massage_date, begin_time, end_time):
        self.name = name
        if os.path.exists(self.name + '.json'):
            with open(self.name + '.json', 'r') as f:
                self.data_store = json.load(f)
                self.massage_date_raw = datetime.strptime(self.data_store["massage_date"], "%Y-%m-%d %H:%M:%S")
                self.massage_date = self.massage_date_raw.strftime("%a, %d %b %Y")
        else:
            self.massage_date_raw = massage_date
            self.massage_date = massage_date.strftime("%a, %d %b %Y")
            self.data_store = {
                "admin_name": name,
                "massage_date": str(massage_date),
                "schedule": [],
                "wait_list": []
            }
            delta = timedelta(minutes=30)
            thirty_min_timestamps = [begin_time]
            x_time = begin_time
            while x_time < end_time:
                x_time += delta
                thirty_min_timestamps.append(x_time)

            blank_booking = {"name": "", "email": "", "event_id": ""}
            for i in range(len(thirty_min_timestamps)):
                time_str = str((thirty_min_timestamps[i]).strftime("%I:%M %p"))
                self.data_store["schedule"].append({"time": time_str, "booked_by": blank_booking})

            with open(self.name + '.json', 'w') as f:
                json.dump(self.data_store, f)

    def is_time_passed(self, index):
        massage_date = self.massage_date_raw
        massage_time = datetime.strptime(self.data_store["schedule"][index]['time'], '%I:%M %p')
        massage_date_time = massage_date.replace(
            hour=massage_time.hour, minute=massage_time.minute, second=0, microsecond=0
        )
        return massage_date_time < datetime.today() - timedelta(minutes=30)

    def find_booking(self, user):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            for b in self.data_store["schedule"]:
                if b["booked_by"]["name"] == user["name"]:
                    return b
        return None

    def find_booking_index(self, index):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            booking = self.data_store["schedule"][index]

        return booking

    def user_has_booking(self, user):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            schedule = self.data_store["schedule"]
            for entry in schedule:
                if entry["booked_by"]["email"] == user["email"] or entry["booked_by"]["name"] == user["name"]:
                    return True
            return False

    def make_booking(self, index, user):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            booking = self.data_store["schedule"][index]["booked_by"]
            booking["name"] = user["name"]
            booking["email"] = user["email"]

        with open(self.name + '.json', 'w') as f:
            json.dump(self.data_store, f)

        return self.data_store["schedule"][index]

    def admin_update_booking(self, time, username):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            schedule = self.data_store["schedule"]
        for s in schedule:
            if s['time'] == time:
                s['booked_by']['name'] = username
                with open(self.name + '.json', 'w') as f:
                    json.dump(self.data_store, f)

    def can_user_book(self, index):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            booking = self.data_store["schedule"][index]["booked_by"]
            if booking["email"] == '' and booking["name"] == '':
                return True

    def can_user_cancel(self, index, user, admin_cancel=False):
        if admin_cancel:
            return True
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            booking = self.data_store["schedule"][index]["booked_by"]
            if booking["email"] == user["email"] or booking["name"] == user["name"]:
                return True

        return False

    def cancel_booking(self, index):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            if self.data_store["wait_list"]:
                self.data_store["schedule"][index]["booked_by"] = self.data_store["wait_list"].pop(0)
            else:
                blank_user = {"name": "", "email": "", "event_id": ""}
                self.data_store["schedule"][index]["booked_by"] = blank_user
        with open(self.name + '.json', 'w') as f:
            json.dump(self.data_store, f)
        return self.data_store["schedule"][index]["booked_by"]

    def is_in_wait_list(self, user):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            wait_list = self.data_store["wait_list"]
            for i in range(len(wait_list)):
                if wait_list[i]["email"] == user["email"]:
                    return i
            return None

    def len_wait_list(self):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            wait_list = self.data_store["wait_list"]
            return len(wait_list)

    def modify_wait_list(self, user, action="add", index=None):

        if action == "remove":
            with open(self.name + '.json', 'r') as f:
                self.data_store = json.load(f)
                wait_list = self.data_store["wait_list"]
                wait_list.pop(index)

        elif action == "add":
            with open(self.name + '.json', 'r') as f:
                self.data_store = json.load(f)
                wait_list = self.data_store["wait_list"]
                wait_list.append(user)
        else:
            return False

        with open(self.name + '.json', 'w') as f:
            json.dump(self.data_store, f)

        return True

    def get_schedule_list(self):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            schedule_list = []
            for booking in self.data_store["schedule"]:
                schedule_list.append([booking])

        return schedule_list

    def add_event_id(self, user, event_id):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            for b in self.data_store["schedule"]:
                if b["booked_by"]["name"] == user["name"]:
                    b["booked_by"]["event_id"] = event_id
                    break

        with open(self.name + '.json', 'w') as f:
            json.dump(self.data_store, f)

    def get_wait_list_status(self, user=None):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            wait_list = self.data_store["wait_list"]

        if user is None:
            return len(wait_list)

        elif self.find_booking(user) is not None:
            return "You Are Booked!"

        else:
            for w in wait_list:
                if w['email'] == user['email']:
                    return "You are number " + str(wait_list.index(w) + 1) + " in " + self.name + "'s Wait List "

        return False

    def get_submit_form(self):
        with open(self.name + '.json', 'r') as f:
            self.data_store = json.load(f)
            schedule = self.data_store['schedule']
            csv_out = open(self.name + '.csv', 'w+')
            csv_writer = csv.writer(csv_out, delimiter=',')
            count = 0
            for bk in schedule:
                if count == 0:
                    header = bk.keys()
                    csv_writer.writerow(header)
                    count += 1
                csv_writer.writerow([str(bk["time"]), str(bk["booked_by"]["name"]), str(bk["booked_by"]["email"])])
