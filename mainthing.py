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
def get_entities(format, msg, sentiment=1):
    response = alchemyapi.entities(format, msg, { 'sentiment':sentiment })
    if response['status'] == 'OK':
        if sentiment == 1:
            return [(e['text'], e['relevance'], e['type'], e['count'], e['sentiment']['type'], e['sentiment'].get('score') or 0) for e in response['entities']]   
        else:
            return [(e['text'], e['relevance'], e['type'], e['count']) for e in response['entities']]   
    else:
        print('Error in entity extraction call: ', response['statusInfo'])
        return None

def get_keywords(format, msg, sentiment=1):
    response = alchemyapi.keywords(format, msg, { 'sentiment':sentiment })
    if response['status'] == 'OK':
        if sentiment == 1:
            return [(e['text'], e['relevance'], e['sentiment']['type'], e['sentiment'].get('score') or 0) for e in response['keywords']]
        else:
            return [(e['text'], e['relevance']) for e in response['keywords']]
    else:
        print('Error in keyword extraction call: ', response['statusInfo'])
        return None

def get_concepts(format, msg):
    response = alchemyapi.concepts(format, msg)
    if response['status'] == 'OK':
        return [(e['text'], e['relevance']) for e in response['concepts']]
    else:
        print('Error in concept extraction call: ', response['statusInfo'])
        return None
		
def determine_string_match(job_string, applicant_string):
	ret = 1. if applicant_string.lower().find(job_string.lower()) >= 0 else 0.
	if ret == 0:
		ret = 0.5 * max([determine_string_match(job_string, sub) for sub in applicant_string.split()])

def determine_job_title_match(job_string, applicant_string):
	ret = 2. if applicant_string.lower().find(job_string.lower()) >= 0 else 0.
	if ret == 0:
		ret = 1. * max([determine_string_match(job_string, sub) for sub in applicant_string.split()])
	if applicant_string.lower().find('intern') >= 0 and job_string.lower().find('intern') < 0:
		ret /= 2.
	return ret
# Returns json data for a job query ...?url=<THE_URL>
@app.route("/query/job", methods=['GET','POST'])
def doJobQuery():
    # Job Listing URL
    if request.method == 'GET':
        job_url = request.args.get('url')
    else:
        job_url = request.form['url']
    if not job_url:
        return "Need url parameter"
    # Get Job Listing URL data
    job_entity_data = get_entities('url', job_url, 0)
    job_keyword_data = get_keywords('url', job_url, 0)
    job_concept_data = get_concepts('url', job_url)

    # Filter out City, StateOrCounty
    if job_entity_data:
        job_entity_location_data = filter(lambda x: x[2] in ["City", "StateOrCounty"],
                                          job_entity_data)
        job_entity_data = filter(lambda x: x[2] not in ["City", "StateOrCounty"],
                                 job_entity_data)
    else:
        job_entity_location_data = None

    data = {"job_url": job_url,
            "job_entity_data": job_entity_data, 
            "job_keyword_data": job_keyword_data, 
            "job_concept_data": job_concept_data,
            "job_entity_location_data": job_entity_location_data}
    
    return jsonify(**data)

# Input: a list of all entity objects whose type is Degree for both inputs
def determine_degree_match(job_degrees, applicant_degrees):
	return 1. #Return 0.0 if no match, 1.0 if match, 1.5 if requirements exceeded
	
def score_resume(job_entities, job_keywords, job_concepts, applicant_entities, applicant_keywords, applicant_concepts, clusters):
	text = lambda x: x[0]
	cluster = filter(lambda x : company in x, clusters)
	#Points for having a relevant degree
	job_degrees = map(text,filter(lambda x : x[2] == 'ProfessionalDegree', job_entities))
	applicant_degrees = map(text, filter(lambda x : x[2] == 'ProfessionalDegree', applicant_entities))
	degree_score = determine_degree_match(job_degrees, applicant_degrees)
	#Points for having relevant job experience
	job_job_titles = map(text,filter(lambda x : x[2] == 'JobTitle', job_entities))
	applicant_job_titles = map(text,filter(lambda x : x[2] == 'JobTitle', applicant_entities))
	combinations = [[(x, y) for x in job_job_titles] for y in applicant_job_titles]
	job_title_score = max([determine_job_title_match(x, y) for (x, y) in combinations])
	#Points for referencing relevant organizations or companies
	job_organizations = map(text,filter(lambda x : x[2] == 'Organization' or x[2] == 'Company', job_entities))
	applicant_organizations = map(text, filter(lambda x : x[2] == 'Organization' or x[2] == 'Company', applicant_entities))
	combinations = [[(x, y) for x in job_organizations] for y in applicant_organizations]
	organization_score = 0.5 * max([determine_string_match(x, y) for (x, y) in combinations])	
	#Points for working for company in same cluster
	cluster_score = 1.0 if len(set(applicant_organizations) & set(cluster)) > 0 else 0.
	#Points for using relevant keywords
	combinations = [[(x, y) for x in map(text, job_keywords)] for y in map(text, applicant_keywords)]
	keyword_score = max(3., sum([determine_string_match(x, y) for (x, y) in combinations]))
	#Points for using relevant concepts
	combinations = [[(x, y) for x in map(text, job_concepts)] for y in map(text, applicant_concepts)]
	concept_score = max(2., sum([determine_string_match(x, y) for (x, y) in combinations]))
	final_score = degree_score + job_title_score + organization_score + cluster_score + keyword_score + concept_score
	
	return final_score


@app.route("/query", methods=['POST'])
def doQuery():
    # format = request.form['format']

    url_or_text = request.form['url_or_text']
    if not url_or_text:
        return "Need url or text parameter"

    # print url_or_text

    if url_or_text.startswith('http://'):
        # Job Listing URL
        job_url = url_or_text
        # Get Job Listing URL data
        job_entity_data = get_entities('url', job_url)
        job_keyword_data = get_keywords('url', job_url)
        job_concept_data = get_concepts('url', job_url)
    else:
        try:
            job_text = url_or_text.encode('utf-8')
        except:
            job_text = url_or_text
        # Get Job Listing URL data
        job_entity_data = get_entities('text', job_text)
        job_keyword_data = get_keywords('text', job_text)
        job_concept_data = get_concepts('text', job_text)

    # Filter out City, StateOrCounty
    if job_entity_data:
        job_entity_location_data = filter(lambda x: x[2] in ["City", "StateOrCounty"],
                                          job_entity_data)
        job_entity_data = filter(lambda x: x[2] not in ["City", "StateOrCounty"],
                                 job_entity_data)
    else:
        job_entity_location_data = None

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
        if resume_entity_data:
            resume_entity_location_data = filter(lambda x: x[2] in ["City", "StateOrCounty"],
                                                 resume_entity_data)
            resume_entity_data = filter(lambda x: x[2] not in ["City", "StateOrCounty"],
                                     resume_entity_data)
        else:
            resume_entity_location_data = None

        try:
            final_score = score_resume(job_entity_data, job_keyword_data, job_concept_data, resume_entity_data, resume_keyword_data, resume_concept_data, [])
        except Exception, e:
            print "Error generating final score", e
            final_score = -1
    else:
        final_score = -1
        resume_entity_data = None
        resume_entity_location_data = None
        resume_keyword_data = None
        resume_concept_data = None
    
    data = {"final_score": final_score,
            "job_entity_data": job_entity_data, 
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