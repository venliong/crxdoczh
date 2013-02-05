#!/bin/bash

rsync -a --exclude='.svn' --exclude='*.cc' --exclude='*.h' ../official/src ./
svn status

