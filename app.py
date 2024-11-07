from flask import Flask, render_template, request, jsonify
import requests
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
apikey = "f7ca13ee"

country_name_mapping = {
    "USA": "United States of America",
    "UK": "United Kingdom"
}

local_flag_cache = {}

executor = ThreadPoolExecutor(max_workers=10)


@lru_cache(maxsize=500)
def searchfilms(search_text, page=1):
    url = f"https://www.omdbapi.com/?s={
        search_text}&apikey={apikey}&page={page}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    print("Failed to retrieve search results.")
    return None


@lru_cache(maxsize=1000)
def getmoviedetails(imdb_id):
    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={apikey}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    print("Failed to retrieve movie details.")
    return None


def get_country_flag(fullname):
    if fullname in ["N/A", None, ""]:
        return "No flag available"
    if fullname in local_flag_cache:
        return local_flag_cache[fullname]
    fullname = country_name_mapping.get(fullname, fullname)
    url = f"https://restcountries.com/v3.1/name/{fullname}?fullText=true"
    response = requests.get(url)
    if response.status_code == 200:
        country_data = response.json()
        if country_data:
            flag_url = country_data[0].get("flags", {}).get("svg", None)
            if flag_url:
                local_flag_cache[fullname] = flag_url
                return flag_url
    print(f"Failed to retrieve flag for country: {fullname}")
    return "No flag available"


def merge_data_with_flags(filter, page):
    filmssearch = searchfilms(filter, page)
    if not filmssearch or "Search" not in filmssearch:
        return []
    moviesdetailswithflags = []
    future_to_movie = {}
    for movie in filmssearch["Search"]:
        future_to_movie[executor.submit(
            getmoviedetails, movie["imdbID"])] = movie

    for future in as_completed(future_to_movie):
        movie = future_to_movie[future]
        moviedetails = future.result()

        countries = []
        if "Country" in moviedetails:
            countriesNames = moviedetails["Country"].split(",")
            countriesNames = [
                name.strip() for name in countriesNames if name.strip() not in ["N/A", ""]]
            future_to_country = {}
            for country in countriesNames:
                future_to_country[executor.submit(
                    get_country_flag, country)] = country
            for country_future in as_completed(future_to_country):
                country = future_to_country[country_future]
                flag = country_future.result()
                countries.append({
                    "name": country,
                    "flag": flag if flag else "No flag available"
                })
        moviesdetailswithflags.append({
            "title": moviedetails.get("Title", "N/A"),
            "year": moviedetails.get("Year", "N/A"),
            "countries": countries
        })
    return moviesdetailswithflags


@app.route("/")
def index():
    filter = request.args.get("filter", "").upper()
    page = int(request.args.get("page", 1))
    movies = merge_data_with_flags(filter, page)
    return render_template("index.html", movies=movies, filter=filter, page=page)


@app.route("/api/movies")
def api_movies():
    filter = request.args.get("filter", "")
    page = int(request.args.get("page", 1))
    return jsonify(merge_data_with_flags(filter, page))


if __name__ == "__main__":
    app.run(debug=True)
    