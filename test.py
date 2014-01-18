import xml.etree.ElementTree as ET

words = {}
root = ET.parse('test.xml')
for keyword in root.iter('keyword'):
    name = keyword[0].text
    relevance = keyword[1].text
    words[name] = relevance
print words
for word in words.items():
    print word[0] + ": " + word[1]