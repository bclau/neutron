#Copyright 2013 Cloudbase Solutions SRL
#Copyright 2013 Pedro Navarro Perez
#All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import platform
import sys

import eventlet
eventlet.monkey_patch()

from hyperv.neutron import hyperv_neutron_agent
from oslo.config import cfg
from oslo import messaging

from neutron.agent.common import config
from neutron.agent import rpc as agent_rpc
from neutron.agent import securitygroups_rpc as sg_rpc
from neutron.common import config as common_config
from neutron.common import constants as n_const
from neutron.common import topics
from neutron import context
from neutron.i18n import _LE, _LI
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall

LOG = logging.getLogger(__name__)

agent_opts = [
    cfg.ListOpt(
        'physical_network_vswitch_mappings',
        default=[],
        help=_('List of <physical_network>:<vswitch> '
               'where the physical networks can be expressed with '
               'wildcards, e.g.: ."*:external"')),
    cfg.StrOpt(
        'local_network_vswitch',
        default='private',
        help=_('Private vswitch name used for local networks')),
    cfg.IntOpt('polling_interval', default=2,
               help=_("The number of seconds the agent will wait between "
                      "polling for local device changes.")),
    cfg.BoolOpt('enable_metrics_collection',
                default=False,
                help=_('Enables metrics collections for switch ports by using '
                       'Hyper-V\'s metric APIs. Collected data can by '
                       'retrieved by other apps and services, e.g.: '
                       'Ceilometer. Requires Hyper-V / Windows Server 2012 '
                       'and above')),
    cfg.IntOpt('metrics_max_retries',
               default=100,
               help=_('Specifies the maximum number of retries to enable '
                      'Hyper-V\'s port metrics collection. The agent will try '
                      'to enable the feature once every polling_interval '
                      'period for at most metrics_max_retries or until it '
                      'succeedes.'))
]

CONF = cfg.CONF
CONF.register_opts(agent_opts, "AGENT")
config.register_agent_state_opts_helper(cfg.CONF)


class HyperVSecurityAgent(sg_rpc.SecurityGroupAgentRpc):

    def __init__(self, context, plugin_rpc):
        # Note: as rootwrap is not supported on HyperV, root_helper is
        # passed in as None.
        super(HyperVSecurityAgent, self).__init__(context, plugin_rpc,
                                                  root_helper=None)
        if sg_rpc.is_firewall_enabled():
            self._setup_rpc()

    def _setup_rpc(self):
        self.topic = topics.AGENT
        self.endpoints = [HyperVSecurityCallbackMixin(self)]
        consumers = [[topics.SECURITY_GROUP, topics.UPDATE]]

        self.connection = agent_rpc.create_consumers(self.endpoints,
                                                     self.topic,
                                                     consumers)


class HyperVSecurityCallbackMixin(sg_rpc.SecurityGroupAgentRpcCallbackMixin):

    target = messaging.Target(version='1.1')

    def __init__(self, sg_agent):
        super(HyperVSecurityCallbackMixin, self).__init__()
        self.sg_agent = sg_agent


class HyperVNeutronAgent(hyperv_neutron_agent.HyperVNeutronAgentMixin):
    # Set RPC API version to 1.1 by default.
    target = messaging.Target(version='1.1')

    def __init__(self):
        super(HyperVNeutronAgent, self).__init__(conf=CONF)
        self._set_agent_state()
        self._setup_rpc()

    def _set_agent_state(self):
        self.agent_state = {
            'binary': 'neutron-hyperv-agent',
            'host': cfg.CONF.host,
            'topic': n_const.L2_AGENT_TOPIC,
            'configurations': {'vswitch_mappings':
                               self._physical_network_mappings},
            'agent_type': n_const.AGENT_TYPE_HYPERV,
            'start_flag': True}

    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context,
                                        self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception(_LE("Failed reporting state!"))

    def _setup_rpc(self):
        self.agent_id = 'hyperv_%s' % platform.node()
        self.topic = topics.AGENT
        self.plugin_rpc = agent_rpc.PluginApi(topics.PLUGIN)
        self.sg_plugin_rpc = sg_rpc.SecurityGroupServerRpcApi(topics.PLUGIN)

        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)

        # RPC network init
        self.context = context.get_admin_context_without_session()
        # Handle updates from service
        self.endpoints = [self]
        # Define the listening consumers for the agent
        consumers = [[topics.PORT, topics.UPDATE],
                     [topics.NETWORK, topics.DELETE],
                     [topics.PORT, topics.DELETE],
                     [topics.TUNNEL, topics.UPDATE]]
        self.connection = agent_rpc.create_consumers(self.endpoints,
                                                     self.topic,
                                                     consumers)

        self.sec_groups_agent = HyperVSecurityAgent(
            self.context, self.sg_plugin_rpc)
        report_interval = CONF.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)


def main():
    common_config.init(sys.argv[1:])
    common_config.setup_logging()

    plugin = HyperVNeutronAgent()

    # Start everything.
    LOG.info(_LI("Agent initialized successfully, now running... "))
    plugin.daemon_loop()
