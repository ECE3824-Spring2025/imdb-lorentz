from flask import Flask, request, jsonify
from flask_cors import CORS
from movie_data import (  # Importing data from `movie_data.py`
    ListWithRatingDrama, ListWithRatingAction, ListWithRatingComedy,
    ListWithLikesDrama, ListWithLikesAction, ListWithLikesComedy
)

app = Flask(__name__)
CORS(app) 
# =====================
# Utility: Convert "2.3M" votes to integer 2300000
# =====================
def parse_votes_to_int(votes_str):
    if votes_str.endswith('M'):
        return int(float(votes_str.replace('M', '')) * 1_000_000)
    elif votes_str.endswith('K'):
        return int(float(votes_str.replace('K', '')) * 1_000)
    return int(votes_str) if votes_str.isdigit() else 0


# =====================
# Function to Fetch Top 10 Movies
# =====================
def get_top_10_data(genre, sort_by):
    if sort_by == 'rating':
        data = {
            'Drama': ListWithRatingDrama,
            'Action': ListWithRatingAction,
            'Comedy': ListWithRatingComedy
        }.get(genre, [])

        data = sorted(data, key=lambda x: x['rating'], reverse=True)

    elif sort_by == 'votes':
        data = {
            'Drama': ListWithLikesDrama,
            'Action': ListWithLikesAction,
            'Comedy': ListWithLikesComedy
        }.get(genre, [])

        data = sorted(data, key=lambda x: parse_votes_to_int(x['votes']), reverse=True)

    else:
        data = []

    return data[:10]  # Return only the top 10 items


# =====================
# Flask Route: API for Movies
# =====================
@app.route("/api/movies", methods=["GET"])
def get_movies():
    genre = request.args.get("genre", default="Drama")
    sort_by = request.args.get("sortBy", default="rating")

    data = get_top_10_data(genre, sort_by)
    return jsonify(data), 200


# =====================
# Run Flask Locally
# =====================
if __name__ == "__main__":
    app.run(debug=True, port=5000)