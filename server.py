from flask import Flask, request, send_from_directory
from main import extract_info_from_link

app = Flask(__name__)

@app.route("/api/info_from_link", methods=['POST'])
def info_from_link():
    data = request.json
    link = data['link']
    return extract_info_from_link(link)

@app.route('/<path:path>')
def send_report(path):
    return send_from_directory('static', path)