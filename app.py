import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory
from scraper import get_lineup
from matcher import get_recommendations

app = Flask(__name__, static_folder="static")


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/lineup")
def lineup():
    festival = request.args.get("festival", "").strip()
    if not festival:
        return jsonify({"error": "festival parameter is required"}), 400

    artists = get_lineup(festival)
    if not artists:
        return jsonify({"error": f"No lineup found for '{festival}'"}), 404

    return jsonify({"festival": festival, "artists": artists})


@app.route("/api/discover", methods=["POST", "OPTIONS"])
def discover():
    if request.method == "OPTIONS":
        return "", 204

    body = request.get_json(silent=True) or {}
    festival = (body.get("festival") or "").strip()
    seed_artist = (body.get("seed_artist") or "").strip()

    if not festival or not seed_artist:
        return jsonify({"error": "festival and seed_artist are required"}), 400

    artists = get_lineup(festival)
    if not artists:
        return jsonify({"error": f"No lineup found for '{festival}'"}), 404

    results = get_recommendations(seed_artist, artists)
    if not results:
        return jsonify({"error": "No matches found for this artist and festival combination"}), 404

    return jsonify({"festival": festival, "seed_artist": seed_artist, "results": results})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
