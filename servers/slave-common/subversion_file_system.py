# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from file_system import FileSystem, FileNotFoundError, StatInfo, ToUnicode
from future import Future
import logging
import re
import xml.dom.minidom as xml
from xml.parsers.expat import ExpatError
from google.appengine.ext import db
import logging
from url_constants import SVN_URL
from appengine_url_fetcher import AppEngineUrlFetcher

def _ListGoogleCodeSvnDir(directory):
  # HACK Filter '<hr noshade>' in Google Code's SVN server to become
  # valid XML
  dom = xml.parseString(directory.replace('<hr noshade>', ''))
  files = []
  # HACK Filter Google Code links at the bottom
  for elem in dom.getElementsByTagName('a'):
    name = elem.childNodes[0].data
    href = elem.getAttribute('href')
    if '..' != name:
      if not (href.startswith('http://') or href.startswith('https://')):
        files.append(name)
  return files

class StatModel(db.Model):
  path = db.StringProperty(required=True)
  revision = db.StringProperty(required=True)
  child_revisions = db.StringListProperty(required=True)

class LastRevisionModel(db.Model):
  revision = db.StringProperty(required=True)

class StatUpdater:
  @staticmethod
  def _GetLastRevision():
    revision = LastRevisionModel.get(db.Key.from_path('LastRevisionModel', 'LAST_CHANGE'))
    if revision is None:
      revision = LastRevisionModel(key_name = 'LAST_CHANGE', revision = '0')
      revision.put()
    return revision.revision

  @staticmethod
  def _SetLastRevision(revision):
    LastRevisionModel(key_name = 'LAST_CHANGE', revision = revision).put()

  @staticmethod
  def _ParseGoogleCodeSvnChanges(feed):
    last_revision = StatUpdater._GetLastRevision()
    result = []
    dom = xml.parseString(feed)
    new_revision = last_revision
    for entry in dom.getElementsByTagName('entry'):
      revision = entry.getElementsByTagName('id')[0].childNodes[0].data.rsplit('/', 1)[1]
      if int(revision) <= int(last_revision):
        break
      new_revision = str(max(int(revision), int(new_revision)))
      content = entry.getElementsByTagName('content')[0].childNodes[0].data
      changes = re.findall(r'<br/>(?:\s|\xa0|&#160;|&nbsp;)+([A-Za-z]+)(?:\s|\xa0|&#160;|&nbsp;)+(\S+)', content)
      for change in changes:
        result.append((change[0], change[1], revision))
    return (result, new_revision)

  @staticmethod
  def Update():
    CRXDOCZH_SVN_CHANGES_FEED = 'https://code.google.com/feeds/p/crxdoczh/svnchanges/basic'
    fetcher = AppEngineUrlFetcher(None)
    result = fetcher.Fetch(CRXDOCZH_SVN_CHANGES_FEED)
    if result.status_code == 200:
      changes = []
      new_revision = 0
      try:
        (changes, new_revision) = StatUpdater._ParseGoogleCodeSvnChanges(result.content)
      except Exception as e:
        logging.error('Error parsing changes from Google Code SVN changes feed: %s' % str(e))
      for change in changes:
        how = change[0]
        (base_path, name) = change[1].rsplit('/', 1)
        revision = change[2]
        logging.info('Change: %s %s %s %s' % (how, base_path, name, revision))
        model = StatModel.get(db.Key.from_path('StatModel', base_path))
        if model is not None:
          model.revision = str(max(int(model.revision), int(revision)))
          # NOTE: Directories are not considered.
          if how == 'Add':
            model.child_revisions.append(name + ':' + revision)
          elif how == 'Delete' or how == 'Modify':
            to_remove = None
            for c in model.child_revisions:
              if c.split(':')[0] == name:
                to_remove = c
                break
            if to_remove is not None:
              model.child_revisions.remove(to_remove)
          else:
            logging.error('Unknown svn change method: %s' % how)
          if how == 'Modify':
            model.child_revisions.append(name + ':' + revision)
          model.put()
      if len(changes) > 0:
        StatUpdater._SetLastRevision(new_revision)

# Sometimes we get bad data and end up caching it. Increment this so that
# CachingFileSystem (if one is attached) knows to re-fetch.
#
# WARNING: This is a VERY EXPENSIVE number to bump. ONLY do so if the data
# returned by these operations changes, DESPITE WHAT THE PRESUBMIT WARNING
# MIGHT TELL YOU!
_VERSION = 1

class _AsyncFetchFuture(object):
  def __init__(self, paths, fetcher, binary):
    # A list of tuples of the form (path, Future).
    self._fetches = [(path, fetcher.FetchAsync(path)) for path in paths]
    self._value = {}
    self._error = None
    self._binary = binary

  def _ListDir(self, directory):
    # CRXDOCZH
    return _ListGoogleCodeSvnDir(directory)
    dom = xml.parseString(directory)
    files = [elem.childNodes[0].data for elem in dom.getElementsByTagName('a')]
    if '..' in files:
      files.remove('..')
    return files

  def Get(self):
    for path, future in self._fetches:
      result = future.Get()
      if result.status_code == 404:
        raise FileNotFoundError('Got 404 when fetching %s for Get' % path)
      elif path.endswith('/'):
        self._value[path] = self._ListDir(result.content)
      elif not self._binary:
        self._value[path] = ToUnicode(result.content)
      else:
        self._value[path] = result.content
    if self._error is not None:
      raise self._error
    return self._value

