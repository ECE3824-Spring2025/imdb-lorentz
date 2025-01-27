from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from movie_data import (  # Import each data list from `movie_data.py`
    ListWithRatingDrama, ListWithRatingAction, ListWithRatingComedy,
    ListWithLikesDrama, ListWithLikesAction, ListWithLikesComedy
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
# =====================
# Utility: Convert "2.3M" votes to integer 2300000
# =====================
def parse_votes_to_int(votes_str): # Define function to convert counts into integer counts

    if votes_str.endswith('M'): # If vote string count ends with M convert to int by multiplying by millions

        return int(float(votes_str.replace('M', '')) * 1_000_000)
    
    elif votes_str.endswith('K'): # If vote string count ends with K convert to int by multiplying by thousands

        return int(float(votes_str.replace('K', '')) * 1_000)
    
    return int(votes_str) if votes_str.isdigit() else 0 # If the string contains only digits convert to int


# =====================
# Function to Fetch Top 10 Movies
# =====================
def get_top_10_data(genre, sort_by): # Define a function that retrieves and decendendly sorts movies by rating or votes 

    if sort_by == 'rating':# If the sort by parameter is equal to rating

        data = { # Retreive the list corresponding to the genre parameter that is assosiated with Ratings, set retreived list to data
            'Drama': ListWithRatingDrama,
            'Action': ListWithRatingAction,
            'Comedy': ListWithRatingComedy
        }.get(genre, [])

        data = sorted(data, key=lambda x: x['rating'], reverse=True) # Sort in decending order by rating

    elif sort_by == 'votes':  # Retreive the list corresponding to the genre that is assosiated with Votes, set retreived list to data
        data = {  # Retreive the list corresponding to the input genre parameter that is assosiated with Ratings, set retreived list to data
            'Drama': ListWithLikesDrama,
            'Action': ListWithLikesAction,
            'Comedy': ListWithLikesComedy
        }.get(genre, [])

        data = sorted(data, key=lambda x: parse_votes_to_int(x['votes']), reverse=True) # Sort in decending order by votes

    else:
        data = [] # If input parameteres are wrong return an empty list

    return data[:10]  # Return only the top 10 items


# =====================
# Flask Route: API for Movies
# =====================
@app.route("/api/movies", methods=["GET"])  # Defines a Flask route that handles GET requests to /api/movies
def get_movies(): # Flask automatically invokes this function when a GET request is received at /api/movies
    genre = request.args.get("genre", default="Drama")  # Extracts 'genre' from the request URL, defaults to "Drama" if not provided
    sort_by = request.args.get("sortBy", default="rating")  # Extracts 'sortBy' from the request URL, defaults to "rating" if not provided
    print(f"API Request: Genre={genre}, SortBy={sort_by}")  # Debug log
    data = get_top_10_data(genre, sort_by) # Fetches the top 10 movies based on the selected genre and sorting criteria
    print(f"Data returned: {data}")  # Debug log
    return jsonify(data), 200 # Returns the movie data as a JSON response with HTTP status 200 (OK)

@app.route("/", methods=["GET"])
def home():
    return render_template('index.html')
# =====================
# Run Flask Locally
# =====================
if __name__ == "__main__":
    app.run(debug=False, port=8080)

