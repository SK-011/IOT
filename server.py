#!/usr/bin/env python
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, ssl
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET
import json
import sys
import base64
import pickle
from time import time, sleep
import mysql.connector
import logging

from pprint import pprint


serverIp = "127.0.0.1"
serverPort = 65535
serverUrl = "json"
#serverCert = '/home/iot/server.crt'
#serverKey = '/home/iot/server.key'
#logFile = "/home/iot/server.log"
serverCert = "server.crt"
serverKey = "server.key"
logFile = "server.log"

user = "iot"
password = "GimmePickle0x42"
#dbHost = "127.0.0.1"
dbHost = "172.17.0.2"
dbUsr = "root"
dbPwd = "vFXsujllIh923ojGKKxS"
db = "ctf"
dbTable = "ctf"
dbCon = None
dbCur = None


logging.basicConfig (filename=logFile, level=logging.DEBUG)

		
def dbConnect ():
	# Initiate database connection
	dbCon = mysql.connector.connect (host=dbHost, user=dbUsr, password=dbPwd, database=db)
	dbCur = dbCon.cursor ()

	return (dbCon, dbCur)


def dbExecute (dbCur, query):
	res = {}
	res["rows"] = []

	try:
		dbCur.execute (query)
		row = dbCur.fetchone ()

		while row != None:
			res["rows"].append (row)
			row = dbCur.fetchone ()

		res["nbRows"] = dbCur.rowcount
		res["error"] = ""

		# Tricky way to detect if the request was an INSERT
		# If so, append the new item's id in the result
		if len (res["rows"]) == 0 and res["nbRows"] > 0:
			res["rows"].append ((dbCur.lastrowid,))

	# If its any mysql error
	except mysql.connector.Error as e:
		print ("[!] [common]\tError during request %s" % query)
		res["error"] = 'DB error during request "%s" : %s' % (query, e)

	return (res)


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
		pass

	def validate (self):
		self.epoch = int (time ())
		self.seq = self.seq + 1

	def dump (self):
		print ("sequence:\t%s" % self.seq)
		print ("epoch:\t%s" % self.epoch)
		print ("worker ID:\t%s" % self.workerId)
		print ("temp:\t%s" % self.temp)
		print ("flag:\t%s" % self.flag)

	def getData (self):
		return (self.epoch, self.workerId, self.temp)


# Check whether the passed basic auth is correct
def authIsValid (auth):
	res = 0
	
	try:
		recvUser, recvPassword = base64.b64decode (auth.split (' ')[1]).split (":")

		if recvUser == user and recvPassword == password:
			res = 1

	except Exception as e:
		pass

	return (res)


# Handle client input
def handleInput (content):
	status = "OK"
	detail = ""
	data = {}
	global dbCon, dbCur

	try:
		# Recover the payload the payload sent by the client
		logging.info ("[*]\tDecoding the payload")
		payload = base64.b64decode (content["payload"])
		logging.info ("[*]\tUnserializing the data")
		workerProcess = pickle.loads (payload)

		epoch, workerId, temp = workerProcess.getData ()
		logging.info ("[*]\tExtracted data: epoch/%s\tworkerId/%s\ttemp/%s" % (epoch, workerId, temp))

		logging.info ("[*]\tInserting data in database")
		sql = 'INSERT INTO %s (epoch, clientId, temp) VALUES (%i, %i, %i)' % (dbTable, epoch, workerId, temp)
		res = dbExecute (dbCur, sql)

		# If the data has been inserted
		if not res["error"] and res["nbRows"] > 0:
			dbCon.commit ()


		# Validate and dump the workerProcess instantiated by the client
		logging.info ("[*]\tValidating data")
		workerProcess.validate ()

		# Prepare the client response
		logging.info ("[*]\tPreparing client response")
		payload = pickle.dumps (workerProcess)
		payloadB64 = base64.b64encode (payload)
		payloadJSON = {"method": "validate-reply", "payload": payloadB64}
		data = payloadJSON

	except Exception as e:
		status = "ERROR"
		detail = "Caugth an exception handling request payload: %s" % e
		logging.info ("[!]\t%s" % detail)

	return (status, detail, data)


