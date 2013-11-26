# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (C) 2012 Midokura Japan K.K.
# Copyright (C) 2013 Midokura PTE LTD
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
#
# @author: Rossella Sblendido, Midokura Japan KK

import mock
from oslo.config import cfg
import sys
sys.modules["midonetclient"] = mock.Mock()

from neutron.agent.common import config
from neutron.agent.linux import dhcp
from neutron.agent.linux import interface
from neutron.agent.linux import ip_lib
from neutron.common import config as base_config
from neutron.openstack.common import uuidutils
import neutron.plugins.midonet.agent.midonet_driver as driver
from neutron.tests import base


class MidoInterfaceDriverTestCase(base.BaseTestCase):
    def setUp(self):
        self.conf = config.setup_conf()
        self.conf.register_opts(interface.OPTS)
        config.register_root_helper(self.conf)
        self.ip_dev_p = mock.patch.object(ip_lib, 'IPDevice')
        self.ip_dev = self.ip_dev_p.start()
        self.ip_p = mock.patch.object(ip_lib, 'IPWrapper')
        self.ip = self.ip_p.start()
        self.device_exists_p = mock.patch.object(ip_lib, 'device_exists')
        self.device_exists = self.device_exists_p.start()
        self.device_exists.return_value = False
        self.addCleanup(mock.patch.stopall)
        midonet_opts = [
            cfg.StrOpt('midonet_uri',
                       default='http://localhost:8080/midonet-api',
                       help=_('MidoNet API server URI.')),
            cfg.StrOpt('username', default='admin',
                       help=_('MidoNet admin username.')),
            cfg.StrOpt('password', default='passw0rd',
                       secret=True,
                       help=_('MidoNet admin password.')),
            cfg.StrOpt('project_id',
                       default='77777777-7777-7777-7777-777777777777',
                       help=_('ID of the project that MidoNet admin user'
                              'belongs to.'))
        ]
        self.conf.register_opts(midonet_opts, "MIDONET")
        self.driver = driver.MidonetInterfaceDriver(self.conf)
        self.root_dev = mock.Mock()
        self.ns_dev = mock.Mock()
        self.ip().add_veth = mock.Mock(return_value=(
            self.root_dev, self.ns_dev))
        self.driver._get_host_uuid = mock.Mock(
            return_value=uuidutils.generate_uuid())
        self.network_id = uuidutils.generate_uuid()
        self.port_id = uuidutils.generate_uuid()
        self.device_name = "tap0"
        self.mac_address = "aa:bb:cc:dd:ee:ff"
        self.bridge = "br-test"
        self.namespace = "ns-test"
        super(MidoInterfaceDriverTestCase, self).setUp()

    def test_plug(self):
        self.driver.plug(
            self.network_id, self.port_id,
            self.device_name, self.mac_address,
            self.bridge, self.namespace)

        expected = [mock.call(), mock.call('sudo'),
                    mock.call().add_veth(self.device_name,
                                         self.device_name,
                                         namespace2=self.namespace),
                    mock.call().ensure_namespace(self.namespace),
                    mock.call().ensure_namespace().add_device_to_namespace(
                        mock.ANY)]
        self.ns_dev.assert_has_calls(
            [mock.call.link.set_address(self.mac_address)])

        self.root_dev.assert_has_calls([mock.call.link.set_up()])
        self.ns_dev.assert_has_calls([mock.call.link.set_up()])
        self.ip.assert_has_calls(expected, True)

    def test_unplug(self):
        self.driver.unplug(self.device_name, self.bridge, self.namespace)

        self.ip_dev.assert_has_calls([
            mock.call(self.device_name, self.driver.root_helper,
                      self.namespace),
            mock.call().link.delete()])
        self.ip.assert_has_calls(mock.call().garbage_collect_namespace())


class FakeNetwork:
    id = 'aaaabbbb-cccc-dddd-eeee-ffff00001111'
    namespace = 'qdhcp-ns'


class TestDhcpNoOpDriver(base.BaseTestCase):
    def setUp(self):
        super(TestDhcpNoOpDriver, self).setUp()
        self.conf = config.setup_conf()
        self.conf.register_opts(base_config.core_opts)
        self.conf.register_opts(dhcp.OPTS)
        self.conf.enable_isolated_metadata = True
        self.conf.use_namespaces = True
        instance = mock.patch("neutron.agent.linux.dhcp.DeviceManager")
        self.mock_mgr = instance.start()
        self.addCleanup(instance.stop)

    def test_disable_no_retain_port(self):
        dhcp_driver = driver.DhcpNoOpDriver(self.conf, FakeNetwork())
        dhcp_driver.disable(retain_port=False)
        self.assertTrue(self.mock_mgr.return_value.destroy.called)

    def test_disable_retain_port(self):
        dhcp_driver = driver.DhcpNoOpDriver(self.conf, FakeNetwork())
        dhcp_driver.disable(retain_port=True)
        self.assertFalse(self.mock_mgr.return_value.destroy.called)
