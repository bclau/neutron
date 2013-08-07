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
# @author: Pedro Navarro Perez
# @author: Alessandro Pilotti, Cloudbase Solutions Srl

import sys

from neutron.plugins.hyperv.agent import utils

# Check needed for unit testing on Unix
if sys.platform == 'win32':
    import wmi

JOB_START = 4096
JOB_COMPLETE = 0


class HyperVUtilsV2(utils.HyperVUtils):

    EXTERNAL_PORT = 'Msvm_ExternalEthernetPort'
    SWITCH_PORT = 'Msvm_EthernetSwitchPort'
    Port_VLAN_SET_DATA = 'Msvm_EthernetSwitchPortVlanSettingData'
    LAN_ENDPOINT = 'Msvm_LANEndpoint'


    _namespace = '//./root/virtualization/v2'

    def __init__(self):
        super(HyperVUtilsV2, self).__init__()
        self._wmi_conn = None

    @property
    def _conn(self):
        if self._wmi_conn is None:
            self._wmi_conn = wmi.WMI(moniker=self._namespace)
        return self._wmi_conn

    def get_switch_ports(self, vswitch_name):
        vswitch = self._get_vswitch(vswitch_name)
        vswitch_ports = vswitch.associators(
            wmi_result_class=self.SWITCH_PORT)
        return set(p.Name for p in vswitch_ports)

    def get_vnic_ids(self):
        return set(
            p.ElementName
            for p in self._conn.Msvm_SyntheticEthernetPortSettingData()
            if not p.ElementName is None )

    def connect_vnic_to_vswitch(self, vswitch_name, switch_port_name):
        vnic = self._get_vnic_settings(switch_port_name)
        vm = self._get_vm_from_res_setting_data(vnic)
        vswitch = self._get_vswitch(vswitch_name)

        port, found = self._get_switch_port_allocation(switch_port_name, True)
        port.HostResource = [vswitch.path_()]
        port.Parent = vnic.path_()  
        if not found:
            self._add_virt_resource(vm, port)
        else:
            self._modify_virt_resource(vm, port)

    def _modify_virt_resource(self, vm, res_setting_data):
        vs_man_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        (job_path,
         out_res_setting_data,
         ret_val) = vs_man_svc.ModifyResourceSettings(
            ResourceSettings=[res_setting_data.GetText_(1)])
        self._check_job_status(ret_val, job_path)

    def _add_virt_resource(self, vm, res_setting_data):
        vs_man_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        res_xml = [res_setting_data.GetText_(1)]
        (job_path,
         out_res_setting_data,
         ret_val) = vs_man_svc.AddResourceSettings(vm.path_(), res_xml)
        self._check_job_status(ret_val, job_path)

    def disconnect_switch_port(
            self, vswitch_name, switch_port_name, delete_port):
        """ Disconnects the switch port """
        vs_man_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        sw_port, f = self._get_switch_port_allocation(switch_port_name)
        if not sw_port:
            # Port not found. It happens when the VM was already deleted.
            return
        
        sw_port.EnabledState = 3
        self._modify_virt_resource(None, sw_port)
        if delete_port:
            (job, ret_val) = vs_man_svc.RemoveResourceSettings(
                ResourceSettings=[sw_port.path_()])
            self._check_job_status(ret_val, job)

    def _get_vswitch(self, vswitch_name):
        vswitch = self._conn.Msvm_VirtualEthernetSwitch(
            ElementName=vswitch_name)
        if not len(vswitch):
            raise utils.HyperVException(msg=_('VSwitch not found: %s') %
                                  vswitch_name)
        return vswitch[0]

    def _get_vswitch_external_port(self, vswitch):
        vswitch_ports = vswitch.associators(
            wmi_result_class=self.SWITCH_PORT)
        for vswitch_port in vswitch_ports:
            lan_endpoints = vswitch_port.associators(
                wmi_result_class=self.LAN_ENDPOINT)
            if len(lan_endpoints):
                lan_endpoints = lan_endpoints[0].associators(
                    wmi_result_class=self.LAN_ENDPOINT)
                if len(lan_endpoints):
                    ext_port = lan_endpoints[0].associators(
                        wmi_result_class=self.EXTERNAL_PORT)
                    if ext_port:
                        return vswitch_port

    def set_vswitch_port_vlan_id(self, vlan_id, switch_port_name):
        port_alloc, found = self._get_switch_port_allocation(switch_port_name)
        if not found:
            raise utils.HyperVException(
                msg=_('Port Alloc not found: %s') % switch_port_name)
        
        vs_man_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        vlan_settings = self._get_vlan_setting_data_from_port_alloc(port_alloc)
        if vlan_settings:
            # removing the feature because it cannot be modified
            # due to wmi exception.
            (job_path, ret_val) = vs_man_svc.RemoveFeatureSettings(
                FeatureSettings=[vlan_settings.path_()])
            self._check_job_status(ret_val, job_path)

        (vlan_settings, found) = self._get_vlan_setting_data(switch_port_name)
        vlan_settings.AccessVlanId = vlan_id
        vlan_settings.OperationMode = 1
        (job_path, out, ret_val) = vs_man_svc.AddFeatureSettings(
            port_alloc.path_(), [vlan_settings.GetText_(1)])
        self._check_job_status(ret_val, job_path)

    def get_port_by_id(self, port_id, vswitch_name):
        vswitch = self._get_vswitch(vswitch_name)
        switch_ports = vswitch.associators(
            wmi_result_class=self.SWITCH_PORT)
        for switch_port in switch_ports:
            if (switch_port.ElementName == port_id):
                return switch_port

    def _check_job_status(self, ret_val, jobpath):
        if ret_val == JOB_START:
            super(HyperVUtilsV2, self)._check_job_status(
                utils.WMI_JOB_STATE_RUNNING, jobpath)

    def _get_vlan_setting_data_from_port_alloc(self, port_alloc):
        return self._get_first_or_null(port_alloc.associators(
            wmi_result_class=self.Port_VLAN_SET_DATA))

    def _get_vlan_setting_data(self, sp_name, create=True):
        return self._get_setting_data(
            self._conn.Msvm_EthernetSwitchPortVlanSettingData, sp_name, create)

    def _get_switch_port_allocation(self, el_name, create=False):
        return self._get_setting_data(
            self._conn.Msvm_EthernetPortAllocationSettingData, el_name, create)

    def _get_setting_data(self, class_call, element_name, create=True):
        data = self._get_first_or_null(class_call(ElementName=element_name))
        found = data is not None
        if not found and create:
            data = self._get_setting_data_default(class_call)
            data.ElementName = element_name
        return data, found

    def _get_setting_data_default(self, class_call):
        return [n for n in class_call()
                    if n.InstanceID.rfind('Default') > 0] [0]

    def _get_first_or_null(self, set_objects):
        if set_objects:
            return set_objects[0]                
