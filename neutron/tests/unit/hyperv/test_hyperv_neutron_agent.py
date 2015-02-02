# Copyright 2013 Cloudbase Solutions SRL
# Copyright 2013 Pedro Navarro Perez
# All Rights Reserved.
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

"""
Unit tests for Windows Hyper-V virtual switch neutron driver
"""

import mock
from oslo.config import cfg

from neutron.plugins.hyperv.agent import hyperv_neutron_agent
from neutron.tests import base


class TestHyperVNeutronAgent(base.BaseTestCase):

    def setUp(self):
        super(TestHyperVNeutronAgent, self).setUp()

        cfg.CONF.set_default('firewall_driver',
                             'neutron.agent.firewall.NoopFirewallDriver',
                             group='SECURITYGROUP')
        self.agent = hyperv_neutron_agent.HyperVNeutronAgent()
        self.agent.context = mock.Mock()

        fake_agent_state = {
            'binary': 'neutron-hyperv-agent',
            'host': 'fake_host_name',
            'topic': 'N/A',
            'configurations': {'vswitch_mappings': ['*:MyVirtualSwitch']},
            'agent_type': 'HyperV agent',
            'start_flag': True}
        self.agent_state = fake_agent_state

    def test_report_state(self):
        with mock.patch.object(self.agent.state_rpc,
                               "report_state") as report_st:
            self.agent._report_state()
            report_st.assert_called_with(self.agent.context,
                                         self.agent.agent_state)
            self.assertNotIn("start_flag", self.agent.agent_state)

    def test_main(self):
        with mock.patch.object(hyperv_neutron_agent,
                               'HyperVNeutronAgent') as plugin:
            with mock.patch.object(hyperv_neutron_agent,
                                   'common_config') as common_config:
                hyperv_neutron_agent.main()

                self.assertTrue(common_config.init.called)
                self.assertTrue(common_config.setup_logging.called)
                plugin.assert_has_calls([mock.call().daemon_loop()])
