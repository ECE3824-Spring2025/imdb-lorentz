import sqlalchemy #pip install sqlalchemy
import sqlalchemy.orm

# Patch SQLAlchemy Session.get_bind to avoid extra argument errors.
def patched_get_bind(self, mapper=None, clause=None):
    return self.bind
sqlalchemy.orm.Session.get_bind = patched_get_bind

if not hasattr(sqlalchemy, '__all__'):
    sqlalchemy.__all__ = []
if not hasattr(sqlalchemy.orm, '__all__'):
    sqlalchemy.orm.__all__ = []
if not hasattr(sqlalchemy.orm, 'dynamic_loader'):
    sqlalchemy.orm.dynamic_loader = lambda *args, **kwargs: None

from flask import Flask, request, jsonify, render_template #pip install flask
from flask_sqlalchemy import SQLAlchemy #pip install flask_sqlalchemy
from flask_caching import Cache #pip install flask_caching
from flask_cors import CORS #pip install flask_cors
import os
import csv
import pandas as pd #pip install flask_cors
from tqdm import tqdm  # pip install tqdm

# --- Monkey patch: subclass SQLAlchemy to add missing attributes ---
class PatchedSQLAlchemy(SQLAlchemy):
    pass

# Add missing attributes from SQLAlchemy ORM.
PatchedSQLAlchemy.relationship = sqlalchemy.orm.relationship
PatchedSQLAlchemy.relation = sqlalchemy.orm.relationship  # Alias for relationship
PatchedSQLAlchemy.dynamic_loader = sqlalchemy.orm.dynamic_loader
PatchedSQLAlchemy.Column = sqlalchemy.Column
PatchedSQLAlchemy.Integer = sqlalchemy.Integer
PatchedSQLAlchemy.String = sqlalchemy.String
PatchedSQLAlchemy.Float = sqlalchemy.Float

# --- Initialize the app and extensions using the patched SQLAlchemy ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///movies.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300

db = PatchedSQLAlchemy(app)
cache = Cache(app)

# --- Database Model ---
class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.String(20), primary_key=True)  # IMDb id (tconst)
    name = db.Column(db.String(200), nullable=False, default="Unknown")
    rating = db.Column(db.Float, nullable=True)
    votes = db.Column(db.String(20), nullable=True)
    genre = db.Column(db.String(200), nullable=False, default="Unknown")  # May store multiple genres

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rating": self.rating,
            "votes": self.votes,
            "genre": self.genre
        }

def parse_votes_to_int(votes_str):
    if votes_str and votes_str.endswith('M'):
        return int(float(votes_str.replace('M', '')) * 1_000_000)
    elif votes_str and votes_str.endswith('K'):
        return int(float(votes_str.replace('K', '')) * 1_000)
    return int(votes_str) if votes_str and votes_str.isdigit() else 0

