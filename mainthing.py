#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

from matplotlib import rcParams

rcParams['lines.linewidth'] = 2
rcParams['axes.grid'] = False
rcParams['axes.facecolor'] = 'white'
rcParams['patch.edgecolor'] = 'none'
rcParams['font.size'] = 18

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

UPLOAD_FOLDER = '/Users/shankar1093/Resumazing/resumazing'
ALLOWED_EXTENSIONS = set(['pdf'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


########################################3

@app.route('/')
def main_page():
    return render_template('index.html', resume=u'résumé')

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
    job_string = job_string.strip().lower()
    applicant_string = applicant_string.strip().lower()
    if job_string in applicant_string or applicant_string in job_string:
        return 1.0
    # If there's a good fit for either, then we're done

    job_words = job_string.split()
    applicant_words = applicant_string.split()
    n = min(len(job_words), len(applicant_words)) # min # of wors
    c = 0
    for word in job_words:
        if word in applicant_words:
            c += 1
    return 0.5 * float(c)/n # ratio of words found to not found

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

# Entity [ name, relevance, type, count, sentiment value, sentiment type?]
# Input: a list of all entity objects whose type is Degree for both inputs
def determine_degree_match(job_degrees, applicant_degrees):
    min_degree_req = 0
    for entity in job_degrees:
        degree = entity[0].strip()
        if degree.startswith('B') or "Bachelor" in degree:
            min_degree_req = max(1, min_degree_req)
        if degree.startswith('M') or "Master" in degree:
            min_degree_req = max(2, min_degree_req)

    actual_degree_type = 0
    for entity in applicant_degrees:
        degree = entity[0].strip()
        if degree.startswith('B') or "Bachelor" in degree:
            actual_degree_type = max(1, actual_degree_type)
        if degree.startswith('M') or "Master" in degree:
            actual_degree_type = max(2, actual_degree_type)
    
    if actual_degree_type > min_degree_req:
        return 1.5
    elif actual_degree_type == min_degree_req:
        return 1.0
    else:
        return 0.0

    # return 1. #Return 0.0 if no match, 1.0 if match, 1.5 if requirements exceeded
    
clusters = [['NSA'],['Coca-Cola'],['Experis'],['IBM', 'Comcast', 'KForce', 'Amazon', 'Verizon', 'Apple'],['Goldman Sachs', 'Wells-Fargo', 'Bloomberg', 'Chase'], ['Macys', 'Aflac', 'Home Depot', 'UPS', 'Walmart', 'ABM', 'DLC', 'United Technologies Corporation', 'McKesson', 'Staples', 'United Health Group', 'Dupont', 'McDonalds', 'Best Buy', 'Piper Morgan'], ['Northrop Grumman', 'Lockheed Martin']]
    
def score_resume(job_entities, job_keywords, job_concepts, applicant_entities, applicant_keywords, applicant_concepts):    
    text = lambda x: x[0]
    denominator = 10.
    print "DATA:"
    print job_entities
    print job_keywords
    print job_concepts
    print applicant_entities
    print applicant_keywords
    print applicant_concepts
    print clusters
    print "----"
    if not job_entities:
        job_entities = []
    if not applicant_entities:
        applicant_entities = []
        
    #Points for having a relevant degree
    job_degrees = map(text,filter(lambda x : x[2] == 'ProfessionalDegree', job_entities))
    applicant_degrees = map(text, filter(lambda x : x[2] == 'ProfessionalDegree', applicant_entities))
    if len(job_degrees) > 0 and len(applicant_degrees) > 0:
        degree_score = determine_degree_match(job_degrees, applicant_degrees)
    else:
        degree_score = 0.
        denominator -= 1.5
    
    #Points for having relevant job experience
    job_job_titles = map(text,filter(lambda x : x[2] == 'JobTitle', job_entities))
    applicant_job_titles = map(text,filter(lambda x : x[2] == 'JobTitle', applicant_entities))
    if len(job_job_titles) > 0 and len(applicant_job_titles) > 0:
        combinations = [[(x, y) for x in job_job_titles] for y in applicant_job_titles]
        job_title_score = max([determine_job_title_match(x, y) for subcoms in combinations for (x, y) in subcoms])
    else:
        job_title_score = 0.
        denominator -= 2.
    
    #Points for referencing relevant organizations or companies
    job_organizations = map(text,filter(lambda x : x[2] == 'Organization' or x[2] == 'Company', job_entities))
    applicant_organizations = map(text, filter(lambda x : x[2] == 'Organization' or x[2] == 'Company', applicant_entities))
    if len(job_organizations) > 0 and len(applicant_organizations) > 0:
        combinations = [[(x, y) for x in job_organizations] for y in applicant_organizations]
        organization_score = 0.5 * max([determine_string_match(x, y) for subcoms in combinations for (x, y) in subcoms])    
    else:
        organization_score = 0.
        denominator -= 0.5
    
    #Points for working for company in same cluster
    possible_companies = map(text, filter(lambda x : x[2] == 'Company', applicant_entities))
    cluster = []
    if len(possible_companies) > 0:
        cluster = filter(lambda x : possible_companies[0] in x, clusters)
    if len(cluster) > 0:
        cluster_score = 1.0 if len(set(applicant_organizations) & set(cluster)) > 0 else 0.
    else:
        cluster_score = 0.
        denominator -= 1.
    
    #Points for using relevant keywords
    if job_keywords and len(job_keywords) > 0 and applicant_keywords and len(applicant_keywords) > 0:
        combinations = [[(x, y) for x in map(text, job_keywords)] for y in map(text, applicant_keywords)]
        keyword_score = min(3., sum([determine_string_match(x, y) for subcoms in combinations for (x, y) in subcoms]))
    else:
        keyword_score = 0.
        denominator -= 3.
    
    #Points for using relevant concepts
    if job_concepts and len(job_concepts) > 0 and applicant_concepts and len(applicant_concepts) > 0:
        combinations = [[(x, y) for x in map(text, job_concepts)] for y in map(text, applicant_concepts)]
        concept_score = min(2., sum([determine_string_match(x, y) for subcoms in combinations for (x, y) in subcoms]))
    else:
        concept_score = 0.
        denominator -= 2.
    
    if denominator == 0:
        # No data was given.
        return None
    final_score = 10. * (degree_score + job_title_score + organization_score + cluster_score + keyword_score + concept_score) / denominator
    
    return final_score
    
def remove_border(axes=None, top=False, right=False, left=True, bottom=True):
    """
    Minimize chartjunk by stripping out unnecessary plot borders and axis ticks
    
    The top/right/left/bottom keywords toggle whether the corresponding plot border is drawn
    """
    ax = axes or plt.gca()
    ax.spines['top'].set_visible(top)
    ax.spines['right'].set_visible(right)
    ax.spines['left'].set_visible(left)
    ax.spines['bottom'].set_visible(bottom)
    
    #turn off all ticks
    ax.yaxis.set_ticks_position('none')
    ax.xaxis.set_ticks_position('none')
    
    #now re-enable visibles
    if top:
        ax.xaxis.tick_top()
    if bottom:
        ax.xaxis.tick_bottom()
    if left:
        ax.yaxis.tick_left()
    if right:
        ax.yaxis.tick_right()

def draw_spectrum(scores):
    bins = range(1,8)
    fig = plt.figure()
    ax = plt.gca()
    ax.bar(range(7), scores, color=['b','y','aqua','m','g','indigo','r'])
    remove_border()
    ax.set_ylim([0,10])
    ax.set_xlabel('Group of Companies')
    ax.set_ylabel('Compatibility with Group')
    ax.set_title('Your Personal Spectrum of Performance')
    # plt.show()
    fig.savefig(UPLOAD_FOLDER + '/spectrum.png')
    
def generate_group_scores(applicant_entities, applicant_keywords, applicant_concepts):
    with open('spectrum_data.json', 'r') as f:
       json_data=f.read()
    data = json.loads(json_data)
    scores = [score_resume(data[str(i)]['entities'], data[str(i)]['keywords'], data[str(i)]['concepts'], applicant_entities, applicant_keywords, applicant_concepts) for i in range(len(data))]
    draw_spectrum(scores)
    return scores

@app.route("/query", methods=['POST'])
def doQuery():
    # format = request.form['format']

    url_or_text = request.form['url_or_text']
    if not url_or_text:
        return "Need url or text parameter"

    # print url_or_text

    if url_or_text.startswith('http://') or url_or_text.startswith('https://'):
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

        print "PDF TEXT:"
        print resume_text
        print

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

        # try:
        final_score = score_resume(job_entity_data, job_keyword_data, job_concept_data, resume_entity_data, resume_keyword_data, resume_concept_data)
        # except Exception, e:
        #     print "Error generating final score", e
        #     final_score = -1

        # Generate Spectrum PNG
        spectrum_scores = generate_group_scores(resume_entity_data, resume_keyword_data, resume_concept_data)

    else:
        final_score = -1
        resume_entity_data = None
        resume_entity_location_data = None
        resume_keyword_data = None
        resume_concept_data = None
        spectrum_scores = None
    
    data = {"final_score": final_score,
            "spectrum_scores":spectrum_scores,
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
    app.run(host='0.0.0.0', port=8080, debug=True)