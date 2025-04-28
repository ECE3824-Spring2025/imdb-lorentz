from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    jsonify
)
import base64
import sqlalchemy  # pip install sqlalchemy
import sqlalchemy.orm
from flask_sqlalchemy import SQLAlchemy  # pip install flask_sqlalchemy
from flask_caching import Cache         # pip install flask_caching
from flask_cors import CORS             # pip install flask_cors
import os
import pandas as pd                     # pip install pandas
from tqdm import tqdm                   # pip install tqdm

# ─── Helper: Base64 encode/decode ──────────────────────────────────────────────
def encode_base64(value: str) -> str:
    """Encode a string to Base64."""
    return base64.b64encode(value.encode('utf-8')).decode('utf-8')

def decode_base64(encoded: str) -> str:
    """Decode a Base64 string."""
    return base64.b64decode(encoded.encode('utf-8')).decode('utf-8')

# ─── Monkey-patch SQLAlchemy Session.get_bind to avoid extra-arg errors ──────
def patched_get_bind(self, mapper=None, clause=None):
    return self.bind
sqlalchemy.orm.Session.get_bind = patched_get_bind

if not hasattr(sqlalchemy, '__all__'):
    sqlalchemy.__all__ = []
if not hasattr(sqlalchemy.orm, '__all__'):
    sqlalchemy.orm.__all__ = []
if not hasattr(sqlalchemy.orm, 'dynamic_loader'):
    sqlalchemy.orm.dynamic_loader = lambda *args, **kwargs: None

# ─── Subclass SQLAlchemy to re-expose missing ORM attributes ─────────────────
class PatchedSQLAlchemy(SQLAlchemy):
    pass

PatchedSQLAlchemy.relationship   = sqlalchemy.orm.relationship
PatchedSQLAlchemy.relation       = sqlalchemy.orm.relationship
PatchedSQLAlchemy.dynamic_loader = sqlalchemy.orm.dynamic_loader
PatchedSQLAlchemy.Column         = sqlalchemy.Column
PatchedSQLAlchemy.Integer        = sqlalchemy.Integer
PatchedSQLAlchemy.String         = sqlalchemy.String
PatchedSQLAlchemy.Float          = sqlalchemy.Float

# ─── Flask app + extensions ─────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI']        = os.getenv(
    'DATABASE_URI',
    'mysql+pymysql://admin:password@imdb.cxc0y8aocyro.us-east-1.rds.amazonaws.com:3306/imdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE']                     = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT']          = 300

db    = PatchedSQLAlchemy(app)
cache = Cache(app)

# ─── Database Model ─────────────────────────────────────────────────────────
class Movie(db.Model):
    __tablename__ = 'movies'
    id     = db.Column(db.String(20), primary_key=True)  # IMDb tconst
    name   = db.Column(db.String(200), nullable=False, default="Unknown")
    rating = db.Column(db.Float, nullable=True)
    votes  = db.Column(db.String(20), nullable=True)
    genre  = db.Column(db.String(200), nullable=False, default="Unknown")

    def to_dict(self):
        return {
            "id":     self.id,
            "name":   self.name,
            "rating": self.rating,
            "votes":  self.votes,
            "genre":  self.genre
        }

def parse_votes_to_int(votes_str):
    if votes_str and votes_str.endswith('M'):
        return int(float(votes_str[:-1]) * 1_000_000)
    if votes_str and votes_str.endswith('K'):
        return int(float(votes_str[:-1]) * 1_000)
    return int(votes_str) if votes_str and votes_str.isdigit() else 0

