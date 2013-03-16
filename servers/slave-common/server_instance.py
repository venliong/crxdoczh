# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from fnmatch import fnmatch
import mimetypes
import os
import logging
import datetime

from file_system import FileNotFoundError
import compiled_file_system as compiled_fs
import url_constants
from response_cache import ResponseCache

STATIC_DIR_PREFIX = 'docs'
DOCS_PATH = 'docs'

def _IsBinaryMimetype(mimetype):
  return any(mimetype.startswith(prefix)
             for prefix in ['audio', 'image', 'video'])

class ServerInstance(object):
  """This class is used to hold a data source and fetcher for an instance of a
  server. Each new branch will get its own ServerInstance.
  """
  def __init__(self,
               template_data_source_factory,
               example_zipper,
               cache_factory):
    self._template_data_source_factory = template_data_source_factory
    self._example_zipper = example_zipper
    self._cache = cache_factory.Create(lambda _, x: x, compiled_fs.STATIC)

  def _FetchStaticResource(self, path, response):
    """Fetch a resource in the 'static' directory.
    """
    mimetype = mimetypes.guess_type(path)[0] or 'text/plain'
    try:
      result = self._cache.GetFromFile(STATIC_DIR_PREFIX + '/' + path,
                                       binary=_IsBinaryMimetype(mimetype))
    except FileNotFoundError:
      return None
    response.headers['content-type'] = mimetype
    return result

  def Get(self, path, request, response):
    if os.environ.get('CRXDOCZH_SLAVE_TYPE') == 'samples':
      logging.error('NOTREACHED: slave-samples: server_instance: Get')
    elif os.environ.get('CRXDOCZH_SLAVE_TYPE') == 'docs':
      if not self._GetDocsAPI(path, request, response):
        self._OriginalGet(path, request, response)
    else:
      self._OriginalGet(path, request, response)
  
  def _GetSamplesJSON(self, request, key, update=False):
    templates = self._template_data_source_factory.Create(request, 
        key + '/samples.html')
    if key == 'apps' or key == 'extensions':
      cache_url = None
      if key == 'apps':
        cache_url = '/trunk/' + key
      else:
        cache_url = '/' + templates._branch_info['current'] + '/' + key
      logging.info('Serving API request %s' % cache_url)

      data = ResponseCache.Get(cache_url)
      age = ResponseCache.GetAge(cache_url)
      need_update = (age > datetime.timedelta(1))
      logging.info('Cache age: %s' % str(age))
      if data is not None and not ( update == True and need_update == True):
        return data
      else:
        content = []
        try:
          logging.info('Trying to generate samples.json for %s' % cache_url)
          content = templates._samples_data_source.GetAsJSON(key)
        except:
          logging.getLogger('slave-samples-api').exception(
              'Error generating samples!')
          pass
        if len(content) > 0:
          logging.info('samples.json saved for %s' % cache_url)
          ResponseCache.Set(cache_url, content)
        return content

  def _GetDocsAPI(self, path, request, response):
    if path.startswith(url_constants.SLAVE_DOCS_API_BASE_URL):
      new_path = path[len(url_constants.SLAVE_DOCS_API_BASE_URL):]
      if new_path.startswith('static/'):
        response.headers['content-type'] = 'text/plain';
        response.out.write(self._FetchStaticResource(path, response))
        return True
      if not new_path.endswith('.html'):
        return False
      content = self._GetDocsHTML(request, new_path)
      if len(content) > 0:
        response.headers['content-type'] = 'text/plain'
        response.out.write(content)
      else:
        response.set_status(503)
      return True
    else:
      return False

  def _GetDocsHTML(self, request, path, update=False):
    templates = self._template_data_source_factory.Create(request, path)
    cache_url = '/' + templates._branch_info['current'] + '/' + path

    logging.info('Serving API request %s' % cache_url)
    data = ResponseCache.Get(cache_url)
    age = ResponseCache.GetAge(cache_url)
    need_update = (age > datetime.timedelta(1))
    logging.info('Cache age: %s' % str(age))
    if data is not None and not (update == True and need_update == True):
      return data
    else:
      content = ''
      try:
        logging.info('Trying to render %s' % cache_url)
        content = templates.Render(path)
      except:
        logging.getLogger('slave-docs-api').exception(
            'Error rendering HTML!')
        pass
      if len(content) > 0:
        logging.info('HTML saved for %s' % cache_url)
        ResponseCache.Set(cache_url, content.encode('utf-8'))
      return content

  def _OriginalGet(self, path, request, response):
    # TODO(cduvall): bundle up all the request-scoped data into a single object.
    templates = self._template_data_source_factory.Create(request, path)

    content = None
    if fnmatch(path, 'extensions/examples/*.zip'):
      try:
        content = self._example_zipper.Create(
            path[len('extensions/'):-len('.zip')])
        response.headers['content-type'] = 'application/zip'
      except FileNotFoundError:
        content = None
    elif path.startswith('extensions/examples/'):
      mimetype = mimetypes.guess_type(path)[0] or 'text/plain'
      try:
        content = self._cache.GetFromFile(
            '%s/%s' % (DOCS_PATH, path[len('extensions/'):]),
            binary=_IsBinaryMimetype(mimetype))
        response.headers['content-type'] = 'text/plain'
      except FileNotFoundError:
        content = None
    elif path.startswith('static/'):
      content = self._FetchStaticResource(path, response)
    elif path.endswith('.html'):
      content = templates.Render(path)

    response.headers['x-frame-options'] = 'sameorigin'
    if content:
      response.headers['cache-control'] = 'max-age=300'
      response.out.write(content)
      cache_url = '/' + templates._branch_info['current'] + '/' + path
      ResponseCache.Set(cache_url, content.encode('utf-8'))
    else:
      response.set_status(404);
      response.out.write(templates.Render('404'))
