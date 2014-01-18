import os
from flask import Flask
from flask import send_from_directory
from flask import render_template
from flask import request, redirect, url_for
from werkzeug import secure_filename
import requests
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import sys
import pyPdf

from alchemyapi import AlchemyAPI
alchemyapi = AlchemyAPI()

def getPDFContent(path):
    content = ""
    # Load PDF into pyPDF
    pdf = pyPdf.PdfFileReader(file(path, "rb"))
    # Iterate pages
    for i in range(0, pdf.getNumPages()):
        # Extract text from page and add to content
        content += pdf.getPage(i).extractText() + " \n"
    # Collapse whitespace
    content = u" ".join(content.replace(u"\xa0", u" ").strip().split())
    return content

# Secret Key
API_KEY = "bae55da9dafaa2c7b9e8d78e678d69c4ce210ddf"

app = Flask(__name__)

UPLOAD_FOLDER = '/home/sam/files'
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
        entities.append( (text, relevance, _type, count) )
    return entities

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


########################################3

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            text = getPDFContent(filepath)
            print "File uploaded successfully"
            return render_template('loadResume.html', text=text)
            # return redirect(url_for('uploaded_file',
            #                         filename=filename))
    return render_template('loadResume.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route("/keyword")
@app.route("/keyword/")
@app.route("/keyword/<query_type>")
def getKeywords(query_type="TextGetRankedKeywords"):
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

@app.route("/entityurl")
def getEntitiesFromURL():
    url = request.args.get('url')
    if not url:
        return "Need url parameter"
    data = get_entities_from_url(url)
    if not data:
        return "Error getting url data"
    return render_template('entities.html', original=url, entities=data)

def get_entities_from_url(url):
	response = alchemyapi.entities('url',url, { 'sentiment':1 })
	if response['status'] == 'OK':
		return [(e['text'], e['relevance'], e['type']) for e in response['entities']]	
	else:
		print('Error in entity extraction call: ', response['statusInfo'])
		return None

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)