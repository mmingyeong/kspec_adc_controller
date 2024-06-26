#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_controller.py

import os
import time

from nanotec_nanolib import Nanolib

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

        self.device_handle_1 = self.nanolib_accessor.addDevice(self.device_ids[0]).getResult()
        self.device_handle_2 = self.nanolib_accessor.addDevice(self.device_ids[1]).getResult()

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
