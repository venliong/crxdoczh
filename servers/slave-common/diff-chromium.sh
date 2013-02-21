#!/bin/bash

for x in *.py; do
  echo Diff $x:
  diff ../../chromium/official/src/chrome/common/extensions/docs/server2/$x $x
done

