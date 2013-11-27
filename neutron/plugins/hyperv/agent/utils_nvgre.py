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

import uuid
import wmi

from neutron.openstack.common import log as logging
from neutron.plugins.hyperv.common import constants

from neutron.plugins.hyperv.agent import utilsfactory

LOG = logging.getLogger(__name__)


class Nvgre(object):
    _HYPERV_VIRT_ADAPTER = 'Hyper-V Virtual Ethernet Adapter'
    _IPV4_ADDRESS_FAMILY = 2

    _WNV_BIND_NAME = 'Wnv'
    _TRANSLATE_NAT = 0
    _TRANSLATE_ENCAP = 1

    _LOOKUP_RECORD_TYPE_STATIC = 0
    _LOOKUP_RECORD_TYPE_L2_ONLY = 3

    _STDCIMV2_NAMESPACE = '//./root/StandardCimv2'

    def __init__(self):
        super(Nvgre, self).__init__()
        self._scimv2 = wmi.WMI(moniker=self._STDCIMV2_NAMESPACE)
        self._utils = utilsfactory.get_hypervutils()
        self._net_if_indexes = {}

    def multi_enable_wnv(self, network_names):
        all_bindings = self._scimv2.MSFT_NetAdapterBindingSettingData(
            BindName=self._WNV_BIND_NAME)

        bindings = [r for r in all_bindings if r.Name in network_names]

        if len(bindings) is not len(network_names):
            found_netw_names = [r.Name for r in bindings]
            not_found_netw_names = [n for n in network_names if
                                    n not in found_netw_names]

            LOG.warning(_("Didn't find Bindings for "
                          "networks: %s"), not_found_netw_names)

        for binding in bindings:
            binding.Enable()

    def enable_wnv(self, network_name):
        bindings = self._scimv2.MSFT_NetAdapterBindingSettingData(
            BindName=self._WNV_BIND_NAME, Name=network_name)

        if bindings:
            bindings[0].Enable()
        else:
            LOG.warning(_("Didn't find Bindings for "
                          "network: %s"), network_name)

    def create_provider_address(self, network_name):
        iface_index = self._get_network_iface_index(network_name)
        (provider_addr, prefix_len) = self.get_network_iface_ip(network_name)

        if iface_index is None or provider_addr is None:
            return None

        return self._create_new_object(
            self._scimv2.MSFT_NetVirtualizationProviderAddressSettingData,
            ProviderAddress=provider_addr,
            InterfaceIndex=iface_index,
            PrefixLength=prefix_len)

    def create_provider_route(self, network_name):
        iface_index = self._get_network_iface_index(network_name)
        next_hop = constants.IPV4_DEFAULT

        if iface_index is None or next_hop is None:
            return None

        routes = self._scimv2.MSFT_NetVirtualizationProviderRouteSettingData(
            InterfaceIndex=iface_index, NextHop=next_hop)

        if routes:
            return routes[0]

        return self._create_new_object(
            self._scimv2.MSFT_NetVirtualizationProviderRouteSettingData,
            InterfaceIndex=iface_index,
            DestinationPrefix=constants.IPV4_DEFAULT_DESTINATION,
            NextHop=next_hop)

    def create_customer_route(self, vsid, network_name, dest_prefix):
        cust_route_string = network_name + dest_prefix + str(vsid)
        rdid_uuid = uuid.uuid5(uuid.NAMESPACE_X500, cust_route_string)

        routes = self._scimv2.MSFT_NetVirtualizationCustomerRouteSettingData(
            VirtualSubnetID=vsid)

        if routes:
            return routes[0]

        return self._create_new_object(
            self._scimv2.MSFT_NetVirtualizationCustomerRouteSettingData,
            VirtualSubnetID=vsid,
            DestinationPrefix=dest_prefix,
            NextHop=constants.IPV4_DEFAULT,
            Metric=255,
            RoutingDomainID='{%s}' % str(rdid_uuid))

    def create_lookup_record(self, provider_addr, customer_addr, mac, vsid):
        # check for existing entry.
        if constants.IPV4_DEFAULT == customer_addr:
            # customer address used for DHCP requests.
            lrec = self._scimv2.MSFT_NetVirtualizationLookupRecordSettingData(
                CustomerAddress=customer_addr, MACAddress=mac)
            record_type = self._LOOKUP_RECORD_TYPE_L2_ONLY

        else:
            lrec = self._scimv2.MSFT_NetVirtualizationLookupRecordSettingData(
                CustomerAddress=customer_addr, VirtualSubnetID=vsid)
            record_type = self._LOOKUP_RECORD_TYPE_STATIC

        if (lrec and lrec[0].VirtualSubnetID == vsid and
                lrec[0].ProviderAddress == provider_addr):
            # lookup record already exists, nothing to do.
            return

        # create new lookup record.
        if lrec:
            lrec[0].Delete_()

        return self._create_new_object(
            self._scimv2.MSFT_NetVirtualizationLookupRecordSettingData,
            VirtualSubnetID=vsid,
            Rule=self._TRANSLATE_ENCAP,
            Type=record_type,
            MACAddress=mac,
            CustomerAddress=customer_addr,
            ProviderAddress=provider_addr)

    def _create_new_object(self, object_class, **args):
        new_obj = object_class.new(**args)
        new_obj.Put_()
        return new_obj

    def _get_network_ifaces_by_name(self, network_name):
        return [n for n in self._scimv2.MSFT_NetAdapter() if
                n.Name.find(network_name) >= 0]

    def _get_network_iface_index(self, network_name):
        if self._net_if_indexes.get(network_name, None):
            return self._net_if_indexes[network_name]

        description = (
            self._utils.get_vswitch_external_network_caption(network_name))

        # physical NIC and vswitch must have the same MAC address.
        networks = self._scimv2.MSFT_NetAdapter(
            InterfaceDescription=description)

        if networks:
            self._net_if_indexes[network_name] = networks[0].InterfaceIndex
            return networks[0].InterfaceIndex

    def get_network_iface_ip(self, network_name):
        networks = [n for n in self._get_network_ifaces_by_name(network_name)
                    if n.DriverDescription == self._HYPERV_VIRT_ADAPTER]

        if networks:
            ip_addr = self._scimv2.MSFT_NetIPAddress(
                InterfaceIndex=networks[0].InterfaceIndex,
                AddressFamily=self._IPV4_ADDRESS_FAMILY)

            if ip_addr:
                return (ip_addr[0].IPAddress, ip_addr[0].PrefixLength)
            else:
                LOG.error('No IP Address could be found for network: %s',
                          network_name)
        else:
            LOG.error('No vswitch was found with name: %s', network_name)

        return (None, None)


class NvgreR2(Nvgre):
    def multi_enable_wnv(self, network_names):
        # Windows Server 2012 R2 enables HNV automatically.
        pass

    def enable_wnv(self, network_name):
        # Windows Server 2012 R2 enables HNV automatically.
        pass
