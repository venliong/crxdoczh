#!/bin/bash

status=0

for key_file in private/*; do
  if [ $key_file != private/keys.sed ]; then
    if grep `cat $key_file` slave-common/* slave-docs/* slave-samples/*; then
      echo WARNING: Private keys should not be placed in the source code.
      status=1
    fi
  fi
done

exit $status
