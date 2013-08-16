# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Cloudbase Solutions SRL
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
Unit tests for Hyper-V utils factory.
"""

import mock
from oslo.config import cfg

from mock import MagicMock

from neutron.plugins.hyperv.agent import utils
from neutron.plugins.hyperv.agent import utilsv2
from neutron.plugins.hyperv.agent import utilsfactory
from neutron.tests import base

CONF = cfg.CONF


class TestHyperVUtilsFactory(base.BaseTestCase):

    def setUp(self):
        super(TestHyperVUtilsFactory, self).setUp()
        self.addCleanup(cfg.CONF.reset)
        self._factory = utilsfactory

    def test_get_hypervutils_v2(self):
        self._test_returned_class(utilsv2.HyperVUtilsV2, False, '6.2.0')

    def test_get_hypervutils_v1_old_version(self):
        self._test_returned_class(utils.HyperVUtils, False, '5.0.0')

    def test_get_hypervutils_v1_forced(self):
        self._test_returned_class(utils.HyperVUtils, True, '6.2.0')

    def _test_returned_class(self, expected_class, force_v1, os_version):
        CONF.hyperv.force_hyperv_utils_v1 = force_v1
        self._factory._get_windows_version = MagicMock(return_value=os_version)
        actual_class = type(self._factory.get_hypervutils())
        assert actual_class is expected_class
