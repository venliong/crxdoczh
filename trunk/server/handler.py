import webapp2, logging
from google.appengine.api import urlfetch, memcache

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
  def get(self, doctype, filename):
    cache = HandlerCache(self.request, self.response)

    if not cache.get():
      url = 'https://crxdoczh.googlecode.com/svn/trunk/docs' + self.request.path
      result = urlfetch.fetch(url, validate_certificate = False)
      if result.status_code == 200:
        cache.add(result.content)
        self.response.write(result.content)
      else:
        self.response.status = result.status_code

class StaticHandler(webapp2.RequestHandler):
  def get(self, doctype, static_path):
    cache = HandlerCache(self.request, self.response)

    if(static_path.endswith('.css')):
      self.response.content_type = 'text/css'

    if not cache.get():
      url = 'https://crxdoczh.googlecode.com/svn/trunk/chromium/crxdoczh/src/chrome/common/extensions/docs/static/' + static_path
      result = urlfetch.fetch(url, validate_certificate=False)
      if result.status_code == 200:
        cache.add(result.content)
        self.response.write(result.content)
      else:
        self.response.status = 404

app = webapp2.WSGIApplication([
  (r'/trunk/(apps|extensions)/([^/]*\.html)', HTMLHandler),
  (r'/trunk/(apps|extensions)/static/(.*)', StaticHandler),
])