# Parse and check the received JSON query
class jsonHandler (Resource):

	# Callback function for the render_POST defer, does the actual job
	def _delayedRender (self, request):

		if not authIsValid (request.getHeader ("authorization")):
			logging.info ("[*]\tInvalid User/Password")
			request.write ('{\n\t"status": "ERROR",\n\t"detail": "Invalid User/password"\n}')
			request.finish ()
			return ()


		# Try to parse the JSON client input. If unsuccesful, return an error
		try:
			logging.info ("[*]\tParsing JSON payload")
			jsonContent = json.loads (request.content.read ())

		except Exception as e:
			# Construct response and end it
			logging.info ("[*]\tInvalid JSON payload")
			request.write ('{\n\t"status": "ERROR",\n\t"detail": "Invalid JSON payload"\n}')
			request.finish ()
			return ()

		try:
			# Check if method and payload are present in the JSON file, send an error
			if not "payload" in jsonContent.keys ():
				logging.info ("[*]\tMissing JSON payload")
				request.write ('{\n\t"status": "ERROR",\n\t"detail": "Missing payload in JSON query"\n}')
				request.finish ()
				return ()

			# Send the command to the core function handling the argument parsing
			status, detail, data = handleInput (jsonContent)

			res = data
			res.update ({"status": status, "detail": detail.encode ("utf8")})
			
			# Construct response and end it
			request.write (json.dumps (res, sort_keys=True, indent=4, separators=(',', ': ')))
			request.finish ()

		except Exception as e:
			# Construct response and end it
			request.write ('{\n\t"status": "ERROR",\n\t"detail": "Error while payload analysis"\n}')
			request.finish ()

		return ()


	# Errback function that cancel the connection
	def _responseFailed (self, err, call):
		call.cancel ()
		return ()


	# Handle POST requests
	def render_POST (self, request):
		# Set the response headers
		request.setHeader ("Server", "Apache 2.0")
		request.setHeader ("Content-Type", "application/json")
			
		# Return an ERROR to the client if the Content-Type header is incorrect
		if request.getHeader ("Content-Type") != "application/json":
			logging.info ("[*]\tInvalid Content-Type")
			return ('{\n\t"status": "ERROR",\n\t"detail": "Invalid Content-Type"\n}')

		# Setup the deter, its callback and its errorback
		call = reactor.callLater (2, self._delayedRender, request)
		request.notifyFinish ().addErrback (self._responseFailed, call)

		# Special return that says "wait for it budy"
		return (NOT_DONE_YET)


# HTTP listenner class
class listenner ():
	apiUrl = ""
	apiInterface = ""
	apiPort = ""


	# Init the listenner with the URL to use for the API
	def __init__ (self, url, apiInterface, apiPort):
		self.apiUrl = url
		self.apiInterface = apiInterface
		self.apiPort = apiPort


	def run (self):
		# Create the webserver root
		root = Resource ()

		# Create /json page and bind it to jsonHandler ressource
		root.putChild (self.apiUrl, jsonHandler ())

		# Create the factory
		factory = Site (root)
		reactor.listenSSL (self.apiPort, factory, ssl.DefaultOpenSSLContextFactory (serverKey, serverCert))

		# Launch the reactor (the main event loop)
		reactor.run ()



def main ():
	global dbCon, dbCur

	# Set the HTTP listenner to listen on http://127.0.0.1:65535/json
	try:
		logging.info ("[*]\tLaunching server")
		logging.info ("[*]\tConnecting to database")
		sleep (30)
		dbCon, dbCur = dbConnect ()
		logging.info ("[*]\tLaunching HTTPs listenner")
		httpListenner = listenner (serverUrl, serverIp, serverPort)
		httpListenner.run ()
		logging.info ("[*]\tStopping server")
		dbCon.commit ()
		dbCur.close ()
		dbCon.close ()

	except Exception as e:
		logging.warning ("[!]\tCaugth an unhandled exception: %s" % e)

	return (0)


if __name__ == "__main__":
	sys.exit (main ())
