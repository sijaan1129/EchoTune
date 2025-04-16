from flask import Flask, render_template, redirect, url_for
import os
from pymongo import MongoClient

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["echotune"]

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/settings")
def settings():
    server_id = "123456789012345678"  # Replace with dynamic server ID in the future
    settings = db["settings"].find_one({"server_id": server_id})

    return render_template("settings.html", settings=settings)

if __name__ == "__main__":
    app.run(debug=True)
  
