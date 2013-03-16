import webapp2, os, logging, mimetypes, json
from google.appengine.api import urlfetch, memcache
from google.appengine.ext import db

class CacheModel(db.Model):
  data = db.BlobProperty(required=True)

class Cache:
  @staticmethod
  def get(path):
    data = memcache.get(path)
    if data is not None:
      return data

    data = db.get(db.Key.from_path('CacheModel', path))
    if data is not None:
      memcache.add(path, data)
      return data

    return None

  @staticmethod
  def update(self, path, data):
    model = CacheModel(key_name = path, data = data)
    model.put()

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

# Parameters:
# |slashed_channel|: trunk/|dev/|beta/|stable/|<empty>
# |doc_type|: apps|extensions|static
# |remaining_path|: xxx.html|css/xxx.css|...
# Returns:
# A path that can be passed to Cache or None if invalid.
def NormalizePath(slashed_channel, doc_type, remaining_path):
  channel = slashed_channel[0:-1]
  if len(channel) == 0:
    channel = 'stable'
  path = '/' + channel + '/' + doc_type + '/'

  if doc_type == 'static':
    return path + remaining_path
  else:
    if not remaining_path.endswith('.html'):
      return None
    file_title = remaining_path[:-len('.html')]
    return path + file_title.replace('.', '_') + '.html'

def Handle404(response, slashed_channel = None, doc_type = None):
  response.status = 404
  if slashed_channel is None:
    slashed_channel = 'stable/'
  if doc_type != 'apps':
    doc_type = 'extensions'
  response.content_type = 'text/html'
  response.write(Cache.get(NormalizePath(
      slashed_channel, doc_type, '404.html')))

class Handler(webapp2.RequestHandler):
  def get(self, slashed_channel, doc_type, remaining_path):
    path = NormalizePath(slashed_channel, doc_type, remaining_path)

    data = Cache.get(path)
    AddSecurityHeaders(self.response)

    if data is None:
      Handle404(self.response, slashed_channel, doc_type)
    else:
      mimetypes.init()
      base, ext = os.path.splitext(remaining_path)
      self.response.content_type = mimetypes.types_map[ext]
      self.response.write(data)

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

class NotFoundHandler(webapp2.RequestHandler):
  def get(self):
    AddSecurityHeaders(self.response)
    Handle404(self.response)

class APIUpdateHandler(webapp2.RequestHandler):
  def post(self):
    paths = json.loads(self.request.body)
    for path in paths:
      pass
    # TODO Request updated resources from slave-docs and update cache

app = webapp2.WSGIApplication([
  (r'/_/api/' + os.environ.get('CRXDOCZH_MASTER_API_KEY') + '/pushUpdate',
      APIUpdateHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions/examples/(.*)', ExamplesRedirectHandler),
  (r'/', HomeRedirectHandler),
  (r'/index.html', HomeRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps/', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)apps/index\.html', AppsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions', ExtensionsIndexRedirectHandler),
  (r'(/trunk/|/dev/|/beta/|/stable/|/)extensions/', ExtensionsIndexRedirectHandler),
  (r'/(trunk/|dev/|beta/|stable/|)(apps|extensions|static)/(.+)', Handler),
  (r'.*', NotFoundHandler)
])

