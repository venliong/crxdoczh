#!/bin/bash

#./update_static.sh

current_dir=$PWD

cd ../chromium/crxdoczh/src/chrome/common/extensions/docs/templates/public/extensions/
for file in *; do
  ../../../server2/preview.py -r trunk/extensions/$file > $current_dir/extensions/$file
done
cd -
