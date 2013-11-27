# vim: tabstop=4 shiftwidth=4 softtabstop=4

#Copyright 2013 Cloudbase Solutions SRL
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
# @author: Claudiu Belu, Cloudbase Solutions Srl

from neutronclient.v2_0 import client as clientv20
from neutron.openstack.common import log as logging
from oslo.config import cfg


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

neutron_opts = [
    cfg.StrOpt('neutron_url',
               default='http://127.0.0.1:9696',
               help='URL for connecting to neutron'),
    cfg.IntOpt('neutron_url_timeout',
               default=30,
               help='timeout value for connecting to neutron in seconds'),
    cfg.StrOpt('neutron_admin_username',
               help='username for connecting to neutron in admin context'),
    cfg.StrOpt('neutron_admin_password',
               help='password for connecting to neutron in admin context',
               secret=True),
    cfg.StrOpt('neutron_admin_tenant_name',
               help='tenant name for connecting to neutron in admin context'),
    cfg.StrOpt('neutron_admin_auth_url',
               default='http://localhost:5000/v2.0',
               help='auth url for connecting to neutron in admin context'),
    cfg.StrOpt('neutron_auth_strategy',
               default='keystone',
               help='auth strategy for connecting to '
                    'neutron in admin context')
    ]

CONF.register_opts(neutron_opts)


class NeutronAPIClient(object):

    def __init__(self):
        self._init_client()

    def _init_client(self, token=None):
        params = {
            'endpoint_url': CONF.neutron_url,
            'timeout': CONF.neutron_url_timeout,
            'insecure': True,
            'ca_cert': None,
        }

        if token:
            params['token'] = token
            params['auth_strategy'] = None
        else:
            params['username'] = CONF.neutron_admin_username
            params['tenant_name'] = CONF.neutron_admin_tenant_name
            params['password'] = CONF.neutron_admin_password
            params['auth_url'] = CONF.neutron_admin_auth_url
            params['auth_strategy'] = CONF.neutron_auth_strategy

        self._client = clientv20.Client(**params)

    def get_network_subnets(self, network_id):
        try:
            net = self._client.show_network(network_id)
            return net['network']['subnets']
        except:
            LOG.error(_("Could not retrieve network %s"), network_id)

        return []

    def get_network_subnet_cidr(self, subnet_id):
        try:
            subnet = self._client.show_subnet(subnet_id)
            return str(subnet['subnet']['cidr'])
        except:
            LOG.error(_("Could not retrieve subnet %s"), subnet_id)

        return None

    def get_port_ip_address(self, port_id):
        try:
            port = self._client.show_port(port_id)
            fixed_ips = port['port']['fixed_ips'][0]
            return fixed_ips['ip_address']
        except:
            LOG.error(_("Could not retrieve port %s"), port_id)

        return None
