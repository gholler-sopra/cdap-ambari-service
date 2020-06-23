#!/usr/bin/env bash

VERSION=${VERSION:-5.1.216}
RELEASE=${RELEASE:-42}
RPM_RELEASE_PATH=${RPM_RELEASE_PATH:-http:\\/\\/repository.cask.co\\/centos\\/6\\/x86_64\\/cdap\\/5.1\\/}
DEB_RELEASE_PATH=${DEB_RELEASE_PATH:-http:\\/\\/master1.diane.com\\/repos\\/ubuntu18\\/cdap\\/5.1\\/}
REPO_ID=CDAP-${VERSION}
PACKAGE_VERSION=${VERSION:-5.1.0}
PACKAGE_ITERATION=${PACKAGE_ITERATION:-1}
PACKAGE_FORMATS=${PACKAGE_FORMATS:-deb}

LICENSE="Copyright © 2015-2018 Cask Data, Inc. Licensed under the Apache License, Version 2.0."
RPM_FPM_ARGS="-t rpm --rpm-os linux"
DEB_FPM_ARGS="-t deb"

if [[ ${PACKAGE_VERSION} =~ "-SNAPSHOT" ]] ; then
  PACKAGE_VERSION=${PACKAGE_VERSION/-SNAPSHOT/.$(date +%s)}
fi

clean() { rm -rf build target; };
setup() { mkdir -p build/var/lib/ambari-server/resources target; };

install() {
  cp -a src/main/resources/* build/var/lib/ambari-server/resources
  echo rpm release_path: $RPM_RELEASE_PATH
  echo deb release_path: $DEB_RELEASE_PATH
  echo version: $VERSION
  echo build_number: $RELEASE
  echo repo_id: $REPO_ID
  sed -i'' -e "s/RPM_RELEASE_PATH/${RPM_RELEASE_PATH}/g" \
    build/var/lib/ambari-server/resources/stacks/*/*/services/CDAP/repos/repoinfo.xml \
    build/var/lib/ambari-server/resources/common-services/CDAP/5.0.0/configuration/cdap-env.xml
  sed -i'' -e "s/DEB_RELEASE_PATH/${DEB_RELEASE_PATH}/g" \
    build/var/lib/ambari-server/resources/stacks/*/*/services/CDAP/repos/repoinfo.xml \
    build/var/lib/ambari-server/resources/common-services/CDAP/5.0.0/configuration/cdap-env.xml
  sed -i'' -e "s/REPO_ID/${REPO_ID}/g" \
    build/var/lib/ambari-server/resources/stacks/*/*/services/CDAP/repos/repoinfo.xml
}

clean && setup && install

__failed=0
cd target
for p in ${PACKAGE_FORMATS} ; do
  case ${p} in
    deb)
      fpm \
        --name cdap-ambari-service \
        --license "${LICENSE}" \
        --vendor "Cask Data, Inc." \
        --maintainer support@cask.co \
        --description "Ambari service for Cask Data Application Platform (CDAP)" \
        -s dir \
        -a all \
        --url "http://cask.co" \
        --category misc \
        --depends "python > 2.6" \
        --depends "ambari-server > 2.2" \
        --version ${PACKAGE_VERSION} \
        --iteration ${RELEASE} \
        ${DEB_FPM_ARGS} \
        -C ../build \
        var
      __ret=$?
      ;;
    rpm)
      fpm \
        --name cdap-ambari-service \
        --license "${LICENSE}" \
        --vendor "Cask Data, Inc." \
        --maintainer support@cask.co \
        --description "Ambari service for Cask Data Application Platform (CDAP)" \
        -s dir \
        -a all \
        --url "http://cask.co" \
        --category misc \
        --depends "python > 2.6" \
        --depends "ambari-server > 2.2" \
        --version ${PACKAGE_VERSION} \
        --iteration ${RELEASE} \
        ${RPM_FPM_ARGS} \
        -C ../build \
        var
      __ret=$?
     ;;
    *)
      echo "Unsupported format! ${p}"
      exit 1
      ;;
  esac
  [[ ${__ret} -ne 0 ]] && __failed=1
done

exit ${__failed} # It's okay if this is empty
