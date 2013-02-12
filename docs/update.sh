#!/bin/bash

#./update_static.sh

current_dir=$PWD

# Usage: render_docs {extensions/apps}
render_docs () (
  cd ../chromium/crxdoczh/src/chrome/common/extensions/docs/templates/public/$1/
  for file in *; do
    echo Rendering $1/$file...
    ../../../server2/preview.py -r trunk/$1/$file > $current_dir/$1/$file
  done
  cd -
)

echo Rendering extensions docs...
render_docs extensions
echo
echo Rendering apps docs...
render_docs apps

