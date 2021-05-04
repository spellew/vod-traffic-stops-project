from shutil import copyfile, rmtree
from bs4 import BeautifulSoup
from os import path, listdir
import requests
import zipfile
import time


def download_csv(download_directory, stateabbrev_underscore_city=None):
    soup = BeautifulSoup(requests.get("https://openpolicing.stanford.edu/data/").content, "html.parser")
    download_cells = soup.findAll("td", attrs={"data-title": "Download"})
    data = {}

    for cell in download_cells:
        parent_element = cell.parent
        grandparent_element = cell.parent.parent

        city = parent_element.find("td", attrs={"class": "state text-left"}).find("span").contents
        state = grandparent_element.find("tr", attrs={"class": "state-title"}).find("td").contents
        href = cell.find("a", attrs={"title": "Download data as CSV"}).get("href")

        city = city[0].replace(" ", "_").lower()
        state = state[0].replace(" ", "_").lower()

        if stateabbrev_underscore_city and f"{state}_{city}" == stateabbrev_underscore_city.lower():
            data[href] = {
                "state": state,
                "city": city,
                "href": href
            }


    data_values = list(data.values())
    num_data_values = len(data_values)

    for i in range(num_data_values):
        download = data_values[i]

        directory_name = download["state"] + "_" + download["city"]
        directory_path = download_directory + directory_name

        file_name = directory_name + ".csv"
        file_path = download_directory + file_name

        zip_name = file_name + ".zip"
        zip_path = download_directory + zip_name

        print("(" + "%.2f" % ((i / num_data_values) * 100) + "%) Attempting to download " + zip_name + "...")
        if path.exists(zip_path):
            print("\tAlready downloaded " + zip_name + "!")
            if path.exists(file_path):
                print("\tAlready extracted " + file_name + "!")
            else:
                with zipfile.ZipFile(zip_path,"r") as zip_ref:
                    zip_ref.extractall(directory_path)
                    csv_file = [file for file in listdir(directory_path) if ".csv" in file][0]
                    copyfile(directory_path + "/" + csv_file, file_path)
                    rmtree(directory_path)
        else:
            r = requests.get(download["href"], allow_redirects=True)
            open(zip_path, "wb").write(r.content)
            time.sleep(3)
