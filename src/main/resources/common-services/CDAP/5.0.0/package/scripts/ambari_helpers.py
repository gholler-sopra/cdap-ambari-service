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
from resource_management import *
from resource_management.libraries.functions.version import format_stack_version

def create_hdfs_dir(path, owner, perms):
    import params
    kinit_cmd = params.kinit_cmd_hdfs
    mkdir_cmd = format("{kinit_cmd} hadoop fs -mkdir -p {path}")
    chown_cmd = format("{kinit_cmd} hadoop fs -chown {owner} {path}")
    chmod_cmd = format("{kinit_cmd} hadoop fs -chmod {perms} {path}")
    Execute(mkdir_cmd, user='hdfs')
    Execute(chown_cmd, user='hdfs')
    Execute(chmod_cmd, user='hdfs')


# def package(name):
#     import params
#     yum_cmd = (params.package_mgr, '--disablerepo=*', '--enablerepo=CDAP', 'install', '-y', name)
#     Execute(yum_cmd, sudo=True)

def package(name):
    import params
    print("params.package_mgr:  " + params.package_mgr )
    install_cmd = (params.package_mgr,)
    if params.package_mgr == 'apt-get':
        # FIXME how to disable/enable repo
        install_cmd += ( 'install', '-y', name)
    else:
        install_cmd += ('--disablerepo=*', '--enablerepo=CDAP', 'install', '-y', name)
    Execute(install_cmd, sudo=True)

def fix_hive_conf_perms():
    fix_cmd = ('chmod','-R', 'a+r', '/usr/hdp/current/hive-client/conf')
    Execute(fix_cmd, sudo=True)

def add_symlink(source, target):
    ln_cmd = ('ln', '-nsf',  source , target)
    Execute(ln_cmd, sudo=True)


def add_repo(source, dest):
    import params
    dest_file = dest + params.repo_file
    tmp_dest_file = "/tmp/" + params.repo_file

    # Remove previous dest_file always
    rm_dst_file_cmd = ('rm' , '-f' , dest_file)
    Execute(rm_dst_file_cmd, sudo=True)
    # Skip sed if CDAP repos exist, we're on a newer Ambari... yay!
    no_op_test = format('ls {dest} 2>/dev/null | grep CDAP >/dev/null 2>&1')
    Execute(
        "sed -e 's#REPO_URL#%s#' -e 's#GPGCHECK#%s#' %s > %s" % (params.repo_url, int(params.gpgcheck_enabled), source, tmp_dest_file),
        not_if=no_op_test
    )
    copy_to_repo_file_cmd = ("/bin/mv", '-f', tmp_dest_file, dest_file)
    Execute(copy_to_repo_file_cmd, sudo=True)
    Execute(params.key_cmd, sudo=True)
    Execute(params.cache_cmd, sudo=True)


def cdap_config(name=None):
    import params
    print('Setting up CDAP configuration for ' + name)
    # We're only setup for *NIX, for now
    
    etc_dir = params.etc_prefix_dir
    create_dir_cmd = ("/bin/mkdir", '-p', etc_dir)
    chmod_dir_cmd = ("/bin/chmod", "755", etc_dir)
    Execute(create_dir_cmd, sudo=True)
    Execute(chmod_dir_cmd, sudo=True)

#     Directory(
#         params.etc_prefix_dir,
#         mode=755
#     )

    # Why don't we use Directory here? A: parameters changed between Ambari minor versions
    for i in params.cdap_conf_dir, params.log_dir, params.pid_dir:
        mkdir_dirs_cmd = ("mkdir", "-p", i)
        user_grp_str = params.cdap_user + ":" + params.user_group
        chown_dirs_cmd = ("chown", user_grp_str, i)
        Execute(mkdir_dirs_cmd, sudo=True)
        Execute(chown_dirs_cmd, sudo=True)

    for i in 'security', 'site':
        XmlConfig(
            "cdap-%s.xml" % (i),
            conf_dir=params.cdap_conf_dir,
            configurations=params.config['configurations']["cdap-%s" % (i)],
            owner=params.cdap_user,
            group=params.user_group
        )

    File(
        format("{params.cdap_conf_dir}/cdap-env.sh"),
        owner=params.cdap_user,
        content=InlineTemplate(params.cdap_env_sh_template)
    )

    File(
        format("{params.cdap_conf_dir}/logback.xml"),
        owner=params.cdap_user,
        content=InlineTemplate(params.cdap_logback_xml_template)
    )

    File(
        format("{params.cdap_conf_dir}/logback-container.xml"),
        owner=params.cdap_user,
        content=InlineTemplate(params.cdap_logback_container_xml_template)
    )

    if params.cdap_security_enabled:
        XmlConfig(
            'cdap-security.xml',
            conf_dir=params.cdap_conf_dir,
            configurations=params.config['configurations']['cdap-security'],
            owner=params.cdap_user,
            group=params.user_group
        )

    if params.kerberos_enabled:
        File(
            format(params.client_jaas_config_file),
            owner=params.cdap_user,
            content=Template("cdap_client_jaas.conf.j2")
        )

        File(
            format(params.master_jaas_config_file),
            owner=params.cdap_user,
            content=Template("cdap_master_jaas.conf.j2")
        )

    update_alternatives_cmd = ("update-alternatives", "--install", "/etc/cdap/conf", "cdap-conf", params.cdap_conf_dir, "50")
    Execute(update_alternatives_cmd, sudo=True)


def has_hive():
    import params
    if len(params.hive_metastore_host) > 0:
        return true
    else:
        return false


def generate_quorum(hosts, port):
    p = ':' + port
    return (p + ',').join(hosts) + p


def get_hdp_version():
    return default("/hostLevelParams/hostRepositories/commandRepos/1/repoVersion", None)


def get_hadoop_lib():
    v = get_hdp_version()
    arr = v.split('.')
    maj_min = float("%s.%s" % (arr[0], arr[1]))
    if maj_min >= 2.2:
        hadoop_lib = "/usr/hdp/%s/hadoop/lib" % (v)
    else:
        hadoop_lib = '/usr/lib/hadoop/lib'
    return hadoop_lib
