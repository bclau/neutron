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

import platform

from neutron.agent import rpc as agent_rpc
from neutron.common import topics
from neutron import context
from neutron.openstack.common import log as logging
from neutron.plugins.hyperv import agent_notifier_api
from neutron.plugins.hyperv import db as hyperv_db
from neutron.plugins.hyperv import neutron_client
from neutron.plugins.hyperv.agent import utilsfactory

from neutron.plugins.hyperv.common import constants


LOG = logging.getLogger(__name__)


class HyperVNvgreAgent(object):
    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'

    def __init__(self,  physical_networks):
        self.agent_id = 'hyperv_%s' % platform.node()
        self.topic = topics.AGENT

        self._utils = utilsfactory.get_hypervutils()
        self._nvgre_utils = utilsfactory.get_hyperv_nvgre_utils()
        self._n_client = neutron_client.NeutronAPIClient()
        self._db = hyperv_db.HyperVPluginDB()
        self._db.initialize()

        self._vswitch_ips = {}
        self._tunneling_agents = {}
        self._gre_ports = []
        self._network_vsids = {}

        self._setup_rpc()
        self._init_nvgre(physical_networks)

    def _setup_rpc(self):
        # RPC network init
        self._context = context.get_admin_context_without_session()
        # Handle updates from service
        # Define the listening consumers for the agent
        consumers = [[constants.LOOKUP, topics.UPDATE]]

        self._notifier = agent_notifier_api.AgentNotifierApi(self.topic)

    def _init_nvgre(self, physical_networks):
        self._nvgre_utils.multi_enable_wnv(physical_networks)
        for network in physical_networks:
            LOG.info("Adding provider route and address for metwork: %s",
                     network)
            self._nvgre_utils.create_provider_route(network)
            self._nvgre_utils.create_provider_address(network)
            ip_addr, length = self._nvgre_utils.get_network_iface_ip(network)
            self._vswitch_ips[network] = ip_addr

        for lookup in self._db.get_lookup_records():
            self._nvgre_utils.create_lookup_record(lookup['provider_addr'],
                                                   lookup['customer_addr'],
                                                   lookup['mac_address'],
                                                   lookup['vsid'])

    def get_tunneling_ip(self):
        return self._vswitch_ips.values()[0]

    def _refresh_tunneling_agents(self):
        self._tunneling_agents.update(self._n_client.get_tunneling_agents())

    def lookup_update(self, rpc_context, **kwargs):
        lookup_ip = kwargs.get('lookup_ip')
        lookup_details = kwargs.get('lookup_details')

        LOG.info(_("Lookup Received: %s, %s"), lookup_ip, lookup_details)
        if not lookup_ip or not lookup_details:
            return

        self._register_lookup_record(lookup_ip,
                                     lookup_details['customer_addr'],
                                     lookup_details['mac_address'],
                                     lookup_details['customer_vsid'])

    def _register_lookup_record(self, prov_addr, cust_addr, mac_address, vsid):
        LOG.info(_('Creating LookupRecord: VSID: %(vsid)s MAC: %(mac_address)s'
                   ' Customer IP: %(cust_addr)s Provider IP: %(prov_addr)s'),
                 dict(vsid=vsid,
                      mac_address=mac_address,
                      cust_addr=cust_addr,
                      prov_addr=prov_addr))

        self._nvgre_utils.create_lookup_record(
            prov_addr, cust_addr, mac_address, vsid)

        self._db.add_lookup_record(prov_addr, cust_addr, mac_address, vsid)

    def bind_gre_port(self, segmentation_id, network_name, port_id):
        mac_address = self._utils.get_vnic_mac_address(port_id)
        provider_addr = self._nvgre_utils.get_network_iface_ip(network_name)[0]
        customer_addr = self._n_client.get_port_ip_address(port_id)

        if not provider_addr or not customer_addr:
            return

        LOG.info(_('Binding VirtualSubnetID %(segmentation_id)s '
                   'to switch port %(port_id)s'),
                 dict(segmentation_id=segmentation_id, port_id=port_id))
        self._utils.set_vswitch_port_vsid(segmentation_id, port_id)

        # normal lookup record.
        self._register_lookup_record(
            provider_addr, customer_addr, mac_address, segmentation_id)

        # lookup record for dhcp requests.
        self._register_lookup_record(
          self._vswitch_ips[network_name], constants.IPV4_DEFAULT,
          mac_address, segmentation_id)

        LOG.info('Fanning out LookupRecord...')
        #self._notifier.lookup_update(self._context,
        #                             provider_addr,
        #                             {'customer_addr': customer_addr,
        #                              'mac_address': mac_address,
        #                              'customer_vsid': segmentation_id})

    def bind_gre_network(self, net_uuid, vswitch_name, segmentation_id):
        for subnet in self._n_client.get_network_subnets(net_uuid):
            cidr = self._n_client.get_network_subnet_cidr(subnet)
            try:
                self._nvgre_utils.create_customer_route(
                    segmentation_id, vswitch_name, cidr)
            except Exception as ex:
                LOG.error("Exception caught: %s", ex)

        self._network_vsids[net_uuid] = segmentation_id
        self.refresh_gre_records(network_id=net_uuid)
        self._notifier.tunnel_update(
            self._context, self.get_tunneling_ip(), self.get_tunneling_ip())

    def refresh_gre_records(self, **kwargs):
        self._refresh_tunneling_agents()
        ports = self._n_client.get_network_ports(**kwargs)

        # process ports that were not processed yet.
        # process ports that are bound tu tunneling_agents.
        ports = [p for p in ports if p['id'] not in self._gre_ports and
                 p['binding:host_id'] in self._tunneling_agents and
                 p['network_id'] in self._network_vsids.keys()]

        for port in ports:
            tunneling_ip = self._tunneling_agents[port['binding:host_id']]
            customer_addr = port['fixed_ips'][0]['ip_address']
            mac_addr = port['mac_address'].replace(':', '')
            segmentation_id = self._network_vsids[port['network_id']]
            try:
                self._register_lookup_record(
                    tunneling_ip, customer_addr, mac_addr, segmentation_id)

                self._gre_ports.append(port['id'])
            except Exception as ex:
                LOG.error("Exception while adding lookup_record: %(ex)s. VSID:"
                          "%(vsid)s MAC: %(mac_address)s Customer IP: "
                          "%(cust_addr)s Provider IP: %(prov_addr)s" %
                          dict(ex=ex,
                               vsid=segmentation_id,
                               mac_address=mac_addr,
                               cust_addr=customer_addr,
                               prov_addr=tunneling_ip))
