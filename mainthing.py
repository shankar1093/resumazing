from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
from werkzeug import secure_filename
from pdfminer.pdfparser import PDFParser
import requests
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError

# Secret Key
API_KEY = "bae55da9dafaa2c7b9e8d78e678d69c4ce210ddf"

app = Flask(__name__)

UPLOAD_FOLDER = '/path/to/the/uploads'
ALLOWED_EXTENSIONS = set(['txt', 'pdf'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def parseRankedKeywords(xml_str):
    words = {}
    root = ET.fromstring(xml_str)
    for keyword in root.iter('keyword'):
        text = keyword[0].text
        relevance = keyword[1].text
        words[text] = relevance
    return words

def parseRankedEntities(xml_str):
    entities = []
    root = ET.fromstring(xml_str)
    for entity in root.iter('entity'):
        _type = entity[0].text
        relevance = entity[1].text
        count = entity[2].text
        text = entity[3].text
        entities.append( (_type, relevance, count, text) )
    return entities


@app.route("/")
def hello():    
    return render_template('loadResume.html')

@app.route("/test")
@app.route("/test/")
@app.route("/test/<query_type>")
def test(query_type="TextGetRankedKeywords"):
    msg = request.args.get('msg')
    if not msg:
        return "Need to add ?msg= parameter"
    url = "http://access.alchemyapi.com/calls/text/%s?apikey=%s&text=%s" % (query_type, API_KEY, msg)
    # url = "http://127.0.0.1"
    try:
        r = requests.get(url)
        words = parseRankedKeywords(r.text)
        # words = {'boop':5,'abscd':6,'Alop':29}
        return render_template('keywords.html', original=msg, words=words)
    except requests.exceptions.ConnectionError as e:
        return "Connection Error"
    
@app.route("/entity")
def getEntities(query_type="TextGetRankedNamedEntities"):
    msg = request.args.get('msg')
    if not msg:
        return "Need to provide text in a 'msg' parameter"
    url = "http://access.alchemyapi.com/calls/text/%s?apikey=%s&text=%s" % (query_type, API_KEY, msg)
    try:
        r = requests.get(url)
        print "----" 
        print r.text
        print "===="
        try:
            entities = parseRankedEntities(r.text)
            # entities = ( (1,2,3,4), ('blah',3,6,3), (69,43,23,12) )
            return render_template('entities.html', original=msg, entities=entities)
        except ParseError as e:
            return r.text
    except requests.exceptions.ConnectionError as e:
        return "Connection Error"

if __name__ == "__main__":
    app.run(debug=True)