#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_controller.py

import os
import time

from nanotec_nanolib import Nanolib
from nanolib_helper import NanolibHelper

__all__ = ["adc_controller"]

class adc_controller:
    """Talk to an KSPEC ADC system over Serial Port."""

    def __init__(self):
        self.nanolib_accessor: Nanolib.NanoLibAccessor = Nanolib.getNanoLibAccessor()
        listAvailableBus = self.nanolib_accessor.listAvailableBusHardware()
        if listAvailableBus.hasError():
            raise Exception('Error: listAvailableBusHardware() - ' + bus_hardware_ids.getError())
        bus_hardware_ids = listAvailableBus.getResult()

        ind = 2   # input_device = "Serial Port (COM11)"
        self.adc_motor_id = bus_hardware_ids[ind]
        
        self.adc_motor_options = Nanolib.BusHardwareOptions()
        self.adc_motor_options.addOption(
            Nanolib.Serial().BAUD_RATE_OPTIONS_NAME,
            Nanolib.SerialBaudRate().BAUD_RATE_115200
        )
        self.adc_motor_options.addOption(
            Nanolib.Serial().PARITY_OPTIONS_NAME,
            Nanolib.SerialParity().EVEN
        )
        
        open_bus = self.nanolib_accessor.openBusHardwareWithProtocol(self.adc_motor_id, self.adc_motor_options)
        if open_bus.hasError():
            raise Exception('Error: openBusHardwareWithProtocol() - ' + open_bus.getError())
        
        scan_devices = self.nanolib_accessor.scanDevices(self.adc_motor_id, callbackScanBus)
        if scan_devices.hasError():
            raise Exception('Error: scanDevices() - ' + scan_devices.getError())

        self.device_ids = scan_devices.getResult()
        if len(self.device_ids) < 2:
            raise Exception('Error: Not enough devices found')
        
        self.fhandles = []
        self.device_handle_1 = self.nanolib_accessor.addDevice(self.device_ids[0]).getResult()
        self.device_handle_2 = self.nanolib_accessor.addDevice(self.device_ids[1]).getResult()
        self.handles.append(self.device_handle_1)
        self.handles.append(self.device_handle_2)

    def connect(self):
        try:
            res1 = self.nanolib_accessor.connectDevice(self.device_handle_1)
            res2 = self.nanolib_accessor.connectDevice(self.device_handle_2)

            if res1.hasError():
                raise Exception('Error: connectDevice() - ' + res1.getError())
            if res2.hasError():
                raise Exception('Error: connectDevice() - ' + res2.getError())
                
        except Exception as e:
            print(f"An error occurred: {e}")
            # 여기서 필요하다면 추가적인 예외 처리를 할 수 있습니다.

    def disconnect(self):
        try:
            res1 = self.nanolib_accessor.disconnectDevice(self.device_handle_1)
            res2 = self.nanolib_accessor.disconnectDevice(self.device_handle_2)

            if res1.hasError():
                raise Exception('Error: disconnectDevice() - ' + res1.getError())
            if res2.hasError():
                raise Exception('Error: disconnectDevice() - ' + res2.getError())

            close_result = self.nanolib_accessor.closeBusHardware(self.adc_motor_id)
            if close_result.hasError():
                raise Exception('Error: closeBusHardware() - ' + close_result.getError())

        except Exception as e:
            print(f"An error occurred: {e}")
            # 여기서 필요하다면 추가적인 예외 처리를 할 수 있습니다.

    def checkConnectionState(self):
        res = {}
        check1 = self.nanolib_accessor.checkConnectionState(self.device_handle_1)
        check2 = self.nanolib_accessor.checkConnectionState(self.device_handle_2)
        res["motor 1"] = bool(check1.getResult())
        res["motor 2"] = bool(check2.getResult())
        return res
    
    def test_PP(self):
        # now ready to work with the controller, here are some examples on how to access the
        # # object dictionary:
        for device_handle in self.handles:
            object_dictionary_access_examples(NanolibHelper, device_handle)
            
            ### example code to let the motor run in Profile Position mode
            
            # stop a possibly running NanoJ program
            nanoj_control = NanolibHelper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
            
            # choose Profile Position mode
            mode_of_operation = NanolibHelper.write_number(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)
            
            # set the desired speed in rpm
            target_velocity = NanolibHelper.write_number(device_handle, 100, Nanolib.OdIndex(0x6081, 0x00), 32)
            
            # set the desired target position
            target_velocity = NanolibHelper.write_number(device_handle, 36000, Nanolib.OdIndex(0x607A, 0x00), 32)
            
            # switch the state machine to "operation enabled"
            status_word = NanolibHelper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = NanolibHelper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = NanolibHelper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # move the motor to the desired target psoition relatively
            status_word = NanolibHelper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            while(True):
                status_word = NanolibHelper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                if ((status_word & 0x1400) == 0x1400):
                    break
                
            status_word = NanolibHelper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # set the new desired target position
            target_velocity = NanolibHelper.write_number(device_handle, -36000, Nanolib.OdIndex(0x607A, 0x00), 32)
            
            # move the motor to the desired target psoition relatively
            status_word = NanolibHelper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            while(True):
                status_word = NanolibHelper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                if ((status_word & 0x1400) == 0x1400):
                    break
            
            # stop the motor
            status_word = NanolibHelper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

    def test_PV(self):
        # now ready to work with the controller, here are some examples on how to access the
        # # object dictionary:
        for device_handle in self.handles:
            object_dictionary_access_examples(NanolibHelper, device_handle)
            
            ### example code to let the motor run in Profile Velocity mode
            
            # stop a possibly running NanoJ program
            nanoj_control = NanolibHelper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
            
            # choose Profile Velocity mode
            mode_of_operation = NanolibHelper.write_number(device_handle, 3, Nanolib.OdIndex(0x6060, 0x00), 8)
            
            # set the desired speed in rpm
            target_velocity = NanolibHelper.write_number(device_handle, 100, Nanolib.OdIndex(0x60FF, 0x00), 32)
            
            # switch the state machine to "operation enabled"
            status_word = NanolibHelper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = NanolibHelper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = NanolibHelper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # let the motor run for 3s
            time.sleep(3)
                
            # stop the motor
            status_word = NanolibHelper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # set the desired speed in rpm, now counterclockwise
            target_velocity = NanolibHelper.write_number(device_handle, -100, Nanolib.OdIndex(0x60FF, 0x00), 32)
            
            # start the motor    
            status_word = NanolibHelper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # let the motor run for 3s
            time.sleep(3)
            
            # stop the motor
            status_word = NanolibHelper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)


