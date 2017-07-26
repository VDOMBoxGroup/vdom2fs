#!/usr/bin/python

import os
import sys
import time
import urlparse
import requests

from datetime import datetime
from argparse import ArgumentParser
from uuid import uuid4
from getpass import getpass


def _cut(text, a=None, b=None):
	n = len(text)-1
	ltext = text.lower()
	a = a.lower() if a else ''
	b = b.lower() if b else ''

	i = ltext.find(a) if a else 0
	i = i if i >= 0 else 0

	j = ltext.find(b, i) if b else n
	j = j if j >= 0 else n

	return text[i+len(a) : j]



class VDOMServer(object):
	def __init__(self, host):
		if '://' not in host:
			host = 'http://{0}'.format(host)

		self.host = host
		self.session = requests.Session()

	
	def url(self, path):
		return urlparse.urljoin(self.host, path)

	def ping(self):
		try:
			r = requests.get(self.url('/system'))
			return r.status_code == 200
		except:
			pass
		return False


	def login(self, user, password):
		data = {
			'user' : user,
			'password' : password
		}

		self.session.post(self.url('/app.py'), data=data)


	def list(self):
		r = self.session.get(self.url('/export.py'))
		html = r.content
		html = _cut(html, '<select name=appl>', '</select>')

		while '<option ' in html:
			app = _cut(html, '<option ', '</option>')
			html = _cut(html, app)

			id = _cut(app, 'value=', '>')
			name = _cut(app, '>', ' ({0})'.format(id))

			yield (id, name)

	
	def get_appid(self, appid_or_name):
		appid_or_name = appid_or_name.lower()
		
		for id, name in self.list():
			if appid_or_name in [id.lower(), name.lower()]:
				return id
		
		return None
		
	
	def export(self, appid, fname):
		data = {
			'appl' 		: appid,
			'format'	: 'xml',
			'device' 	: 'none',
		}

		r = self.session.post(self.url('/export.py'), data=data, stream=True)

		with open(fname, 'w') as f:
			f.write(r.raw.read())


	def select(self, appid_or_name):
		appid = self.get_appid(appid_or_name) or ''
		data = {'defsite' : appid}
		self.session.post(self.url('/virtualhost.py'), data=data)


	def uninstall(self, appid_or_name):
		appid = self.get_appid(appid_or_name)
		if not appid: return

		appid = appid.replace('-', '_')

		data = {
			'remove_db' 	 : 'on',
			'remove_res' 	 : 'on',
			'remove_ldap' 	 : 'on',
			'remove_storage' : 'on',
			appid 			 : '1',
		}

		self.session.post(self.url('/uninstall.py'), data=data)


	def install(self, fname):
		with open(fname, 'rb') as f:
			files = {'appfile' : f}
			data = {
				'format' : 'xml',
				'vhname' : str(uuid4())
			}

			self.session.post(self.url('/install.py'), data=data, files=files)


	def update(self, fname, upsert=True):
		with open(fname, 'rb') as f:
			files = {'appfile' : f}
			data = {
				'format' : 'xml',
				'vhname' : str(uuid4())
			}

			self.session.post(self.url('/install.py'), data=data, files=files)


	def wait(self, tout=30):
		t1 = time.time()

		while True:
			if tout > 0 and time.time() > t1 + tout:
				break

			try:
				r = self.session.get(self.url('/system'))
				if r.status_code == 200: return 0
			except: pass

			time.sleep(1)

		return 1








def parse_url(host):
	if '@' not in host:
		host = '@' + host

	credentials, host = host.rsplit('@', 1)

	if not credentials:
		credentials = 'root:root'
	
	if ':' not in credentials:
		credentials = credentials + ':'

	user, password = credentials.split(':', 1)
	
	return (host, user, password)



parser = ArgumentParser(add_help=False)

parser.add_argument('host')
parser.add_argument('--install', dest='install')
parser.add_argument('--update', dest='update')
parser.add_argument('--uninstall', dest='uninstall')
parser.add_argument('--list', dest='list', action='store_true')
parser.add_argument('--select', dest='select')
parser.add_argument('--wait', dest='wait', nargs='?', const=-1, type=int)

options = parser.parse_args()


if options.wait is not None:
	server = VDOMServer(options.host)
	r = server.wait() if options.wait < 0 else server.wait(options.wait)
	sys.exit(r)



host, user, password = parse_url(options.host)
server = VDOMServer(host)
server.login(user, password)


if options.list:
	for id, name in server.list():
		print '{0}:{1}'.format(id, name.lower())

if options.uninstall:
	server.uninstall(options.uninstall)

if options.install:
	server.install(options.install)

if options.update:
	server.update(options.update)

if options.select:
	server.select(options.select)



