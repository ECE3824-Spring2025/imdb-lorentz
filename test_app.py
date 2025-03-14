import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

import unittest
import json

from phase_2_imdb.app import app, db, Movie, parse_votes_to_int, get_top_10_movies

class MovieAppTestCase(unittest.TestCase):
    def setUp(self):
        # Configure the app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            # Insert a sample movie into the database for testing
            test_movie = Movie(
                id="tt0000001",
                name="Test Movie",
                rating=8.5,
                votes="1K",
                genre="Action"
            )
            db.session.add(test_movie)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_parse_votes_to_int(self):
        self.assertEqual(parse_votes_to_int("1K"), 1000)
        self.assertEqual(parse_votes_to_int("1.5K"), 1500)
        self.assertEqual(parse_votes_to_int("2M"), 2000000)
        self.assertEqual(parse_votes_to_int("123"), 123)
        self.assertEqual(parse_votes_to_int(""), 0)
        self.assertEqual(parse_votes_to_int(None), 0)

    def test_get_top_10_movies_rating(self):
        with app.app_context():
            movies = get_top_10_movies("Action", "rating")
            self.assertIsInstance(movies, list)
            self.assertGreaterEqual(len(movies), 1)
            self.assertEqual(movies[0]["name"], "Test Movie")

    def test_api_get_movies_endpoint(self):
        response = self.app.get("/api/movies?genre=Action&sortBy=rating")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        movie_names = [movie["name"] for movie in data]
        self.assertIn("Test Movie", movie_names)

if __name__ == '__main__':
    unittest.main()
