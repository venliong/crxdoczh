#!/bin/bash

rsync -a --exclude='.svn' ../chromium/crxdoczh/src/chrome/common/extensions/docs/static ./apps/
rsync -a --exclude='.svn' ../chromium/crxdoczh/src/chrome/common/extensions/docs/static ./extensions/
