from flask import Flask
from flask_pymongo import PyMongo
import os

app = Flask(__name__)

app.secret_key = os.urandom(24)

# MongoDB Configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/memoir_db"  # Update DB name if needed
mongo = PyMongo(app)
db = mongo.db
db.entries.create_index([("user_id", 1), ("content", 1)], unique=True)  # Now `db` is available

# Import routes after Flask initialization (to avoid circular imports)
from app.routes import main
app.register_blueprint(main)