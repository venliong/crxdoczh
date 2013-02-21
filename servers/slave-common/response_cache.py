import datetime
from google.appengine.ext import db
from google.appengine.api import memcache

class ResponseModel(db.Model):
  data = db.BlobProperty(required=True)
  last_update = db.DateTimeProperty(required=True)

class ResponseCache:
  @staticmethod
  def _GetInternal(url):
    cached_data = memcache.get(url)
    if cached_data is not None:
      return cached_data
    else:
      cached_data = db.get(db.Key.from_path('ResponseModel', url))
      if cached_data is not None:
        memcache.add(url, cached_data)
        return cached_data
      else:
        return None

  @staticmethod
  def Get(url):
    cached_data = ResponseCache._GetInternal(url)
    if cached_data is not None:
      return cached_data.data
    else:
      return None

  @staticmethod
  def GetAge(url):
    cached_data = ResponseCache._GetInternal(url)
    if cached_data is not None:
      return datetime.datetime.now() - cached_data.last_update
    else:
      return datetime.timedelta.max

  @staticmethod
  def Set(url, data):
    cached_data = ResponseModel(key_name = url, data = data, last_update=datetime.datetime.now())
    cached_data.put()
    memcache.set(url, cached_data)

