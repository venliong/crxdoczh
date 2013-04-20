# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from fnmatch import fnmatch
import logging
import mimetypes
import os
import datetime

from api_data_source import APIDataSource
from api_list_data_source import APIListDataSource
from appengine_blobstore import AppEngineBlobstore
from appengine_url_fetcher import AppEngineUrlFetcher
from branch_utility import BranchUtility
from caching_file_system import CachingFileSystem
from compiled_file_system import CompiledFileSystem
from example_zipper import ExampleZipper
from file_system import FileNotFoundError
from github_file_system import GithubFileSystem
from intro_data_source import IntroDataSource
from local_file_system import LocalFileSystem
from object_store_creator import ObjectStoreCreator
from offline_file_system import OfflineFileSystem
from path_canonicalizer import PathCanonicalizer
from reference_resolver import ReferenceResolver
from samples_data_source import SamplesDataSource
from sidenav_data_source import SidenavDataSource
from subversion_file_system import SubversionFileSystem
import svn_constants
from template_data_source import TemplateDataSource
from third_party.json_schema_compiler.memoize import memoize
from third_party.json_schema_compiler.model import UnixName
import url_constants
from response_cache import ResponseCache

def _IsBinaryMimetype(mimetype):
  return any(mimetype.startswith(prefix)
             for prefix in ['audio', 'image', 'video'])

