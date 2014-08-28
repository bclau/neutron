# Copyright 2014 Cloudbase Solutions SRL
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
# @author: Claudiu Belu, Cloudbase Solutions Srl

"""
Unit tests for the Hyper-V Security Groups Driver.
"""

import mock
from oslo.config import cfg

from neutron.plugins.hyperv.agent import security_groups_driver as sg_driver0
from neutron.plugins.hyperv.agent import security_groups_driver2 as sg_driver
from neutron.plugins.hyperv.agent import utilsfactory
from neutron.tests import base

CONF = cfg.CONF


class TestHyperVSecurityGroupsDriver(base.BaseTestCase):

    _FAKE_DEVICE = 'fake_device'
    _FAKE_ID = 'fake_id'
    _FAKE_DIRECTION = 'ingress'
    _FAKE_ETHERTYPE = 'IPv4'
    _FAKE_ETHERTYPE_IPV6 = 'IPv6'
    _FAKE_DEST_IP_PREFIX = 'fake_dest_ip_prefix'
    _FAKE_SOURCE_IP_PREFIX = 'fake_source_ip_prefix'
    _FAKE_PARAM_NAME = 'fake_param_name'
    _FAKE_PARAM_VALUE = 'fake_param_value'

    _FAKE_PORT_MIN = 9001
    _FAKE_PORT_MAX = 9011

    def setUp(self):
        super(TestHyperVSecurityGroupsDriver, self).setUp()
        self._mock_windows_version = mock.patch.object(utilsfactory,
                                                       'get_hypervutils')
        self._mock_windows_version.start()
        self._driver = sg_driver0.HyperVSecurityGroupsDriver()
        self._driver._utils = mock.MagicMock()

    @mock.patch('neutron.plugins.hyperv.agent.security_groups_driver'
                '.HyperVSecurityGroupsDriver._create_port_rules')
    def test_prepare_port_filter(self, mock_create_rules):
        mock_port = self._get_port()
        mock_utils_method = self._driver._utils.create_default_reject_all_rules
        self._driver.prepare_port_filter(mock_port)

        self.assertEqual(mock_port,
                         self._driver._security_ports[self._FAKE_DEVICE])
        mock_utils_method.assert_called_once_with(self._FAKE_ID)
        self._driver._create_port_rules.assert_called_once_with(
            self._FAKE_ID, mock_port['security_group_rules'])

    def test_update_port_filter(self):
        mock_port = self._get_port()
        new_mock_port = self._get_port()
        new_mock_port['id'] += '2'
        new_mock_port['security_group_rules'][0]['ethertype'] += "2"

        self._driver._security_ports[mock_port['device']] = mock_port
        self._driver._create_port_rules = mock.MagicMock()
        self._driver._remove_port_rules = mock.MagicMock()
        self._driver.update_port_filter(new_mock_port)

        self._driver._remove_port_rules.assert_called_once_with(
            mock_port['id'], mock_port['security_group_rules'])
        self._driver._create_port_rules.assert_called_once_with(
            new_mock_port['id'], new_mock_port['security_group_rules'])
        self.assertEqual(new_mock_port,
                         self._driver._security_ports[new_mock_port['device']])

    @mock.patch('neutron.plugins.hyperv.agent.security_groups_driver'
                '.HyperVSecurityGroupsDriver.prepare_port_filter')
    def test_update_port_filter_new_port(self, mock_method):
        mock_port = self._get_port()
        self._driver.prepare_port_filter = mock.MagicMock()
        self._driver.update_port_filter(mock_port)

        self._driver.prepare_port_filter.assert_called_once_with(mock_port)

    def test_remove_port_filter(self):
        mock_port = self._get_port()
        self._driver._security_ports[mock_port['device']] = mock_port
        self._driver.remove_port_filter(mock_port)
        self.assertFalse(mock_port['device'] in self._driver._security_ports)

    def test_create_port_rules_exception(self):
        fake_rule = self._create_security_rule()
        self._driver._utils.create_security_rule.side_effect = Exception(
            'Generated Exception for testing.')
        self._driver._create_port_rules(self._FAKE_ID, [fake_rule])

    def test_create_param_map(self):
        fake_rule = self._create_security_rule()
        self._driver._get_rule_remote_address = mock.MagicMock(
            return_value=self._FAKE_SOURCE_IP_PREFIX)
        actual = self._driver._create_param_map(fake_rule)
        expected = {
            'direction': self._driver._ACL_PROP_MAP[
                'direction'][self._FAKE_DIRECTION],
            'acl_type': self._driver._ACL_PROP_MAP[
                'ethertype'][self._FAKE_ETHERTYPE],
            'local_port': '%s-%s' % (self._FAKE_PORT_MIN, self._FAKE_PORT_MAX),
            'protocol': self._driver._ACL_PROP_MAP['default'],
            'remote_address': self._FAKE_SOURCE_IP_PREFIX
        }

        self.assertEqual(expected, actual)

    @mock.patch('neutron.plugins.hyperv.agent.security_groups_driver'
                '.HyperVSecurityGroupsDriver._create_param_map')
    def test_create_port_rules(self, mock_method):
        fake_rule = self._create_security_rule()
        mock_method.return_value = {
            self._FAKE_PARAM_NAME: self._FAKE_PARAM_VALUE}
        self._driver._create_port_rules(self._FAKE_ID, [fake_rule])

        self._driver._utils.create_security_rule.assert_called_once_with(
            self._FAKE_ID, fake_param_name=self._FAKE_PARAM_VALUE)

    def test_convert_any_address_to_same_ingress(self):
        rule = self._create_security_rule()
        actual = self._driver._get_rule_remote_address(rule)
        self.assertEqual(self._FAKE_SOURCE_IP_PREFIX, actual)

    def test_convert_any_address_to_same_egress(self):
        rule = self._create_security_rule()
        rule['direction'] += '2'
        actual = self._driver._get_rule_remote_address(rule)
        self.assertEqual(self._FAKE_DEST_IP_PREFIX, actual)

    def test_convert_any_address_to_ipv4(self):
        rule = self._create_security_rule()
        del rule['source_ip_prefix']
        actual = self._driver._get_rule_remote_address(rule)
        self.assertEqual(self._driver._ACL_PROP_MAP['address_default']['IPv4'],
                         actual)

    def test_convert_any_address_to_ipv6(self):
        rule = self._create_security_rule()
        del rule['source_ip_prefix']
        rule['ethertype'] = self._FAKE_ETHERTYPE_IPV6
        actual = self._driver._get_rule_remote_address(rule)
        self.assertEqual(self._driver._ACL_PROP_MAP['address_default']['IPv6'],
                         actual)

    def test_get_rule_protocol_icmp(self):
        self._test_get_rule_protocol(
            'icmp', self._driver._ACL_PROP_MAP['protocol']['icmp'])

    def test_get_rule_protocol_no_icmp(self):
        self._test_get_rule_protocol('tcp', 'tcp')

    def _test_get_rule_protocol(self, protocol, expected):
        rule = self._create_security_rule()
        rule['protocol'] = protocol
        actual = self._driver._get_rule_protocol(rule)

        self.assertEqual(expected, actual)

    def _get_port(self):
        return {
            'device': self._FAKE_DEVICE,
            'id': self._FAKE_ID,
            'security_group_rules': [self._create_security_rule()]
        }

    def _create_security_rule(self):
        return {
            'direction': self._FAKE_DIRECTION,
            'ethertype': self._FAKE_ETHERTYPE,
            'dest_ip_prefix': self._FAKE_DEST_IP_PREFIX,
            'source_ip_prefix': self._FAKE_SOURCE_IP_PREFIX,
            'port_range_min': self._FAKE_PORT_MIN,
            'port_range_max': self._FAKE_PORT_MAX
        }


