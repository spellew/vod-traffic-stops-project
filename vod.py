from datetime import datetime
from dateutil import tz, parser
from sklearn import model_selection
from sklearn.metrics import classification_report
import geocoder
import json
import math
import pandas as pd
import requests
import statsmodels.api as sm
import statsmodels.formula.api as smf
import time


class OpenPolicing:
    def __init__(self, download_directory=""):
        self.latlng = None
        self.twilight_by_date = None
        self.factors_dict = None
        self.download_directory = download_directory
        pd.set_option('display.max_columns', None)

    def veil_of_darkness(self, data_file, year, minority_demographic="black", degree=6, consider_district=False, twilight_cache={}, debug=False):
        path_to_data_file = data_file[0] + ".csv"
        to_geocode = data_file[1]

        self.latlng = geocoder.osm(to_geocode).latlng
        self.twilight_by_date = {}
        self.factors_dict = {}

        df = pd.read_csv(self.download_directory + path_to_data_file)
        df, num_initial_rows, num_valid_date_time_rows, num_non_duplicate_rows, num_year_rows = self._clean_data_frame(df, year)

        earliest_sunsets = df[((df["date_time"].dt.month == 11) & (df["date_time"].dt.day >= 25)) | ((df["date_time"].dt.month == 12) & (df["date_time"].dt.day <= 15))]
        earliest_sunsets["date_time"].map(lambda date_time: self._date_time_to_darkness(date_time))

        latest_sunsets = df[((df["date_time"].dt.month == 6) & (df["date_time"].dt.day >= 10)) | ((df["date_time"].dt.month == 7) & (df["date_time"].dt.day <= 15))]
        latest_sunsets["date_time"].map(lambda date_time: self._date_time_to_darkness(date_time))

        twilight_by_date_values = [self._parse_twilight_time(twilight_date, same_date=True) for twilight_date in self.twilight_by_date.values()]
        if not len(twilight_by_date_values):
            print(f"{year} not in range!")
            return None

        earliest_sunset = min(twilight_by_date_values, key=self._ignore_twilight_date)
        latest_sunset = max(twilight_by_date_values, key=self._ignore_twilight_date)
        print("\nEarliest sunset: ", earliest_sunset)
        print("Latest sunset: ", latest_sunset)

        cached = twilight_cache[path_to_data_file] if path_to_data_file in twilight_cache else {}
        self.twilight_by_date = self.twilight_by_date | cached

        df = self._filter_data_frame_by_sunset(df, earliest_sunset, latest_sunset)
        X, y = self._manipulate_data_frame(df, minority_demographic, consider_district)
        X["is_minority"] = y

        print("\nManipulated data:")
        print(X)

        formula = f"is_minority ~ is_dark + cr(rounded_minutes, df={degree})"
        if consider_district:
            if "district" in df.columns:
                formula += " + location"
            else:
                print("\nCannot consider district, because district is not included in data!")

        model = smf.glm(formula, data=X, family=sm.families.Binomial())
        result = model.fit()

        if path_to_data_file not in twilight_cache:
            twilight_cache[path_to_data_file] = {}

        with open("cache.json", "w") as f:
            twilight_cache[path_to_data_file] = twilight_cache[path_to_data_file] | self.twilight_by_date
            json.dump(twilight_cache, f)

        if debug:
            print("\nNumber of rows: " + num_initial_rows)
            print("Number of valid rows with a date and time: " + num_valid_date_time_rows)
            print("Number of valid non-duplicate rows: " + num_non_duplicate_rows)
            print(f"Number of {year} rows: " + num_year_rows)
            print(f"\nSummary for {formula}")
            print(result.summary())

    def _ignore_twilight_date(self, twilight_date):
        return twilight_date.replace(year=1970, month=1, day=1)

    def _parse_twilight_time(self, twilight_date, same_date=False):
        return parser.parse(twilight_date).replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())

    def _clean_data_frame(self, df, year):
        num_initial_rows = str(df.shape[0])

        df = df[df["date"].notna()]
        df = df[df["time"].notna()]
        num_valid_date_time_rows = str(df.shape[0])

        date_time_str_column = df["date"].astype(str) + " " + df["time"].astype(str)
        date_time = date_time_str_column.map(lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"))
        df["date_time"] = date_time

        df = df.drop_duplicates()
        num_non_duplicate_rows = str(df.shape[0])

        df = df[df["date_time"].dt.year == year]
        num_year_rows = str(df.shape[0])

        return df, num_initial_rows, num_valid_date_time_rows, num_non_duplicate_rows, num_year_rows

    def _filter_data_frame_by_sunset(self, df, earliest_sunset, latest_sunset):
        return df[(df["date_time"].dt.time >= earliest_sunset.time()) & (df["date_time"].dt.time <= latest_sunset.time())]

    def _as_factor(self, data):
        if type(data) is float and math.isnan(data):
            return None

        for factor, value in self.factors_dict.items():
            if data == value:
                return factor

        factor = len(self.factors_dict)
        self.factors_dict[factor] = data
        return factor

    def _date_time_to_rounded_minutes(self, date_time, interval=5):
        minutes_since_midnight = ((date_time - date_time.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()) / 60
        return interval * round(minutes_since_midnight / interval)

    def _date_time_to_darkness(self, date_time):
        date = date_time.strftime("%Y-%m-%d")
        if date not in self.twilight_by_date:
            r = requests.get(f"https://api.sunrise-sunset.org/json?lat={self.latlng[0]}&lng={self.latlng[1]}&date={date}")
            json = r.json()
            if json["status"] != "OK":
                return None

            time.sleep(0.0625)
            civil_twilight_end = json["results"]["civil_twilight_end"]
            self.twilight_by_date[date] = f"{date} {civil_twilight_end}"

        return 1 if date_time.to_pydatetime().astimezone(tz.tzlocal()) >= self._parse_twilight_time(self.twilight_by_date[date]) else 0

    def _manipulate_data_frame(self, df, minority_demographic, consider_district):
        print("\nConverting date_time to is_dark...")
        df["is_dark"] = df["date_time"].map(lambda date_time: self._date_time_to_darkness(date_time))

        print("Converting date_time to rounded_minutes...")
        df["rounded_minutes"] = df["date_time"].map(lambda date_time: self._date_time_to_rounded_minutes(date_time))

        feature_cols = ["is_dark", "rounded_minutes"]
        if consider_district and "district" in df.columns:
            df["location"] = df["district"].map(lambda district: self._as_factor(district))
            feature_cols += ["location"]

        is_minority = df["subject_race"].map(lambda x: 1 if x == minority_demographic else 0)
        return df.loc[:, feature_cols], is_minority