class SubversionFileSystem(FileSystem):
  """Class to fetch resources from src.chromium.org.
  """
  def __init__(self, fetcher, stat_fetcher):
    self._fetcher = fetcher
    self._stat_fetcher = stat_fetcher

  def Read(self, paths, binary=False):
    return Future(delegate=_AsyncFetchFuture(paths, self._fetcher, binary))

  def _ParseHTML(self, html):
    """Unfortunately, the viewvc page has a stray </div> tag, so this takes care
    of all mismatched tags.
    """
    try:
      return xml.parseString(html)
    except ExpatError as e:
      return self._ParseHTML('\n'.join(
          line for (i, line) in enumerate(html.split('\n'))
          if e.lineno != i + 1))

  def _CreateStatInfo(self, html):
    def inner_text(node):
      '''Like node.innerText in JS DOM, but strips surrounding whitespace.
      '''
      text = []
      if node.nodeValue:
        text.append(node.nodeValue)
      if hasattr(node, 'childNodes'):
        for child_node in node.childNodes:
          text.append(inner_text(child_node))
      return ''.join(text).strip()

    dom = self._ParseHTML(html)

    # Try all of the tables until we find the one that contains the data.
    for table in dom.getElementsByTagName('table'):
      # Within the table there is a list of files. However, there may be some
      # things beforehand; a header, "parent directory" list, etc. We will deal
      # with that below by being generous and just ignoring such rows.
      rows = table.getElementsByTagName('tr')
      child_versions = {}

      for row in rows:
        # Within each row there are probably 5 cells; name, version, age,
        # author, and last log entry. Maybe the columns will change; we're at
        # the mercy viewvc, but this constant can be easily updated.
        elements = row.getElementsByTagName('td')
        if len(elements) != 5:
          continue
        name_element, version_element, _, __, ___ = elements

        name = inner_text(name_element)  # note: will end in / for directories
        try:
          version = int(inner_text(version_element))
        except ValueError:
          continue
        child_versions[name] = version

      if not child_versions:
        continue

      # Parent version is max version of all children, since it's SVN.
      parent_version = max(child_versions.values())

      # All versions in StatInfo need to be strings.
      return StatInfo(str(parent_version),
                      dict((path, str(version))
                           for path, version in child_versions.iteritems()))

    # Bleh, but, this data is so unreliable. There are actually some empty file
    # listings caused by git/svn/something not cleaning up empty dirs.
    return StatInfo('0', {})

  def _InitStatInfo(self, directory, svn_listing):
    files = _ListGoogleCodeSvnDir(svn_listing)
    child_revisions = []
    for cur in files:
      child_revisions.append(cur + ':0')
    stat_model = StatModel(key_name = directory, path = directory, revision = '0', child_revisions = child_revisions)
    stat_model.put()
    return self._StatFromModel(stat_model)

  def _UpdateStatInfo(self, updates):
    pass

  def _StatFromModel(self, model):
    child_revisions = {}
    for cur in model.child_revisions:
      value = cur.split(':')
      child_revisions[value[0]] = value[1]
    return file_system.StatInfo(model.revision, child_revisions)

  def Stat(self, path):
    directory = path.rsplit('/', 1)[0]
    if os.environ.get('CRXDOCZH_SLAVE_TYPE') == 'docs':
      full_path = (self._stat_fetcher._base_path.replace(SVN_URL, '') +
          '/' + directory)
      result = StatModel.get(db.Key.from_path('StatModel', full_path))
      stat_info = None
      if result is None:
        result = self._stat_fetcher.Fetch(directory + '/')
        if result.status_code == 404:
          raise ileNotFoundError(
              'Got 404 when fetching %s from %s for Stat' % (path, directory))
        stat_info = self._InitStatInfo(full_path, result.content)
      else:
        stat_info = self._StatFromModel(result)
    else:
      result = self._stat_fetcher.Fetch(directory + '/')
      if result.status_code == 404:
        raise FileNotFoundError(
            'Got 404 when fetching %s from %s for Stat' % (path, directory))
      stat_info = self._CreateStatInfo(result.content)
    if not path.endswith('/'):
      filename = path.rsplit('/', 1)[-1]
      if filename not in stat_info.child_versions:
        raise FileNotFoundError('%s was not in child versions' % filename)
      stat_info.version = stat_info.child_versions[filename]
    logging.info('Stat: %s of %s' % (path, stat_info.version))
    return stat_info

  @classmethod
  def GetVersion(cls):
    return _VERSION
