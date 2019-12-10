from datetime import date, timedelta, datetime
import json


class Admin:
    def __init__(self, name, massage_date, begin_time, end_time):
        self.name = name
        self.massage_date = massage_date
        self.data_store = {
            "admin_name": name,
            "massage_date": str(massage_date),
            "schedule": []
        }
        delta = timedelta(minutes=30)
        thirty_min_timestamps = []
        x_time = begin_time
        while x_time < end_time:
            x_time += delta
            thirty_min_timestamps.append(x_time)

        blank_booking = {"name": "", "email": ""}
        for i in range(len(thirty_min_timestamps)):
            time_str = str((thirty_min_timestamps[i]).strftime("%I:%M %p"))
            self.data_store["schedule"].append({"time": time_str, "Booked By": blank_booking})

        with open('db.json', 'w') as f:
            json.dump(self.data_store, f)

    def make_booking(self, index, user):
        with open('db.json', 'r') as f:
            self.data_store = json.load(f)
            for b in self.data_store["schedule"]:
                if b["Booked By"]["name"] == user["name"]:
                    return False

            booking = self.data_store["schedule"][index]["Booked By"]
            if booking["name"] == "" and user["name"]:
                booking["name"] = user["name"]
                booking["email"] = user["email"]
            else:
                return False
        with open('db.json', 'w') as f:
            json.dump(self.data_store, f)
        return True

    def cancel_booking(self, index, user):
        with open('db.json', 'r') as f:
            self.data_store = json.load(f)
            booking = self.data_store["schedule"][index]["Booked By"]
            if booking["email"] == user["email"]:
                self.data_store["schedule"][index]["Booked By"]["name"] = ""
                self.data_store["schedule"][index]["Booked By"]["email"] = ""
            else:
                return False
        with open('db.json', 'w') as f:
            json.dump(self.data_store, f)
        return True

    def get_schedule_list(self):
        with open('db.json', 'r') as f:
            self.data_store = json.load(f)
            schedule_list = []
            for booking in self.data_store["schedule"]:
                schedule_list.append([booking])
        return schedule_list


# date_a = datetime(2016, 8, 9, 8, 24)
# date_b = datetime(2016, 8, 9, 16, 24)
# db1 = Admin("Jack", date.today(), datetime(2019, 10, 3, 8, 30), datetime(2019, 10, 3, 16, 30))

# print(db1.make_booking(0, {"name": "Musab", "email": "musab@tooslow.com"}))
# print(db1.make_booking(0, {"name": "Musab", "email": "musab@tooslow.com"}))
# print(db1.make_booking(1, {"name": "Musab", "email": "musab@tooslow.com"}))
# print(db1.cancel_booking(0, {"name": "Musab", "email": "musab@tooslow.com"}))
# print(db1.make_booking(0, {"name": "Musab", "email": "musab@tooslow.com"}))
# print(db1.make_booking(1, {"name": "Gabriel", "email": "gabriel@toofast.com"}))
# db = (db1.get_schedule_list())
# for d in db:
#     print(d)