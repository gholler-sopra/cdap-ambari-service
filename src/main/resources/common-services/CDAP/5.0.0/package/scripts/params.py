# coding=utf8
# Copyright © 2015-2017 Cask Data, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#

import os
import ambari_helpers as helpers
from resource_management import *
from resource_management.libraries.functions import get_kinit_path

# config object that holds the configurations declared in the -config.xml file
config = Script.get_config()
tmp_dir = Script.get_tmp_dir()

stack_dir = os.path.realpath(__file__).split('/scripts')[0]
package_dir = os.path.realpath(__file__).split('/package')[0] + '/package/'
files_dir = package_dir + 'files/'
scripts_dir = package_dir + 'scripts/'
distribution = platform.linux_distribution()[0].lower()
hostname = config['agentLevelParams']['hostname'].lower()
java64_home = config['ambariLevelParams']['java_home']
user_group = config['configurations']['cluster-env']['user_group']

hdp_version = helpers.get_hdp_version()
hadoop_lib_home = helpers.get_hadoop_lib()

if distribution.startswith('debian') or distribution.startswith('ubuntu'):
    os_repo_dir = '/etc/apt/sources.list.d/'
    repo_file = 'cdap.list'
    package_mgr = 'apt-get'
    key_cmd_str_part = files_dir + "/pubkey.gpg"
    key_cmd = ("apt-key", "add", key_cmd_str_part)
    cache_cmd = ('apt-get', 'update')
    repo_url = config['configurations']['cdap-env']['apt_repo_url']
    gpgcheck_enabled = config['configurations']['cdap-env']['apt_gpgcheck_enabled']
else:
    os_repo_dir = '/etc/yum.repos.d/'
    repo_file = 'cdap.repo'
    package_mgr = 'yum'
    key_cmd_str_part = files_dir + "/pubkey.gpg"
    key_cmd = ("rpm", "--import", key_cmd_str_part)
    cache_cmd = ('yum', '--disablerepo=*', '--enablerepo=CDAP', 'makecache')
    repo_url = config['configurations']['cdap-env']['yum_repo_url']
    gpgcheck_enabled = config['configurations']['cdap-env']['yum_gpgcheck_enabled']

cdap_user = config['configurations']['cdap-env']['cdap_user']
log_dir = config['configurations']['cdap-env']['cdap_log_dir']
pid_dir = config['configurations']['cdap-env']['cdap_pid_dir']
cdap_auth_heapsize = config['configurations']['cdap-env']['cdap_auth_heapsize']
cdap_kafka_heapsize = config['configurations']['cdap-env']['cdap_kafka_heapsize']
cdap_master_heapsize = config['configurations']['cdap-env']['cdap_master_heapsize']
cdap_router_heapsize = config['configurations']['cdap-env']['cdap_router_heapsize']

etc_prefix_dir = "/etc/cdap"
cdap_conf_dir = "/etc/cdap/conf.ambari"
dfs = config['configurations']['core-site']['fs.defaultFS']

cdap_env_sh_template = config['configurations']['cdap-env']['content']
cdap_logback_xml_template = config['configurations']['cdap-logback']['logback-content']
cdap_logback_container_xml_template = config['configurations']['cdap-logback-container']['logback-container-content']

map_cdap_site = config['configurations']['cdap-site']

# Example: root.namespace
root_namespace = map_cdap_site['root.namespace']
if map_cdap_site['hdfs.namespace'] == '/${root.namespace}':
    hdfs_namespace = '/' + root_namespace
else:
    hdfs_namespace = map_cdap_site['hdfs.namespace']



cdap_security_enabled = config['configurations']['cdap-site']['security.enabled']
cdap_access_logging = config['configurations']['cdap-logback']['access_logging']

# Kerberos stuff
kerberos_enabled = config['configurations']['cluster-env']['security_enabled']
hdfs_user_keytab = config['configurations']['hadoop-env']['hdfs_user_keytab']
hdfs_user = config['configurations']['hadoop-env']['hdfs_user']
hdfs_principal_name = config['configurations']['hadoop-env']['hdfs_principal_name']
kinit_path_local = get_kinit_path(default('/configurations/kerberos-env/executable_search_paths', None))
cdap_principal_name = config['configurations']['cdap-env']['cdap_principal_name']
cdap_user_keytab = config['configurations']['cdap-env']['cdap_user_keytab']

if kerberos_enabled:
    master_jaas_princ = config['configurations']['cdap-site']['cdap.master.kerberos.principal'].replace('_HOST', hostname)
    master_keytab_path = config['configurations']['cdap-site']['cdap.master.kerberos.keytab']
    client_jaas_config_file = format("{cdap_conf_dir}/cdap_client_jaas.conf")
    master_jaas_config_file = format("{cdap_conf_dir}/cdap_master_jaas.conf")
    kinit_cmd = format("{kinit_path_local} -kt {cdap_user_keytab} {cdap_principal_name};")
    kinit_cmd_hdfs = format("{kinit_path_local} -kt {hdfs_user_keytab} {hdfs_principal_name};")
    kinit_cmd_master = format("{kinit_path_local} -kt {master_keytab_path} {master_jaas_princ};")
    cdap_hdfs_user = cdap_user
else:
    kinit_cmd = ""
    kinit_cmd_hdfs = ""
    kinit_cmd_master = ""
    cdap_hdfs_user = "yarn"

# Get ZooKeeper variables
zk_client_port = str(default('/configurations/zoo.cfg/clientPort', None))
zk_hosts = config['clusterHostInfo']['zookeeper_server_hosts']
zk_hosts.sort()
cdap_zookeeper_quorum = helpers.generate_quorum(zk_hosts, zk_client_port) + '/' + root_namespace

kafka_log_dir = map_cdap_site['kafka.server.log.dirs']
# CDAP requires Kafka 0.8, so use CDAP_KAFKA
# kafka_bind_port = str(default('/configurations/kafka-broker/port', 6667))
# kafka_hosts = config['clusterHostInfo']['kafka_broker_hosts']
kafka_bind_port = str(default('/configurations/cdap-site/kafka.server.port', 9092))
kafka_hosts = config['clusterHostInfo']['cdap_kafka_hosts']
kafka_hosts.sort()
cdap_kafka_brokers = helpers.generate_quorum(kafka_hosts, kafka_bind_port)

router_hosts = config['clusterHostInfo']['cdap_router_hosts']
router_hosts.sort()
cdap_router_host = router_hosts[0]
if len(router_hosts) > 1:
    for val in router_hosts:
        if val == hostname:
            cdap_router_host = hostname

# Return first host, if more than one
ui_hosts = config['clusterHostInfo']['cdap_ui_hosts']
ui_hosts.sort()
cdap_ui_host = ui_hosts[0]
su_hdfs_user = '/bin/su hdfs'
su_cdap_user = '/bin/su ' + cdap_user

