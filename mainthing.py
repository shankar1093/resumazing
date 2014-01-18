from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
from werkzeug import secure_filename
from pdfminer.pdfparser import PDFParser
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

UPLOAD_FOLDER = '/path/to/the/uploads'
ALLOWED_EXTENSIONS = set(['txt', 'pdf'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def parseRankedKeywords(xml_str):
    words = {}
    root = ET.fromstring(xml_str)
    for keyword in root.iter('keyword'):
        name = keyword[0].text
        relevance = keyword[1].text
        words[name] = relevance
    return words

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/test/<msg>")
def test(msg=None):
    url = "http://access.alchemyapi.com/calls/text/TextGetRankedKeywords?apikey=bae55da9dafaa2c7b9e8d78e678d69c4ce210ddf&text=%s" % msg
    # url = "http://127.0.0.1"
    try:
        r = requests.get(url)
        words = parseRankedKeywords(r.text)
        # words = {'boop':5,'abscd':6,'Alop':29}
        return render_template('keywords.html', original=msg, words=words)
    except requests.exceptions.ConnectionError as e:
        return "Connection Error"
    
    

if __name__ == "__main__":
    app.run(debug=True)