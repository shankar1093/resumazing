import os
from flask import Flask
from flask import jsonify
from flask import send_from_directory
from flask import render_template
from flask import request, redirect, url_for
from werkzeug import secure_filename
import requests
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import sys
import pyPdf
import json

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

app = Flask(__name__)

UPLOAD_FOLDER = '/home/sam/files'
ALLOWED_EXTENSIONS = set(['txt', 'pdf'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


########################################3

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/test', methods=['GET', 'POST'])
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
def getKeywords():
    msg = request.args.get('msg')
    words = get_keywords_from_text(msg)
    return render_template('keywords.html', original=msg, words=words)
    
@app.route("/entity")
def getEntities(query_type="TextGetRankedNamedEntities"):
    msg = request.args.get('msg')
    entities = get_entities_from_text(msg)
    format = request.args.get('format')
    if format == 'json':
        return json.dumps(entities)
    else:
        return render_template('entities.html', original=msg, entities=entities)

@app.route("/entityurl")
def getEntitiesFromURL():
    url = request.args.get('url')
    if not url:
        return "Need url parameter"
    data = get_entities_from_url(url)
    if not data:
        return "Error getting url data"

    format = request.args.get('format')
    if format == 'json':
        return json.dumps(data)
    else:
        return render_template('entities.html', original=url, entities=data)

# format = 'url' or 'text'
# msg = 'the url' or 'the text data'
def get_entities(format, msg):
    response = alchemyapi.entities(format, msg, { 'sentiment':1 })
    if response['status'] == 'OK':
        return [(e['text'], e['relevance'], e['type'], e['count'], e['sentiment']['type'], e['sentiment'].get('score') or 0) for e in response['entities']]   
    else:
        print('Error in entity extraction call: ', response['statusInfo'])
        return None

def get_keywords(format, msg):
    response = alchemyapi.keywords(format, msg, { 'sentiment':1 })
    if response['status'] == 'OK':
        return [(e['text'], e['relevance'], e['sentiment']['type'], e['sentiment'].get('score') or 0) for e in response['keywords']]
    else:
        print('Error in keyword extraction call: ', response['statusInfo'])
        return None

def get_concepts(format, msg):
    response = alchemyapi.concepts(format, msg, { 'sentiment':1 })
    if response['status'] == 'OK':
        return [(e['text'], e['relevance']) for e in response['concepts']]
    else:
        print('Error in concept extraction call: ', response['statusInfo'])
        return None

@app.route("/query", methods=['POST'])
def doQuery():
    format = request.form['format']

    # Job Listing URL
    job_url = request.form['url']
    if not job_url:
        return "Need url parameter"

    # Get Job Listing URL data
    job_entity_data = get_entities('url', job_url)
    job_keyword_data = get_keywords('url', job_url)
    job_concept_data = get_concepts('url', job_url)

    # Filter out City, StateOrCounty
    job_entity_location_data = filter(lambda x: x[2] in ["City", "StateOrCounty"],
                                      job_entity_data)
    job_entity_data = filter(lambda x: x[2] not in ["City", "StateOrCounty"],
                             job_entity_data)

    # Resume PDF file
    resume_entity_data = ""
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save PDF file to directory
        file.save(filepath)

        # Get text from PDF file
        resume_text = getPDFContent(filepath)

        # Get PDF text data
        resume_entity_data = get_entities('text', resume_text)
        resume_keyword_data = get_keywords('text', resume_text)
        resume_concept_data = get_concepts('text', resume_text)

        # Filter out City, StateOrCounty
        resume_entity_location_data = filter(lambda x: x[2] in ["City", "StateOrCounty"],
                                             resume_entity_data)
        resume_entity_data = filter(lambda x: x[2] not in ["City", "StateOrCounty"],
                                 resume_entity_data)

        data = {"job_entity_data": job_entity_data, 
                "job_keyword_data": job_keyword_data, 
                "job_concept_data": job_concept_data,
                "job_entity_location_data": job_entity_location_data,
                "resume_entity_data": resume_entity_data,
                "resume_keyword_data": resume_keyword_data,
                "resume_concept_data": resume_concept_data,
                "resume_entity_location_data": resume_entity_location_data}
    if format == 'json':
        return jsonify(**data)
    else:
        return render_template('results.html', data=data)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)