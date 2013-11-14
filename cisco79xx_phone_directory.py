#!/usr/bin/env python

import re
import unicodedata
from flask import Flask, request
from xml.etree import ElementTree

# CONFIGURATION REQUIRED:
# Change these to fit your needs, the port has to match the one on
# which the webserver listens to. It is required to hardcode the port
# number in order to work around a bug with the Cisco 79xx browser.
CONTACTS_FILE = "contacts.xml"
PORT = 5006

app = Flask(__name__)
DIGITS_RE = re.compile(r'[^\d]+')


def remove_accents(str):
    """
    Thanks to MiniQuark:
    http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string/517974#517974
    """
    nkfd_form = unicodedata.normalize('NFKD', unicode(str))
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])


class DirectoryEntry:
    """
    Contains the phone number, owner's name and the label associated
    to the phone number.
    """
    def __init__(self, number, name, label):
        # Discard non-digit characters
        self.number = DIGITS_RE.sub('', number)
        self.name = remove_accents(unicode(name))
        # The label may contain schema information, discard it
        self.label = remove_accents(unicode(label.replace('http://schemas.google.com/g/2005#', '')))

    def __str__(self):
        if self.label:
            return "%s (%s)" % (self.name, self.label,)
        else:
            return self.name


def get_directory():
    """
    Parses the Google Contacts file and returns its contents as a list
    of DirectoryEntry instances.
    """
    with file(CONTACTS_FILE) as f:
        root = ElementTree.parse(f).getroot()
    directory = []
    for children in root.findall('{http://www.w3.org/2005/Atom}entry'):
        # Create a new entry for every phone number that belongs to the same person,
        # which also filters out the persons that do not have phone numbers
        phonenumbers = children.findall('{http://schemas.google.com/g/2005}phoneNumber')
        for phone in phonenumbers:
            number = phone.text
            name = children.find('{http://www.w3.org/2005/Atom}title').text
            # Tests showed that the label can be an attribute named either rel or label
            label = phone.attrib.get('rel', phone.attrib.get('label', ''))
            directory.append(DirectoryEntry(number, name, label))
    return directory


def generate_directory_xml(directory):
    """
    Generates the XML required to display the phone directory from
    the list of DirectoryEntry instances given as a parameter.
    """
    xml = "<CiscoIPPhoneDirectory>\n"
    xml += "\t<Title>Phone directory</Title>\n"
    xml += "\t<Prompt>Select an entry.</Prompt>\n"
    for entry in directory:
        xml += "\t<DirectoryEntry>\n"
        xml += "\t\t<Name>%s</Name>\n" % entry
        xml += "\t\t<Telephone>%s</Telephone>\n" % entry.number
        xml += "\t</DirectoryEntry>\n"
    xml += "</CiscoIPPhoneDirectory>\n"
    return xml


def generate_search_xml():
    """
    Generates the XML required to display a phone directory search
    page on the Cisco 79xx IP phones.
    """
    xml = "<CiscoIPPhoneInput>\n"
    xml += "\t<Title>Search for an entry</Title>\n"
    xml += "\t<Prompt>Enter a search keyword.</Prompt>\n"
    # For a reason unbeknown to me, the Cisco 7940 IP phone is the only
    # device/browser for which the request.environ["SERVER_PORT"] value is
    # set to 80 although the URL accessed is on another port, therefore
    # forcing us to use a hardcoded port number
    xml += "\t<URL>http://%s:%d/directory.xml</URL>\n" % (request.environ["SERVER_NAME"], PORT,)
    xml += "\t<InputItem>\n"
    xml += "\t\t<DisplayName>Keyword</DisplayName>\n"
    xml += "\t\t<QueryStringParam>keyword</QueryStringParam>\n"
    xml += "\t\t<InputFlags></InputFlags>\n"
    xml += "\t\t<DefaultValue></DefaultValue>\n"
    xml += "\t</InputItem>\n"
    xml += "</CiscoIPPhoneInput>\n"
    return xml


@app.route("/directory.xml")
def index():
    """
    Serves the phone directory search page and the search results.
    """
    # We have received the query string, display the results
    if "keyword" in request.args:
        keyword = request.args["keyword"]
        # Get the directory and filter the entries based on the keyword, then sort them
        directory = sorted([entry for entry in get_directory() if keyword.lower() in unicode(entry.name).lower() or keyword in unicode(entry.number)], key=lambda entry: unicode(entry))
        xml = generate_directory_xml(directory)
    # If we haven't received the query string, display the search menu
    else:
        xml = generate_search_xml()
    response = app.response_class(xml, mimetype='text/xml')
    return response


if __name__ == "__main__":
    """
    Starts the debug webserver if the script is called from the command-line.
    WARNING: The debug webserver uses HTTP/1.0 by default, which is not
    supported by the Cisco 79xx IP phones. Have a look at the README file
    if you haven't already!
    """
    app.run(debug=True)

