import os
import datetime
from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask setup
app = Flask(__name__)

# Serve front-end
@app.get("/")
def index():
    return render_template("index.html")

# Azure setup
CONTAINER_NAME = os.getenv("IMAGES_CONTAINER")
BLOB_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_ACCOUNT_URL = os.getenv("STORAGE_ACCOUNT_URL")

# Create Blob Service and Container Clients
bsc = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
cc = bsc.get_container_client(CONTAINER_NAME)

# Ensure container exists (public-read)
try:
    cc.create_container(public_access="container")
except Exception:
    pass  # Already exists


# ========== UPLOAD ENDPOINT ==========
@app.post("/api/v1/upload")
def upload():
    """Upload an image to Azure Blob Storage"""
    if "file" not in request.files:
        return jsonify(ok=False, error="No file uploaded"), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify(ok=False, error="Empty filename"), 400

    # Enforce image file type and max size (10 MB)
    if not f.mimetype.startswith("image/"):
        return jsonify(ok=False, error="Only image files allowed"), 400

    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify(ok=False, error="File too large (max 10MB)"), 400

    # Sanitize filename and prepend timestamp
    filename = secure_filename(f.filename)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    blob_name = f"{timestamp}-{filename}"

    try:
        cc.upload_blob(name=blob_name, data=f, overwrite=True)
        url = f"{STORAGE_ACCOUNT_URL}/{CONTAINER_NAME}/{blob_name}"
        app.logger.info(f"Uploaded: {url}")
        return jsonify(ok=True, url=url)
    except Exception as e:
        app.logger.error(f"Upload failed: {e}")
        return jsonify(ok=False, error=str(e)), 500


# ========== GALLERY ENDPOINT ==========
@app.get("/api/v1/gallery")
def gallery():
    """Return all image URLs from Blob Storage"""
    try:
        blobs = cc.list_blobs()
        urls = [
            f"{STORAGE_ACCOUNT_URL}/{CONTAINER_NAME}/{b.name}" for b in blobs
        ]
        urls.sort(reverse=True)
        return jsonify(ok=True, gallery=urls)
    except Exception as e:
        app.logger.error(f"Gallery failed: {e}")
        return jsonify(ok=False, error=str(e)), 500


# ========== HEALTH ENDPOINT ==========
@app.route("/api/v1/health", methods=["GET"])
def health():
    """Simple health check"""
    return jsonify({"ok": True}), 200


# Run the app locally
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
