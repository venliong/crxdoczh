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
  $APPENGINE_APPCFG update $DST
  if [ "$1" == samples ]; then
    $APPENGINE_APPCFG backends update $DST
  fi
  rm -rf $DST
)

prepare_keys

if [ "$1" == samples ]; then
  deploy_slave samples
fi

if [ "$1" == docs ]; then
  deploy_slave docs
fi

