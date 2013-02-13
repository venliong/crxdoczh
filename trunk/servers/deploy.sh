#!/bin/bash

APPENGINE_PATH=~/google_appengine
APPENGINE_APPCFG=$APPENGINE_PATH/appcfg.py

deploy_slave_samples () (
  cp slave-samples/app.yaml app.yaml.0
  SED=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  sed $SED app.yaml.0 > slave-samples/app.yaml

  cp slave-samples/url_constants.py url_constants.py.0
  SED1=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  SED2=s/\<REPLACE_WITH_YOUR_SAMPLES_API_KEY\>/`cat private/SLAVE_SAMPLES_API_KEY`/
  sed $SED1 url_constants.py.0 | sed $SED2 > slave-samples/url_constants.py

  #$APPENGINE_APPCFG update slave-samples
  cat slave-samples/app.yaml slave-samples/url_constants.py | less

  mv app.yaml.0 slave-samples/app.yaml
  mv url_constants.py.0 slave-samples/url_constants.py
)

deploy_slave_docs () (
  cp slave-docs/url_constants.py url_constants.py.0
  SED1=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  SED2=s/\<REPLACE_WITH_YOUR_SAMPLES_API_KEY\>/`cat private/SLAVE_SAMPLES_API_KEY`/
  sed $SED1 url_constants.py.0 | sed $SED2 > slave-docs/url_constants.py

  #$APPENGINE_APPCFG update slave-docs
  cat slave-docs/url_constants.py | less

  mv url_constants.py.0 slave-docs/url_constants.py
)

deploy_slave_samples
deploy_slave_docs


