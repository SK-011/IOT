#!/usr/bin/env python
import os
import pickle
import base64
import json
import requests
from time import time, sleep
import signal
import sys
from random import randint
import logging

# Suppress the annoying requests HTTPs warning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings (InsecureRequestWarning)

from pprint import pprint


serverIp = "127.0.0.1"
serverPort = 65535
serverUrl = "json"
logFile = "client.log"
user = "iot"
password = ""
workerId = 1337
flag = ""

logging.basicConfig (filename=logFile, level=logging.DEBUG)


def sigintHandler (signal, frame):
	global eventRun
	print ("\t[!]\tCaugth SIGINT, exiting...")
	sys.exit (0)


# Class containing all REST API functions
class restApi ():
	url = None
	auth = None
	headers = {}
	result = None
	resultJson = None
	cookies = []

	# Init the api_request object with an url
	def __init__ (self):
		pass


	# Set the request's URL
	def setUrl (self, url):
		self.url = url


	# Set auth for the request
	def setAuth (self, usr, pwd):
		value = usr + ':' + pwd
		value = base64.b64encode (value).replace ('\n', '')
		self.headers['Authorization'] = 'Basic ' + value


	# Add a custom header to the query
	def setHeader (self, key, value):

		if (key not in self.headers):
			self.headers[key] = value


	# Send the GET request and retrieve the result as JSON
	def get (self):

		# If a session cookie has been saved, use it instead of Authorization HTTP header
		if (self.cookies):

			if ( 'Authorization' in self.headers):
				del self.headers['Authorization']

			self.result = requests.get (self.url, headers=self.headers, cookies=self.cookies, verify=False)

		else:
			self.result = requests.get (self.url, headers=self.headers, verify=False)

			if (self.result.cookies):
				self.cookies = self.result.cookies

		try:
			self.resultJson = json.loads (self.result.content)

		except ValueError:
			print ("[!] [common]\tFatal error during result JSON parsing")


	# Send the POST request and retrieve the result as JSON
	def post (self, payload):

		# Convert the nested dict payload into a proper JSON payload
		jsonPayload = json.dumps (payload)

		# If a session cookie has been saved, use it instead of Authorization HTTP header
		if (self.cookies):

			if ( 'Authorization' in self.headers):
				del self.headers['Authorization']

			self.result = requests.post (self.url, headers=self.headers, cookies=self.cookies, verify=False, data=jsonPayload)

		else:
			self.result = requests.post (self.url, headers=self.headers, verify=False, data=jsonPayload)

			if (self.result.cookies):
				self.cookies = self.result.cookies

		try:
			self.resultJson = json.loads (self.result.content)

		except ValueError:
			print ("[!] [common]\tError during JSON result parsing")

	# Send the PATCH request and retrieve the result as JSON
	def patch (self, payload):

		# Convert the nested dict payload into a proper JSON payload
		jsonPayload = json.dumps (payload)

		# If a session cookie has been saved, use it instead of Authorization HTTP header
		if (self.cookies):
			if ( 'Authorization' in self.headers):
				del self.headers['Authorization']

			self.result = requests.patch (self.url, headers=self.headers, cookies=self.cookies, verify=False, data=jsonPayload)

		else:
			self.result = requests.patch (self.url, headers=self.headers, verify=False, data=jsonPayload)

			if (self.result.cookies):
				self.cookies = self.result.cookies

		try:
			self.resultJson = json.loads (self.result.content)

		except ValueError:
			print ("[!] [common]\tError during JSON result parsing")

	# Send the DELETE request and retrieve the result as JSON
	def delete (self):

		# If a session cookie has been saved, use it instead of Authorization HTTP header
		if (self.cookies):

			if ( 'Authorization' in self.headers):
				del self.headers['Authorization']

			self.result = requests.delete (self.url, headers=self.headers, cookies=self.cookies, verify=False)

		else:
			self.result = requests.delete (self.url, headers=self.headers, verify=False)

			if (self.result.cookies):
				self.cookies = self.result.cookies


	# Print the request result
	def printRes (self):
		print (json.dumps (self.resultJson, sort_keys=True, indent=4, separators=(',', ': ')))


class worker ():
	flag = ""
	epoch = 0
	seq = 0
	temp = 0
	workerId = 0

	# Init the api_request object with an url
	def __init__ (self):
		pass

	def run (self):
		self.epoch = int (time ())
		self.seq = self.seq + 1
		self.temp = randint (30, 40)
		self.workerId = workerId
		self.flag = flag

	def validate (self):
		self.epoch = int (time.time ())
		self.seq = self.seq + 1

	def dump (self):
		print ("sequence:\t%s" % self.seq)
		print ("epoch:\t%s" % self.epoch)
		print ("worker ID:\t%s" % self.workerId)
		print ("temp:\t%s" % self.temp)
		print ("flag:\t%s" % self.flag)

	def getData (self):
		return (self.epoch, self.seq, self.temp)



# Initialize the SIGINT handler
signal.signal (signal.SIGINT, sigintHandler)


if __name__ == '__main__':
	# Initiate API object
	logging.info ("[*]\tLaunching client")
	apiRequest = restApi ()
	apiRequest.setHeader ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:43.0) Gecko/20100101 Firefox/43.0')
	apiRequest.setHeader ('Content-Type', 'application/json')

	# Set the API base URL
	urlBase = "https://%s:%i/" % (serverIp, serverPort)
	
	# And the BASIC auth
	logging.info ("[*]\tSetting authentication")
	apiRequest.setAuth (user, password)
	url = urlBase + serverUrl
	logging.info ("[*]\tSetting URL to %s" % url)
	apiRequest.setUrl (url)

	# Create a worker process
	logging.info ("[*]\tCreating and launching worker process")
	workerProcess = worker ()
	workerProcess.run ()

	# Serialize the worker process, and encode it
	payload = pickle.dumps (workerProcess)
	payloadB64 = base64.b64encode (payload)
	payloadJSON = {"method": "validate", "payload": payloadB64}

	# Main loop
	while 1:
		# Sending the HTTP POST request to create the tunnel
		logging.info ("[*]\tSending POST request %s with payload %s" % (url, payloadJSON))

		try:
			sleep (5)
			apiRequest.post (payloadJSON)

			pprint (apiRequest.resultJson)

			if apiRequest.resultJson["status"] == "ERROR":
				sleep (5)
				continue
		
			payloadJSON = apiRequest.resultJson
			pprint (payloadJSON)
			# Recover the payload the payload sent by the client
			payload = base64.b64decode (payloadJSON["payload"])
			workerProcess = pickle.loads (payload)

			# Run and dump the workerProcess instantiated by the client
			workerProcess.run ()
			logging.info ("[*]\tNew temperature %i" % workerProcess.temp)

			# Prepare the client response
			payload = pickle.dumps (workerProcess)
			payloadB64 = base64.b64encode (payload)
			payloadJSON = {"method": "validate", "payload": payloadB64}


		except Exception as e:
			print ("[!]\tCaugth an unhandled exception during POST: %s" % e)
			sleep (10)