class SecurityGroupRulesTestCase(base.BaseTestCase):
    _FAKE_DEVICE = 'fake_device'
    _FAKE_ID = 'fake_id'
    _FAKE_DIRECTION = 'ingress'
    _FAKE_ETHERTYPE = 'IPv4'
    _FAKE_ETHERTYPE_IPV6 = 'IPv6'
    _FAKE_PROTOCOL = 'tcp'
    _FAKE_ACTION = sg_driver._ACL_PROP_MAP['action']['allow']
    _FAKE_DEST_IP_PREFIX = 'fake_dest_ip_prefix'
    _FAKE_SOURCE_IP_PREFIX = 'fake_source_ip_prefix'
    _FAKE_PARAM_NAME = 'fake_param_name'
    _FAKE_PARAM_VALUE = 'fake_param_value'

    _FAKE_PORT_MIN = 9001
    _FAKE_PORT_MAX = 9011

    def setUp(self):
        super(SecurityGroupRulesTestCase, self).setUp()

        self.sg_gen = sg_driver.SecurityGroupRuleGenerator()

    def test_create_security_group_rule(self):
        expected = [self._create_sg_rule()]
        rule = self._create_security_rule()

        actual = self.sg_gen.create_security_group_rule(rule)
        self.assertEqual(expected, actual)

    def test_create_security_group_rules(self):
        expected = [self._create_sg_rule()] * 2
        rules = [self._create_security_rule()] * 2

        actual = self.sg_gen.create_security_group_rules(rules)
        self.assertEqual(expected, actual)

    def test_create_security_group_rule_any(self):
        sg_rule1 = self._create_sg_rule(self._acl('protocol', 'tcp'))
        sg_rule2 = self._create_sg_rule(self._acl('protocol', 'udp'))
        sg_rule3 = self._create_sg_rule(self._acl('protocol', 'icmp'))

        rule = self._create_security_rule()
        rule['protocol'] = sg_driver._ACL_PROP_MAP["default"]

        actual = self.sg_gen.create_security_group_rule(rule)
        self.assertEqual(sorted([sg_rule1, sg_rule2, sg_rule3]),
                         sorted(actual))

    def test_sg_rule_to_dict(self):
        expected = {'Direction': self._acl('direction', self._FAKE_DIRECTION),
                    'Action': self._FAKE_ACTION,
                    'Protocol': self._FAKE_PROTOCOL,
                    'LocalPort': '%s-%s' % (self._FAKE_PORT_MIN,
                                            self._FAKE_PORT_MAX),
                    'RemoteIPAddress': self._FAKE_DEST_IP_PREFIX,
                    'Stateful': True,
                    'IdleSessionTimeout': 0
        }

        sg_rule = self._create_sg_rule()
        self.assertEqual(expected, sg_rule.to_dict())

    def test_stateful_icmp(self):
        sg_rule = self._create_sg_rule(self._acl('protocol', 'icmp'))
        self.assertFalse(sg_rule.Stateful)

    def test_stateful_deny(self):
        sg_rule = self._create_sg_rule(action=self._acl('action', 'deny'))
        self.assertFalse(sg_rule.Stateful)

    def test_stateful_true(self):
        sg_rule = self._create_sg_rule()
        self.assertTrue(sg_rule.Stateful)

    def test_rule_uniqueness(self):
        sg_rule = self._create_sg_rule()
        sg_rule2 = self._create_sg_rule(self._acl('protocol', 'icmp'))

        self.assertEqual([sg_rule], list(set([sg_rule] * 2)))
        self.assertEqual(sorted([sg_rule, sg_rule2]),
                         sorted(list(set([sg_rule, sg_rule2]))))

    def _create_security_rule(self):
        return {
            'direction': self._FAKE_DIRECTION,
            'ethertype': self._FAKE_ETHERTYPE,
            'protocol': self._FAKE_PROTOCOL,
            'dest_ip_prefix': self._FAKE_DEST_IP_PREFIX,
            'source_ip_prefix': self._FAKE_DEST_IP_PREFIX,
            'port_range_min': self._FAKE_PORT_MIN,
            'port_range_max': self._FAKE_PORT_MAX
        }

    def _create_sg_rule(self, protocol=None, action=None):
        protocol = protocol or self._FAKE_PROTOCOL
        action = action or self._FAKE_ACTION
        return sg_driver.SecurityGroupRule(
            self._acl('direction', self._FAKE_DIRECTION),
            '%s-%s' % (self._FAKE_PORT_MIN, self._FAKE_PORT_MAX),
            protocol,
            self._FAKE_DEST_IP_PREFIX,
            action)

    @classmethod
    def _acl(self, key1, key2):
        return sg_driver._ACL_PROP_MAP[key1][key2]


