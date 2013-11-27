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
Unit tests for the Hyper-V NVGRE support.
"""

import mock

from neutron.plugins.hyperv.agent import utils_nvgre
from neutron.tests import base


class TestHyperVNvgreUtils(base.BaseTestCase):
    _FAKE_NETWORK_IFACE_GATEWAY = 'fake_gateway'
    _FAKE_PREFIX_LENGTH = 24
    _FAKE_NETWORK_IFACE_INDEX = 1
    _FAKE_DRIVER_DESCRIPTION = 'fake_driver_description'
    _FAKE_NETWORK_NAME = 'fake_network_name'
    _INEXISTENT_NETWORK_NAME = 'inexistent_network_name'

    _FAKE_PROVIDER_ADDR = 'fake_provider_address'
    _FAKE_CUSTOMER_ADDR = 'fake_customer_address'
    _FAKE_MAC_ADDRESS = 'fake_mac_address'
    _FAKE_VSID = 9001
    _FAKE_DEST_PREFIX = 'fake_dest_prefix'

    def setUp(self):
        super(TestHyperVNvgreUtils, self).setUp()
        self._utils = utils_nvgre.Nvgre()
        self._utils._scimv2 = mock.MagicMock()

    def test_multi_enable_wnv_true(self):
        self._test_multi_enable_wnv([self._FAKE_NETWORK_NAME], True)

    def test_multi_enable_wnv_false(self):
        self._test_multi_enable_wnv([self._INEXISTENT_NETWORK_NAME], False)

    def _test_multi_enable_wnv(self, network_names, expected):
        binding = self._create_mock_binding()
        self._utils.multi_enable_wnv(network_names)
        self.assertEqual(expected, binding.Enable.called)

    def test_enable_wnv(self):
        binding = self._create_mock_binding()
        self._utils.enable_wnv(self._FAKE_NETWORK_NAME)
        self.assertTrue(binding.Enable.called)

    def _create_mock_binding(self):
        binding = mock.MagicMock()
        binding.BindName = self._utils._WNV_BIND_NAME
        binding.Name = self._FAKE_NETWORK_NAME

        net_binds = self._utils._scimv2.MSFT_NetAdapterBindingSettingData
        net_binds.return_value = [binding]
        return binding

    def test_create_provider_address(self):
        self._utils._get_network_iface_index = mock.MagicMock(
            return_value=self._FAKE_NETWORK_IFACE_INDEX)
        self._utils.get_network_iface_ip = mock.MagicMock(
            return_value=(self._FAKE_PROVIDER_ADDR, self._FAKE_PREFIX_LENGTH))

        self._utils.create_provider_address(self._FAKE_NETWORK_NAME)

        scimv2 = self._utils._scimv2
        obj_class = scimv2.MSFT_NetVirtualizationProviderAddressSettingData
        obj_class.new.assert_called_once_with(
            ProviderAddress=self._FAKE_PROVIDER_ADDR,
            InterfaceIndex=self._FAKE_NETWORK_IFACE_INDEX,
            PrefixLength=self._FAKE_PREFIX_LENGTH)

    def test_create_provider_route(self):
        self._utils._get_network_iface_index = mock.MagicMock(
            return_value=self._FAKE_NETWORK_IFACE_INDEX)
        self._utils._get_network_iface_gateway = mock.MagicMock(
            return_value=self._FAKE_NETWORK_IFACE_GATEWAY)

        self._utils._scimv2.MSFT_NetVirtualizationProviderRouteSettingData = \
            mock.MagicMock(return_value=[])

        self._utils.create_provider_route(self._FAKE_NETWORK_NAME)

        conn_scimv2 = self._utils._scimv2
        obj_class = conn_scimv2.MSFT_NetVirtualizationProviderRouteSettingData
        obj_class.new.assert_called_once_with(
            InterfaceIndex=self._FAKE_NETWORK_IFACE_INDEX,
            DestinationPrefix='0.0.0.0/0',
            NextHop=self._FAKE_NETWORK_IFACE_GATEWAY)

    def test_create_customer_route(self):
        self._utils.create_customer_route(
            self._FAKE_VSID, self._FAKE_NETWORK_NAME, self._FAKE_DEST_PREFIX)

        conn_scimv2 = self._utils._scimv2
        obj_class = conn_scimv2.MSFT_NetVirtualizationCustomerRouteSettingData
        self.assertTrue(obj_class.new.called)

    def test_create_lookup_record(self):
        conn_scimv2 = self._utils._scimv2
        obj_class = conn_scimv2.MSFT_NetVirtualizationLookupRecordSettingData
        lookup = mock.MagicMock()
        obj_class.return_value = [lookup]

        self._utils.create_lookup_record(self._FAKE_PROVIDER_ADDR,
                                         self._FAKE_CUSTOMER_ADDR,
                                         self._FAKE_MAC_ADDRESS,
                                         self._FAKE_VSID)

        self.assertTrue(lookup.Delete_.called)
        obj_class.new.assert_called_once_with(
            VirtualSubnetID=self._FAKE_VSID,
            Rule=self._utils._TRANSLATE_ENCAP,
            MACAddress=self._FAKE_MAC_ADDRESS,
            CustomerAddress=self._FAKE_CUSTOMER_ADDR,
            ProviderAddress=self._FAKE_PROVIDER_ADDR)

    def test_get_network_iface_index(self):
        fake_network = mock.MagicMock()
        fake_network.InterfaceIndex = self._FAKE_NETWORK_IFACE_INDEX
        fake_network.DriverDescription = self._FAKE_DRIVER_DESCRIPTION

        self._utils._get_network_ifaces_by_name = mock.MagicMock(
            return_value=[fake_network])

        index = self._utils._get_network_iface_index(self._FAKE_NETWORK_NAME)
        self.assertEqual(self._FAKE_NETWORK_IFACE_INDEX, index)

    def test_get_network_iface_ip(self):
        fake_network = mock.MagicMock()
        fake_network.InterfaceIndex = self._FAKE_NETWORK_IFACE_INDEX
        fake_network.DriverDescription = self._utils._HYPERV_VIRT_ADAPTER

        fake_netip = mock.MagicMock()
        fake_netip.IPAddress = self._FAKE_PROVIDER_ADDR
        fake_netip.PrefixLength = self._FAKE_PREFIX_LENGTH

        self._utils._get_network_ifaces_by_name = mock.MagicMock(
            return_value=[fake_network])

        self._utils._scimv2.MSFT_NetIPAddress.return_value = [fake_netip]

        pair = self._utils.get_network_iface_ip(self._FAKE_NETWORK_NAME)
        self.assertEqual(
            (self._FAKE_PROVIDER_ADDR, self._FAKE_PREFIX_LENGTH), pair)

    def test_get_network_iface_gateway(self):
        fake_network = mock.MagicMock()
        fake_network.InterfaceIndex = self._FAKE_NETWORK_IFACE_INDEX
        fake_network.DriverDescription = self._utils._HYPERV_VIRT_ADAPTER

        fake_route = mock.MagicMock()
        fake_route.NextHop = self._FAKE_NETWORK_IFACE_GATEWAY

        self._utils._get_network_ifaces_by_name = mock.MagicMock(
            return_value=[fake_network])

        self._utils._scimv2.MSFT_NetRoute.return_value = [fake_route]

        gway = self._utils._get_network_iface_gateway(self._FAKE_NETWORK_NAME)
        self.assertEqual(self._FAKE_NETWORK_IFACE_GATEWAY, gway)