# --- Merge IMDb datasets and seed the database ---
def seed_from_imdb_datasets(basics_tsv, ratings_tsv, chunk_size=10000):
    with app.app_context():
        # Read title.basics.tsv with progress bar
        print("Reading title.basics.tsv in chunks...")
        with open(basics_tsv, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for line in f) - 1  # subtract header
        total_chunks = (total_lines // chunk_size) + 1

        df_basics_list = []
        for chunk in tqdm(pd.read_csv(basics_tsv, sep='\t', na_values='\\N', low_memory=False, chunksize=chunk_size),
                            total=total_chunks, desc="Reading title.basics.tsv"):
            chunk = chunk[chunk['titleType'] == 'movie']
            df_basics_list.append(chunk)
        df_basics = pd.concat(df_basics_list, ignore_index=True)
        print(f"Loaded {len(df_basics)} movie records from title.basics.tsv.")

        # Read title.ratings.tsv (assumed to be smaller)
        print("Reading title.ratings.tsv...")
        df_ratings = pd.read_csv(ratings_tsv, sep='\t', na_values='\\N')
        print(f"Loaded {len(df_ratings)} records from title.ratings.tsv.")

        # Merge datasets on 'tconst'
        print("Merging datasets...")
        df_merged = pd.merge(df_basics, df_ratings, on='tconst', how='inner')
        print(f"Merged dataset has {len(df_merged)} records.")

        # Iterate over merged data and upsert into the database
        print("Seeding database from merged data...")
        for _, row in tqdm(df_merged.iterrows(), total=len(df_merged), desc="Seeding DB"):
            tconst = row['tconst']
            primary_title = row['primaryTitle'] if not pd.isna(row['primaryTitle']) else "Unknown"
            average_rating = row['averageRating'] if not pd.isna(row['averageRating']) else None
            num_votes = row['numVotes'] if not pd.isna(row['numVotes']) else None
            genres = row['genres'] if not pd.isna(row['genres']) else "Unknown"

            movie = db.session.get(Movie, tconst)
            if movie:
                movie.name = primary_title
                movie.rating = average_rating
                movie.votes = str(int(num_votes)) if num_votes is not None else None
                movie.genre = genres
            else:
                movie = Movie(
                    id=tconst,
                    name=primary_title,
                    rating=average_rating,
                    votes=str(int(num_votes)) if num_votes is not None else None,
                    genre=genres
                )
                db.session.add(movie)
        db.session.commit()
        print(f"Finished seeding. Total movies in DB: {Movie.query.count()}")

# --- Function to fetch top 10 movies with caching ---
def get_top_10_movies(genre, sort_by, min_votes_threshold=0, max_votes_threshold=None):
    cache_key = f"top10_{genre}_{sort_by}_{min_votes_threshold}_{max_votes_threshold}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    query = Movie.query
    if genre.lower() != "all":
        query = query.filter(Movie.genre.ilike(f"%{genre}%"))

    if sort_by == 'rating':
        movies = query.filter(Movie.rating != None).order_by(Movie.rating.desc()).all()
        movies = [m for m in movies if parse_votes_to_int(m.votes) >= min_votes_threshold]
        if max_votes_threshold is not None:
            movies = [m for m in movies if parse_votes_to_int(m.votes) <= max_votes_threshold]
        movies = movies[:10]
    elif sort_by == 'votes':
        all_movies = query.all()
        movies_with_votes = [m for m in all_movies if m.votes]
        movies = sorted(movies_with_votes, key=lambda m: parse_votes_to_int(m.votes), reverse=True)[:10]
    else:
        movies = []

    result = [m.to_dict() for m in movies]
    cache.set(cache_key, result)
    return result

@app.route("/api/movies", methods=["GET"])
def api_get_movies():
    genre = request.args.get("genre", default="all")
    sort_by = request.args.get("sortBy", default="rating")
    try:
        min_votes_threshold = int(request.args.get("minVotes", 0))
    except ValueError:
        min_votes_threshold = 0
    max_votes_param = request.args.get("maxVotes")
    try:
        max_votes_threshold = int(max_votes_param) if max_votes_param and max_votes_param.strip() != "" else None
    except ValueError:
        max_votes_threshold = None

    data = get_top_10_movies(genre, sort_by, min_votes_threshold, max_votes_threshold)
    return jsonify(data), 200

# --- Home Page Route ---
@app.route("/", methods=["GET"])
def home():
    return render_template('index.html', title="Project IMDB - Phase 2")

# --- Application Initialization ---
def init_app():
    with app.app_context():
        db.drop_all()    # Drop all tables for a clean start (useful during development)
        db.create_all()  # Create tables
        # Provide paths to your local TSV files
        seed_from_imdb_datasets(basics_tsv="title.basics.tsv", ratings_tsv="title.ratings.tsv")

if __name__ == "__main__":
    init_app()  # Initialize the database and seed data from the TSVs.
    app.run(debug=False, port=8080)