# ============================================================ #

class ScanBusCallback(Nanolib.NlcScanBusCallback): # override super class
    def __init__(self):
        super().__init__()

    def callback(self, info, devicesFound, data):
        if info == Nanolib.BusScanInfo_Start:
            print('Scan started.')
        elif info == Nanolib.BusScanInfo_Progress:
            if (data & 1) == 0:
                print('.', end='', flush=True)
        elif info == Nanolib.BusScanInfo_Finished:
            print('\nScan finished.')

        return Nanolib.ResultVoid()

callbackScanBus = ScanBusCallback() # Nanolib 2021

# ============================================================ #


def object_dictionary_access_examples(nanolib_helper, device_handle):
    print('\nOD Example\n')

    print('Motor Stop (0x6040-0)')
    status_word = nanolib_helper.write_number(device_handle, -200, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    print("Reading subindex 0 of index 0x6040")
    status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x60FF, 0x00))
    print('Result: {}\n'.format(status_word))

    print('\nRead Nanotec home page string')
    home_page = nanolib_helper.read_string(device_handle, Nanolib.OdIndex(0x6505, 0x00))
    print('The home page of Nanotec Electronic GmbH & Co. KG is: {}'.format(home_page))

    print('\nRead device error stack')
    error_stack = nanolib_helper.read_array(device_handle, Nanolib.OdIndex(0x1003, 0x00))
    print('The error stack has {} elements\n'.format(error_stack[0]))