class ServerInstance(object):
  # Lazily create so we don't create github file systems unnecessarily in
  # tests.
  branch_utility = None
  github_file_system = None

  @staticmethod
  @memoize
  def GetOrCreateOffline(channel):
    '''Gets/creates a local ServerInstance, meaning that only resources local to
    the server - memcache, object store, etc, are queried. This amounts to not
    setting up the subversion nor github file systems.
    '''
    branch_utility = ServerInstance._GetOrCreateBranchUtility()
    branch = branch_utility.GetBranchNumberForChannelName(channel)
    object_store_creator_factory = ObjectStoreCreator.Factory(branch)
    # No svn nor github file systems. Rely on the crons to fill the caches, and
    # for the caches to exist.
    return ServerInstance(
        channel,
        object_store_creator_factory,
        CachingFileSystem(OfflineFileSystem(SubversionFileSystem),
                          object_store_creator_factory),
        # TODO(kalman): convert GithubFileSystem to be wrappable in a
        # CachingFileSystem so that it can be replaced with an
        # OfflineFileSystem. Currently GFS doesn't set the child versions of
        # stat requests so it doesn't.
        ServerInstance._GetOrCreateGithubFileSystem())

  @staticmethod
  @memoize
  def GetOrCreateOnline(channel):
    '''Creates/creates an online server instance, meaning that both local and
    subversion/github resources are queried.
    '''
    branch_utility = ServerInstance._GetOrCreateBranchUtility()
    branch = branch_utility.GetBranchNumberForChannelName(channel)

    if branch == 'trunk':
      svn_url = '/'.join((url_constants.SVN_TRUNK_URL,
                          'src',
                          svn_constants.EXTENSIONS_PATH))
    else:
      svn_url = '/'.join((url_constants.SVN_BRANCH_URL,
                          branch,
                          'src',
                          svn_constants.EXTENSIONS_PATH))

    viewvc_url = svn_url.replace(url_constants.SVN_URL,
                                 url_constants.VIEWVC_URL)

    object_store_creator_factory = ObjectStoreCreator.Factory(branch)

    svn_file_system = CachingFileSystem(
        SubversionFileSystem(AppEngineUrlFetcher(svn_url),
                             AppEngineUrlFetcher(viewvc_url)),
        object_store_creator_factory)

    return ServerInstance(channel,
                          object_store_creator_factory,
                          svn_file_system,
                          ServerInstance._GetOrCreateGithubFileSystem())

  @staticmethod
  def CreateForTest(file_system):
    return ServerInstance('test',
                          ObjectStoreCreator.Factory('test'),
                          file_system,
                          None)

  @staticmethod
  def _GetOrCreateBranchUtility():
    if ServerInstance.branch_utility is None:
      ServerInstance.branch_utility = BranchUtility(
          url_constants.OMAHA_PROXY_URL,
          AppEngineUrlFetcher())
    return ServerInstance.branch_utility

  @staticmethod
  def _GetOrCreateGithubFileSystem():
    if ServerInstance.github_file_system is None:
      ServerInstance.github_file_system = GithubFileSystem(
          AppEngineUrlFetcher(url_constants.GITHUB_URL),
          AppEngineBlobstore())
    return ServerInstance.github_file_system

  def __init__(self,
               channel,
               object_store_creator_factory,
               svn_file_system,
               github_file_system):
    self.svn_file_system = svn_file_system

    self.github_file_system = github_file_system

    self.compiled_fs_factory = CompiledFileSystem.Factory(
        svn_file_system,
        object_store_creator_factory)

    self.api_list_data_source_factory = APIListDataSource.Factory(
        self.compiled_fs_factory,
        svn_constants.API_PATH,
        svn_constants.PUBLIC_TEMPLATE_PATH)

    self.api_data_source_factory = APIDataSource.Factory(
        self.compiled_fs_factory,
        svn_constants.API_PATH)

    self.ref_resolver_factory = ReferenceResolver.Factory(
        self.api_data_source_factory,
        self.api_list_data_source_factory,
        object_store_creator_factory)

    self.api_data_source_factory.SetReferenceResolverFactory(
        self.ref_resolver_factory)

    self.samples_data_source_factory = SamplesDataSource.Factory(
        channel,
        self.svn_file_system,
        ServerInstance.github_file_system,
        self.ref_resolver_factory,
        object_store_creator_factory,
        svn_constants.EXAMPLES_PATH)

    self.api_data_source_factory.SetSamplesDataSourceFactory(
        self.samples_data_source_factory)

    self.intro_data_source_factory = IntroDataSource.Factory(
        self.compiled_fs_factory,
        self.ref_resolver_factory,
        [svn_constants.INTRO_PATH, svn_constants.ARTICLE_PATH])

    self.sidenav_data_source_factory = SidenavDataSource.Factory(
        self.compiled_fs_factory,
        svn_constants.JSON_PATH)

    self.template_data_source_factory = TemplateDataSource.Factory(
        channel,
        self.api_data_source_factory,
        self.api_list_data_source_factory,
        self.intro_data_source_factory,
        self.samples_data_source_factory,
        self.sidenav_data_source_factory,
        self.compiled_fs_factory,
        self.ref_resolver_factory,
        svn_constants.PUBLIC_TEMPLATE_PATH,
        svn_constants.PRIVATE_TEMPLATE_PATH)

    self.example_zipper = ExampleZipper(
        self.compiled_fs_factory,
        svn_constants.DOCS_PATH)

    self.path_canonicalizer = PathCanonicalizer(
        channel,
        self.compiled_fs_factory)

    self.content_cache = self.compiled_fs_factory.GetOrCreateIdentity()

  def _FetchStaticResource(self, path, response):
    """Fetch a resource in the 'static' directory.
    """
    mimetype = mimetypes.guess_type(path)[0] or 'text/plain'
    result = self.content_cache.GetFromFile(
        svn_constants.DOCS_PATH + '/' + path,
        binary=_IsBinaryMimetype(mimetype))
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
    templates = self.template_data_source_factory.Create(request, 
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
        response.out.write(self._FetchStaticResource(new_path, response))
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
    templates = self.template_data_source_factory.Create(request, path)
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
    templates = self.template_data_source_factory.Create(request, path)

    content = None
    try:
      if fnmatch(path, 'extensions/examples/*.zip'):
        content = self.example_zipper.Create(
            path[len('extensions/'):-len('.zip')])
        response.headers['content-type'] = 'application/zip'
      elif path.startswith('extensions/examples/'):
        mimetype = mimetypes.guess_type(path)[0] or 'text/plain'
        content = self.content_cache.GetFromFile(
            '%s/%s' % (svn_constants.DOCS_PATH, path[len('extensions/'):]),
            binary=_IsBinaryMimetype(mimetype))
        response.headers['content-type'] = 'text/plain'
      elif path.startswith('static/'):
        content = self._FetchStaticResource(path, response)
      elif path.endswith('.html'):
        content = templates.Render(path)
    except FileNotFoundError as e:
      logging.warning(e)

    response.headers['x-frame-options'] = 'sameorigin'
    if content is None:
      response.set_status(404);
      response.out.write(templates.Render('404'))
    else:
      if not content:
        logging.error('%s had empty content' % path)
      response.headers['cache-control'] = 'max-age=300'
      response.out.write(content)
      cache_url = '/' + templates._branch_info['current'] + '/' + path
      if isinstance(content, unicode):
        ResponseCache.Set(cache_url, content.encode('utf-8'))
      else:
        ResponseCache.Set(cache_url, content)
