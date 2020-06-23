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

import ambari_helpers as helpers
from resource_management import *
import json
import time
import subprocess as sp

class Master(Script):
    def install(self, env):
        print('Install the CDAP Master')
        import params
        # Add repository file
        helpers.add_repo(
            params.files_dir + params.repo_file,
            params.os_repo_dir
        )
        # Install any global packages
        self.install_packages(env)
        # Workaround for CDAP-3961
        helpers.package('cdap-hbase-compat-2.0')
        # Install package
        helpers.package('cdap-master')
        self.configure(env)

    def start(self, env, upgrade_type=None):
        print('Start the CDAP Master')
        import params
        import status_params
        env.set_params(params)
        self.configure(env)

        helpers.create_hdfs_dir(params.hdfs_namespace, params.cdap_hdfs_user, 775)
        # Create user's HDFS home
        helpers.create_hdfs_dir('/user/' + params.cdap_user, params.cdap_user, 775)
        if params.cdap_hdfs_user != params.cdap_user:
            helpers.create_hdfs_dir('/user/' + params.cdap_hdfs_user, params.cdap_hdfs_user, 775)

        # fix insufficient permissions for some files that cdap master needs to read at startup
        helpers.fix_hive_conf_perms()

        # Hack to work around CDAP-1967
        self.remove_jackson(env)
        daemon_cmd = format('/opt/cdap/master/bin/cdap master start')
        no_op_test = format('ls {status_params.cdap_master_pid_file} >/dev/null 2>&1 && ps -p $(<{status_params.cdap_master_pid_file}) >/dev/null 2>&1')
        Execute(
            daemon_cmd,
            user=params.cdap_user,
            not_if=no_op_test
        )

    def executeShellCommands(self, command):
        output = ''
        status = 1

        pipe = sp.Popen(command, shell=True, stdout=sp.PIPE, stderr=sp.PIPE )
        if pipe.wait() != 0:
            print("Command execution fail " + command)
            return status, output
        output = pipe.communicate()[0].strip()
        status = 0
        return status, output

    def __killOlderProcesses(self):
        # execute ls /cdap/election/master.services and check if emty then only execute the following steps else exit

        import params

        zkCliCommand = '/usr/hdp/current/zookeeper-client/bin/zkCli.sh -server ' + params.cdap_zookeeper_quorum

        Execute(zkCliCommand + " ls /election/master.services > /tmp/election_master_services", user='zookeeper')
        status, output = self.executeShellCommands('tail -n1 /tmp/election_master_services')
        if status != 0:
            Execute("rm -rf /tmp/election_master_services", user='zookeeper')
            return
        if (not(output.startswith('[') and output.endswith(']') and output == '[]')):
            Execute("rm -rf /tmp/election_master_services", user='zookeeper')
            print('output value is not equal to []')
            return
        # exectute ls /cdap/twill and save its output
        Execute(zkCliCommand + " ls /twill > /tmp/twill_master_services", user='zookeeper')
        status, output = self.executeShellCommands('tail -n1 /tmp/twill_master_services')
        if status != 0:
            Execute("rm -rf /tmp/twill_master_services", user='zookeeper')
            return
        if (not(output.startswith('[') and output.endswith(']') and output != '[]')):
            Execute("rm -rf /tmp/twill_master_services", user='zookeeper')
            print('output value is equal to []')
            return
        result = output[1:len(output)-1]
        services = result.split(',')
        # iterate over last output and execute ls /cdap/twill/<name>/instances and save its output
        for service in services:
            service = service.strip()
            if (service == 'master.services'):
                continue
            Execute(zkCliCommand + " ls /twill/" + service + "/instances > /tmp/twill_" + service + "_instances", user='zookeeper')
            status, output = self.executeShellCommands('tail -n1 /tmp/twill_' + service + '_instances')
            if status != 0:
                Execute("rm -rf /tmp/twill_" + service + "_instances", user='zookeeper')
                continue        
            if (not(output.startswith('[') and output.endswith(']') and output != '[]')):
                Execute("rm -rf /tmp/twill_" + service + "_instances", user='zookeeper')
                print('output value is equal to []')
                continue
            Execute("rm -rf /tmp/twill_" + service + "_instances", user='zookeeper')
            result = output[1:len(output)-1]
            # execute get /cdap/twill/<name>/instances/<last_output and save its output
            Execute(zkCliCommand + " get /twill/" + service + "/instances/" + result + " > /tmp/twill_" + service + "_instances_output", user='zookeeper')
            status, output = self.executeShellCommands('tail -n1 /tmp/twill_' + service + '_instances_output')
            if status != 0:
                Execute("rm -rf /tmp/twill_" + service + "_instances_output", user='zookeeper')
                continue
            data = json.loads(output)
            status = 1
            if 'data' in data:
                if 'containerId' in data['data']:
                    status = 0
            if status != 0:
                Execute("rm -rf /tmp/twill_" + service + "_instances_output", user='zookeeper') 
                print('conatinerId key not present in data')
                continue
            Execute("rm -rf /tmp/twill_" + service + "_instances_output", user='zookeeper') 
            container_id = data['data']['containerId']
            container_values = container_id.split('_')
            if (len(container_values) <= 3):
                print("container id name is not correct")
                continue
            applicationId = "application_" + container_values[2] + "_" + container_values[3] 
            kinit_cmd = params.kinit_cmd_master
            kill_application_cmd = format("{kinit_cmd} yarn application -kill " + applicationId)
            Execute(kill_application_cmd, user='cdap')
        Execute("rm -rf /tmp/twill_master_services", user='zookeeper')                  
        Execute("rm -rf /tmp/election_master_services", user='zookeeper')             


    def stop(self, env, upgrade_type=None):
        print('Stop the CDAP Master')
        import params
        import status_params
        daemon_cmd = format('/opt/cdap/master/bin/cdap master stop')
        no_op_test = format('ls {status_params.cdap_master_pid_file} >/dev/null 2>&1 && ps -p $(<{status_params.cdap_master_pid_file}) >/dev/null 2>&1')
        Execute(
            daemon_cmd,
            user=params.cdap_user,
            only_if=no_op_test
        )
        print('sleep 60 seconds before kill the other service processes')
        time.sleep(60)
        self.__killOlderProcesses()

    def status(self, env):
        import status_params
        check_process_status(status_params.cdap_master_pid_file)

    def configure(self, env):
        print('Configure the CDAP Master')
        import params
        env.set_params(params)
        helpers.cdap_config('master')

    def upgrade(self, env):
        self.run_class(
            env,
            classname='co.cask.cdap.data.tools.UpgradeTool',
            label='CDAP Upgrade Tool',
            arguments='upgrade force'
        )

    def upgrade_hbase(self, env):
        self.run_class(
            env,
            classname='co.cask.cdap.data.tools.UpgradeTool',
            label='CDAP HBase Coprocessor Upgrade Tool',
            arguments='upgrade_hbase force'
        )

    def postupgrade(self, env):
        self.run_class(
            env,
            classname='co.cask.cdap.data.tools.flow.FlowQueuePendingCorrector',
            label='CDAP Post-Upgrade Tool'
        )

    def queue_debugger(self, env):
        self.run_class(
            env,
            classname='co.cask.cdap.data.tools.SimpleHBaseQueueDebugger',
            label='CDAP Queue Debugger Tool'
        )

    def jobqueue_debugger(self, env):
        self.run_class(
            env,
            classname='co.cask.cdap.data.tools.JobQueueDebugger',
            label='CDAP Job Queue Debugger Tool'
        )

    def run_class(self, env, classname, label=None, arguments=''):
        if label is None:
            label = classname
        print('Running: ' + label)
        import params
        cmd = format("/opt/cdap/master/bin/cdap run %s %s" % (classname, arguments))
        Execute(
            cmd,
            user=params.cdap_user
        )

    def remove_jackson(self, env):
        jackson_check = format('ls -1 /opt/cdap/master/lib/org.codehaus.jackson* 2>/dev/null')
        jackson_rm_cmd = ('rm', '-f', '/opt/cdap/master/lib/org.codehaus.jackson.jackson-*')
        Execute(
            jackson_rm_cmd,
            not_if=jackson_check,
            sudo=True
        )

if __name__ == "__main__":
    Master().execute()
