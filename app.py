import os
from flask import Flask, request, jsonify
from PIL import Image
from werkzeug.utils import secure_filename
from gemini_ocr import extract_text

app = Flask(__name__)

# 업로드 허용 확장자
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        try:
            image = Image.open(file.stream)
            result = extract_text(image)

            return jsonify({
                "filename": filename,
                "extracted_articles": result
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "File type not allowed"}), 400

@app.route("/")
def index():
    return "✅ Object OCR is running!"

if __name__ == "__main__":
    app.run(debug=True)


