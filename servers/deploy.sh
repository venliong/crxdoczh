#!/bin/bash

APPENGINE_PATH=~/google_appengine
APPENGINE_APPCFG=$APPENGINE_PATH/appcfg.py
KEYS_SED=private/keys.sed

prepare_keys () {
  cat > $KEYS_SED << END_OF_SED
#!/bin/sed -f
s#<REPLACE_WITH_YOUR_DOCS_APP_ID>#`cat private/SLAVE_DOCS_APP_ID`#
s#<REPLACE_WITH_YOUR_DOCS_API_KEY>#`cat private/SLAVE_DOCS_API_KEY`#
s#<REPLACE_WITH_YOUR_SAMPLES_APP_ID>#`cat private/SLAVE_SAMPLES_APP_ID`#
s#<REPLACE_WITH_YOUR_SAMPLES_API_KEY>#`cat private/SLAVE_SAMPLES_API_KEY`#
s#<REPLACE_WITH_YOUR_GITHUB_API_USERNAME>#`cat private/GITHUB_API_USERNAME`#
s#<REPLACE_WITH_YOUR_GITHUB_API_PASSWORD>#`cat private/GITHUB_API_PASSWORD`#
END_OF_SED
}

deploy_slave () (
  COMMON=slave-common
  SRC=slave-$1
  DST=slave-deploy
  CP='rsync -a --exclude=.svn --exclude=test_data'
  mkdir $DST
  $CP $COMMON/* $DST/
  $CP $SRC/* $DST/
  sed -f $KEYS_SED $COMMON/url_constants.py > $DST/url_constants.py
  sed -f $KEYS_SED $SRC/app.yaml > $DST/app.yaml
  $DST/build_server.py
  #$APPENGINE_APPCFG update $DST
  $APPENGINE_APPCFG backends update $DST
  rm -rf $DST
)

deploy_slave_samples () (
  cp slave-samples/app.yaml app.yaml.0
  SED=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  sed $SED app.yaml.0 > slave-samples/app.yaml

  cp slave-samples/url_constants.py url_constants.py.0
  SED1=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  SED2=s/\<REPLACE_WITH_YOUR_SAMPLES_API_KEY\>/`cat private/SLAVE_SAMPLES_API_KEY`/
  sed $SED1 url_constants.py.0 | sed $SED2 > slave-samples/url_constants.py

  $APPENGINE_APPCFG update slave-samples
  $APPENGINE_APPCFG backends update slave-samples
  #cat slave-samples/app.yaml slave-samples/url_constants.py | less

  mv app.yaml.0 slave-samples/app.yaml
  mv url_constants.py.0 slave-samples/url_constants.py
)

deploy_slave_docs () (
  cp slave-docs/app.yaml app.yaml.0
  cp slave-docs/url_constants.py url_constants.py.0
  SED1=s/\<REPLACE_WITH_YOUR_DOCS_APP_ID\>/`cat private/SLAVE_DOCS_APP_ID`/
  SED2=s/\<REPLACE_WITH_YOUR_DOCS_API_KEY\>/`cat private/SLAVE_DOCS_API_KEY`/
  SED3=s/\<REPLACE_WITH_YOUR_SAMPLES_APP_ID\>/`cat private/SLAVE_SAMPLES_APP_ID`/
  SED4=s/\<REPLACE_WITH_YOUR_SAMPLES_API_KEY\>/`cat private/SLAVE_SAMPLES_API_KEY`/
  sed $SED1 url_constants.py.0 | sed $SED2 | sed $SED3 | sed $SED4 > slave-docs/url_constants.py
  sed $SED1 app.yaml.0 | sed $SED2 | sed $SED3 | sed $SED4 > slave-docs/app.yaml

  $APPENGINE_APPCFG update slave-docs
  #cat slave-docs/url_constants.py slave-docs/app.yaml | less

  mv app.yaml.0 slave-docs/app.yaml
  mv url_constants.py.0 slave-docs/url_constants.py
)

prepare_keys

if [ "$1" == samples ]; then
  deploy_slave samples
fi

if [ "$1" == docs ]; then
  deploy_slave docs
fi

