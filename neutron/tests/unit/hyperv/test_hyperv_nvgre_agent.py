# Copyright 2015 Cloudbase Solutions SRL
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
Unit tests for Windows Hyper-V NVGRE driver.
"""

import mock

from neutron.plugins.hyperv.agent import hyperv_nvgre_agent
from neutron.plugins.hyperv.agent import utilsfactory
from neutron.tests import base


class TestHyperVNeutronAgent(base.BaseTestCase):

    _FAKE_CUSTOMER_ADDR = 'fake_customer_address'
    _FAKE_PREFIX_LENGTH = 24
    _FAKE_SEG_ID = 9001
    _FAKE_NETWORK_NAME = 'fake_network_name'
    _FAKE_PORT_ID = 'fake_port_id'

    _FAKE_MAC_ADDRESS = 'fake_mac_address'
    _FAKE_IP = 'fake_ip'
    _FAKE_NETWORK_UUID = 'fake_network_uuid'
    _FAKE_SWITCH_NAME = 'fake_switch_name'
    _FAKE_SUBNET_ID = 'fake_subnet_id'
    _FAKE_CIDR = 'fake_cidr'

    def setUp(self):
        super(TestHyperVNeutronAgent, self).setUp()

        utilsfactory._get_windows_version = mock.MagicMock(
            return_value='6.2.0')

        self._agent = hyperv_nvgre_agent.HyperVNvgreAgent([])
        self._agent._notifier = mock.Mock()
        self._agent._utils = mock.MagicMock()
        self._agent._nvgre_utils = mock.MagicMock()
        self._agent._n_client = mock.MagicMock()
        self._agent._db = mock.MagicMock()

    def test_bind_nvgre_port_ok(self):
        self._agent._nvgre_utils.get_network_iface_ip = mock.MagicMock(
            return_value=(self._FAKE_CUSTOMER_ADDR, self._FAKE_PREFIX_LENGTH))

        self._test_bind_nvgre_port(True)

    def test_bind_nvgre_port_not_ok(self):
        self._agent._nvgre_utils.get_network_iface_ip = mock.MagicMock(
            return_value=(None, None))

        self._test_bind_nvgre_port(False)

    def _test_bind_nvgre_port(self, expected):
        self._agent.bind_gre_port(
            self._FAKE_SEG_ID, self._FAKE_NETWORK_NAME, self._FAKE_PORT_ID)

        self.assertEqual(self._agent._utils.set_vswitch_port_vsid.called,
                         expected)
        self.assertEqual(self._agent._nvgre_utils.create_lookup_record.called,
                         expected)
        self.assertEqual(self._agent._db.add_lookup_record.called, expected)
        self.assertEqual(self._agent._notifier.lookup_update.called, expected)

    def test_lookup_update_ok(self):
        args = {
            'lookup_ip': self._FAKE_IP,
            'lookup_details': {
                'customer_addr': self._FAKE_CUSTOMER_ADDR,
                'mac_address': self._FAKE_MAC_ADDRESS,
                'customer_vsid': self._FAKE_SEG_ID
            }
        }

        self._agent._register_lookup_record = mock.MagicMock()
        self._agent.lookup_update(self._agent._context, **args)
        self._agent._register_lookup_record.assert_called_once_with(
            self._FAKE_IP,
            self._FAKE_CUSTOMER_ADDR,
            self._FAKE_MAC_ADDRESS,
            self._FAKE_SEG_ID)

    def test_lookup_update_not_ok(self):
        self._agent._register_lookup_record = mock.MagicMock()
        self._agent.lookup_update(self._agent._context)
        self.assertFalse(self._agent._register_lookup_record.called)

    def test_bind_gre_network(self):
        self._agent._n_client.get_network_subnets = mock.MagicMock(
            return_value=[self._FAKE_SUBNET_ID])

        self._agent._n_client.get_network_subnet_cidr = mock.MagicMock(
            return_value=self._FAKE_CIDR)

        self._agent.bind_gre_network(
            self._FAKE_NETWORK_UUID, self._FAKE_SWITCH_NAME, self._FAKE_SEG_ID)

        self._agent._nvgre_utils.create_customer_route.assert_called_once_with(
            self._FAKE_SEG_ID, self._FAKE_SWITCH_NAME, self._FAKE_CIDR)