# ─── Seed helper (optional) ─────────────────────────────────────────────────
def seed_from_imdb_datasets(basics_tsv, ratings_tsv, chunk_size=10000):
    with app.app_context():
        total_lines = sum(1 for _ in open(basics_tsv, 'r', encoding='utf-8')) - 1
        total_chunks = (total_lines // chunk_size) + 1
        df_list = []
        for chunk in tqdm(pd.read_csv(
                basics_tsv, sep='\t', na_values='\\N',
                low_memory=False, chunksize=chunk_size
            ), total=total_chunks, desc="Reading title.basics.tsv"):
            df_list.append(chunk[chunk['titleType'] == 'movie'])
        df_basics = pd.concat(df_list, ignore_index=True)
        df_ratings = pd.read_csv(ratings_tsv, sep='\t', na_values='\\N')
        df_merged = pd.merge(df_basics, df_ratings, on='tconst', how='inner')

        for _, row in tqdm(df_merged.iterrows(), total=len(df_merged), desc="Seeding DB"):
            tconst = row['tconst']
            movie = db.session.get(Movie, tconst)
            data = {
                'name':   row['primaryTitle'] if pd.notna(row['primaryTitle']) else "Unknown",
                'rating': row['averageRating'] if pd.notna(row['averageRating']) else None,
                'votes':  str(int(row['numVotes'])) if pd.notna(row['numVotes']) else None,
                'genre':  row['genres'] if pd.notna(row['genres']) else "Unknown"
            }
            if movie:
                for k, v in data.items():
                    setattr(movie, k, v)
            else:
                db.session.add(Movie(id=tconst, **data))
        db.session.commit()

# ─── Top-10 API with caching ─────────────────────────────────────────────────
@app.route("/api/movies", methods=["GET"])
def api_get_movies():
    genre   = request.args.get("genre", default="all")
    sort_by = request.args.get("sortBy", default="rating")
    try:
        min_votes = int(request.args.get("minVotes", 0))
    except ValueError:
        min_votes = 0
    mvp       = request.args.get("maxVotes")
    try:
        max_votes = int(mvp) if mvp else None
    except ValueError:
        max_votes = None

    # build & cache the query
    key = f"top10_{genre}_{sort_by}_{min_votes}_{max_votes}"
    cached = cache.get(key)
    if cached:
        return jsonify(cached), 200

    query = Movie.query
    if genre.lower() != "all":
        query = query.filter(Movie.genre.ilike(f"%{genre}%"))

    if sort_by == 'rating':
        lst = query.filter(Movie.rating != None).order_by(Movie.rating.desc()).all()
        lst = [m for m in lst if parse_votes_to_int(m.votes) >= min_votes]
        if max_votes is not None:
            lst = [m for m in lst if parse_votes_to_int(m.votes) <= max_votes]
        lst = lst[:10]
    else:
        allm = query.all()
        lst = sorted(
            [m for m in allm if m.votes],
            key=lambda m: parse_votes_to_int(m.votes),
            reverse=True
        )[:10]

    result = [m.to_dict() for m in lst]
    cache.set(key, result)
    return jsonify(result), 200

# ─── LOGIN / REGISTER / DASHBOARD / LOGOUT ────────────────────────────────────

# Show login page
@app.route("/", methods=["GET"])
def show_login():
    return render_template("login.html")

# Handle login form (GET shows form, POST processes it)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        raw_user = request.form["username"]
        raw_pw   = request.form["password"]
        enc_user = encode_base64(raw_user)
        enc_pw   = encode_base64(raw_pw)

        try:
            with open("users.txt") as f:
                for line in f:
                    saved_user, saved_pw = line.strip().split(":", 1)
                    if saved_user == enc_user and saved_pw == enc_pw:
                        # successful login → welcome (auto-redirects in template)
                        return render_template("welcome.html", username=raw_user)
        except FileNotFoundError:
            pass

        # failed authentication
        return render_template("login.html", error="Invalid username or password.")

    # GET → just show the form
    return render_template("login.html")

# Registration page & form
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        raw_user = request.form["username"]
        raw_pw   = request.form["password"]
        enc_user = encode_base64(raw_user)
        enc_pw   = encode_base64(raw_pw)

        with open("users.txt", "a") as f:
            f.write(f"{enc_user}:{enc_pw}\n")

        return render_template("registered_popup.html", username=raw_user)

    return render_template("register.html")

# Dashboard (your index.html)
@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

# Logout simply redirects to login
@app.route("/logout")
def logout():
    return redirect(url_for("show_login"))

# ─── Run the server ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)