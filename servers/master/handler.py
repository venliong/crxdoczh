import webapp2, logging
import mimetypes
import os
from google.appengine.api import urlfetch, memcache

def AddSecurityHeaders(response):
  response.headers.add('Strict-Transport-Security',
                       'max-age=31536000')
  # Keep these synced with https://src.chromium.org/viewvc/chrome/trunk/src/net/base/transport_security_state_static.certs
  response.headers.add('Public-Key-Pins',
                       'max-age=2592000; ' + 
                       'pin-sha1="4n972HfV354KP560yw4uqe/baXc="; ' +
                       'pin-sha1="IvGeLsbqzPxdI0b0wuj2xVTdXgc="; ' +
                       'pin-sha1="QMVAHW+MuvCLAO3vse6H0AWzuc0="; ' +
                       'pin-sha1="AbkhxY0L343gKf+cki7NVWp+ozk="; ' +
                       'pin-sha1="fVujyo43ZR18ccPjt3TN6XsbWUM="; ' +
                       'pin-sha1="vq7OyjSnqOco9nyMCDGdy77eijM="; ' +
                       'pin-sha1="SOZo+SvSspXXR9gjIBBPM5iQn9Q="; ' +
                       'pin-sha1="wHqYaI2J+6sFZAwRfap9ZbjKzE4="')
  response.headers.add('X-Frame-Options', 'SAMEORIGIN')

class HandlerCache(webapp2.RequestHandler):
  def __init__(self, request, response):
    self.request = request
    self.response = response

  def get(self):
    cached = memcache.get(self.request.path)
    if cached is not None:
      logging.info('Serving %s from memcache.' % self.request.path)
      self.response.write(cached)
      return True
    else:
      return False

  def add(self, content):
    memcache.add(key = self.request.path, value = content, time = 3600)

class HTMLHandler(webapp2.RequestHandler):
  def get(self, slashed_channel, doctype, filename):
    channel = slashed_channel[1:-1]
    if len(channel) == 0:
      channel = 'stable'
    cache = HandlerCache(self.request, self.response)

    if not cache.get():
      url = 'https://crxdoczh-slave-docs-qjn45lbk2r.appspot.com/' + channel + '/_/api/Oxd3faDoX570NSlaItOqbmen8tmxyg54nhnbo9qo66333kEHLU8jbd/html/docs/' + doctype + '/' + filename
      logging.info(url)
      result = urlfetch.fetch(url, deadline=40)
      logging.info(result.status_code)
      if result.status_code == 200:
        cache.add(result.content)
        AddSecurityHeaders(self.response)
        self.response.write(result.content)
      else:
        self.response.status = result.status_code

class StaticHandler(webapp2.RequestHandler):
  def get(self, static_path):
    cache = HandlerCache(self.request, self.response)
    mimetypes.init()
    base, ext = os.path.splitext(static_path)
    self.response.content_type = mimetypes.types_map[ext]

    if not cache.get():
      url = 'https://crxdoczh.googlecode.com/svn/trunk/chromium/crxdoczh/src/chrome/common/extensions/docs/static/' + static_path
      result = urlfetch.fetch(url, deadline=20)
      if result.status_code == 200:
        cache.add(result.content)
        self.response.write(result.content)
        AddSecurityHeaders(self.response)
      else:
        self.response.status = 404

class HomeRedirectHandler(webapp2.RequestHandler):
  def get(self):
    self.response.location = '/trunk/extensions/index.html'
    AddSecurityHeaders(self.response)
    self.response.status = 302

class ExamplesRedirectHandler(webapp2.RequestHandler):
  def get(self, slashed_channel, example_path):
    self.response.location = 'https://developer.chrome.com' + self.request.path
    AddSecurityHeaders(self.response)
    self.response.status = 301

class AppsIndexRedirectHandler(webapp2.RequestHandler):
  def get(self, slashed_channel):
    self.response.location = slashed_channel + 'apps/about_apps.html'
    AddSecurityHeaders(self.response)
    self.response.status = 301

class ExtensionsIndexRedirectHandler(webapp2.RequestHandler):
  def get(self, slashed_channel):
    self.response.location = slashed_channel + 'extensions/index.html'
    AddSecurityHeaders(self.response)
    self.response.status = 301

app = webapp2.WSGIApplication([
  (r'(/trunk/|/dev/|/beta/|/stable/|/)(apps|extensions)/([^/]*\.html)', HTMLHandler),
  (r'/trunk/static/(.*)', StaticHandler),
  (r'/dev/static/(.*)', StaticHandler), # TODO
  (r'/beta/static/(.*)', StaticHandler), # TODO
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions/examples/(.*)', ExamplesRedirectHandler),
  (r'/', HomeRedirectHandler),
  (r'/index.html', HomeRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps/', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps/index\.html', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions', ExtensionsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions/', ExtensionsIndexRedirectHandler),
])

