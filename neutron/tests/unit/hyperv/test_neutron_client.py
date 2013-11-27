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
Unit tests for the Hyper-V neutron client.
"""

import mock

from neutron.plugins.hyperv import neutron_client
from neutron.tests import base


class TestNeutronClient(base.BaseTestCase):
    _FAKE_NETWORK_ID = 'fake_network_id'
    _FAKE_SUBNET_ID = 'fake_subnet_id'
    _FAKE_PORT_ID = 'fake_port_id'

    _FAKE_CIDR = 'fake_cidr'
    _FAKE_IP_ADDR = 'fake_ip_addr'

    def setUp(self):
        super(TestNeutronClient, self).setUp()
        self._neutron = neutron_client.NeutronAPIClient()
        self._neutron._client = mock.MagicMock()

    def test_get_network_subnets(self):
        self._neutron._client.show_network.return_value = {
            'network': {
                'subnets': [self._FAKE_SUBNET_ID]
            }
        }

        subnets = self._neutron.get_network_subnets(self._FAKE_NETWORK_ID)
        self.assertEqual([self._FAKE_SUBNET_ID], subnets)

    def test_get_network_subnet_cidr(self):
        self._neutron._client.show_subnet.return_value = {
            'subnet': {
                'cidr': self._FAKE_CIDR
            }
        }

        cidr = self._neutron.get_network_subnet_cidr(self._FAKE_SUBNET_ID)
        self.assertEqual(self._FAKE_CIDR, cidr)

    def test_get_port_ip_address(self):
        self._neutron._client.show_port.return_value = {
            'port': {
                'fixed_ips': [{'ip_address': self._FAKE_IP_ADDR}]
            }
        }

        ip_addr = self._neutron.get_port_ip_address(self._FAKE_PORT_ID)
        self.assertEqual(self._FAKE_IP_ADDR, ip_addr)
