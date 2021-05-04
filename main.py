from download_data import download_csv
from vod import OpenPolicing
import json


# DATA_FILE = ("ar_little_rock", "Little Rock Arkansas USA",)
# DATA_FILE = ("pa_philadelphia", "Philadelphia Pennsylvania USA",)
DATA_FILE = ("ct_hartford", "Hartford Connecticut USA",)
# DATA_FILE = ("ca_oakland", "Oakland California USA",)
# DATA_FILE = ("ny_state_patrol", "New York USA",)


# Change this to absolute path
DOWNLOAD_DIRECTORY = "CSE540/traffic-stops-project/data/"
download_csv(DOWNLOAD_DIRECTORY, stateabbrev_underscore_city=DATA_FILE[0])


with open("cache.json", "a+") as f:
    op = OpenPolicing(DOWNLOAD_DIRECTORY)
    twilight_cache = {}
    f.seek(0)

    if f.read(1):
        f.seek(0)
        twilight_cache = json.load(f)

    op.veil_of_darkness(
        DATA_FILE,
        2015, # select the year from the chosen dataset to run analysis
        consider_district=True,
        twilight_cache=twilight_cache,
        debug=True
    )
