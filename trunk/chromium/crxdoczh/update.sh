#!/bin/bash

rsync -a --exclude='.svn' ../official/src ./
svn status

