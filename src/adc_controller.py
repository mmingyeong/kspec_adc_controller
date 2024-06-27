#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_controller.py

import os
import time
import logging

from nanotec_nanolib import Nanolib
from nanolib_helper import NanolibHelper

__all__ = ["adc_controller"]

# 설정 로깅
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("adc_controller.log"),
        logging.StreamHandler()
    ]
)

class adc_controller:
    """Talk to an KSPEC ADC system over Serial Port."""

    def __init__(self):
        logging.debug("Initializing adc_controller")
        self.nanolib_accessor: Nanolib.NanoLibAccessor = Nanolib.getNanoLibAccessor()
        listAvailableBus = self.nanolib_accessor.listAvailableBusHardware()
        if listAvailableBus.hasError():
            error_message = 'Error: listAvailableBusHardware() - ' + bus_hardware_ids.getError()
            logging.error(error_message)
            raise Exception(error_message)
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
            error_message = 'Error: openBusHardwareWithProtocol() - ' + open_bus.getError()
            logging.error(error_message)
            raise Exception(error_message)
        
        scan_devices = self.nanolib_accessor.scanDevices(self.adc_motor_id, callbackScanBus)
        if scan_devices.hasError():
            error_message = 'Error: scanDevices() - ' + scan_devices.getError()
            logging.error(error_message)
            raise Exception(error_message)

        self.device_ids = scan_devices.getResult()
        #if len(self.device_ids) < 2:
        #    error_message = 'Error: Not enough devices found'
        #    logging.error(error_message)
        #    raise Exception(error_message)
        
        self.handles = []
        self.device_handle_1 = self.nanolib_accessor.addDevice(self.device_ids[0]).getResult()
        self.device_handle_2 = self.nanolib_accessor.addDevice(self.device_ids[1]).getResult()
        self.handles.append(self.device_handle_1)
        self.handles.append(self.device_handle_2)

    def connect(self):
        logging.debug("Connecting devices")
        try:
            res1 = self.nanolib_accessor.connectDevice(self.device_handle_1)
            res2 = self.nanolib_accessor.connectDevice(self.device_handle_2)

            if res1.hasError():
                error_message = 'Error: connectDevice() - ' + res1.getError()
                logging.error(error_message)
                raise Exception(error_message)
            if res2.hasError():
                error_message = 'Error: connectDevice() - ' + res2.getError()
                logging.error(error_message)
                raise Exception(error_message)
                
        except Exception as e:
            logging.exception("An error occurred during connect: %s", e)
            print(f"An error occurred: {e}")

    def disconnect(self):
        logging.debug("Disconnecting devices")
        try:
            res1 = self.nanolib_accessor.disconnectDevice(self.device_handle_1)
            res2 = self.nanolib_accessor.disconnectDevice(self.device_handle_2)

            if res1.hasError():
                error_message = 'Error: disconnectDevice() - ' + res1.getError()
                logging.error(error_message)
                raise Exception(error_message)
            if res2.hasError():
                error_message = 'Error: disconnectDevice() - ' + res2.getError()
                logging.error(error_message)
                raise Exception(error_message)

        except Exception as e:
            logging.exception("An error occurred during disconnect: %s", e)
            print(f"An error occurred: {e}")
            
    def close(self):
        logging.debug("close all")

        close_result = self.nanolib_accessor.closeBusHardware(self.adc_motor_id)
        if close_result.hasError():
            error_message = 'Error: closeBusHardware() - ' + close_result.getError()
            logging.error(error_message)
            raise Exception(error_message)
        

    def checkConnectionState(self):
        logging.debug("Checking connection state")
        res = {}
        check1 = self.nanolib_accessor.checkConnectionState(self.device_handle_1)
        check2 = self.nanolib_accessor.checkConnectionState(self.device_handle_2)
        res["motor 1"] = bool(check1.getResult())
        res["motor 2"] = bool(check2.getResult())
        logging.info("Connection state: %s", res)
        return res
    
    def test_PP(self):
        logging.debug("Testing Profile Position mode")
        for device_handle in self.handles:
            self.object_dictionary_access_examples(device_handle)
            
            # stop a possibly running NanoJ program
            self.nanolib_accessor.writeNumber(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
            
            # choose Profile Position mode
            self.nanolib_accessor.writeNumber(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)
            
            # set the desired speed in rpm
            self.nanolib_accessor.writeNumber(device_handle, 100, Nanolib.OdIndex(0x6081, 0x00), 32)
            
            # set the desired target position
            self.nanolib_accessor.writeNumber(device_handle, 36000, Nanolib.OdIndex(0x607A, 0x00), 32)
            
            # switch the state machine to "operation enabled"
            self.nanolib_accessor.writeNumber(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
            self.nanolib_accessor.writeNumber(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
            self.nanolib_accessor.writeNumber(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # move the motor to the desired target psoition relatively
            self.nanolib_accessor.writeNumber(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
            logging.debug(f"status_word = {status_word.getResult()}")
            #while(True):
            #    status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
            #    logging.debug(f"status_word = {status_word.getResult()}")
            #    if ((status_word.getResult() & 0x1400) == 0x1400):
            #        break
                
            self.nanolib_accessor.writeNumber(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # set the new desired target position
            self.nanolib_accessor.writeNumber(device_handle, -36000, Nanolib.OdIndex(0x607A, 0x00), 32)
            
            # move the motor to the desired target psoition relatively
            self.nanolib_accessor.writeNumber(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)

            status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
            logging.debug(f"status_word = {status_word.getResult()}")            
            #while(True):
            #    status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
            #    logging.debug(f"status_word = {status_word.getResult()}")
            #    if ((status_word.getResult() & 0x1400) == 0x1400):
            #        break
            
            # stop the motor
            self.nanolib_accessor.writeNumber(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

    def test_PV(self):
        logging.debug("Testing Profile Velocity mode")
        for device_handle in self.handles:
            self.object_dictionary_access_examples(device_handle)
            
            # stop a possibly running NanoJ program
            self.nanolib_accessor.writeNumber(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
            
            # choose Profile Velocity mode
            self.nanolib_accessor.writeNumber(device_handle, 3, Nanolib.OdIndex(0x6060, 0x00), 8)
            
            # set the desired speed in rpm
            self.nanolib_accessor.writeNumber(device_handle, 100, Nanolib.OdIndex(0x60FF, 0x00), 32)
            
            # switch the state machine to "operation enabled"
            self.nanolib_accessor.writeNumber(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
            self.nanolib_accessor.writeNumber(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
            self.nanolib_accessor.writeNumber(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # let the motor run for 3s
            time.sleep(3)
                
            # stop the motor
            self.nanolib_accessor.writeNumber(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # set the desired speed in rpm, now counterclockwise
            self.nanolib_accessor.writeNumber(device_handle, -100, Nanolib.OdIndex(0x60FF, 0x00), 32)
            
            # start the motor    
            self.nanolib_accessor.writeNumber(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            # let the motor run for 3s
            time.sleep(3)
            
            # stop the motor
            self.nanolib_accessor.writeNumber(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    def object_dictionary_access_examples(self, device_handle):
        logging.debug('OD Example')

        logging.debug('Motor Stop (0x6040-0)')
        self.nanolib_accessor.writeNumber(device_handle, -200, Nanolib.OdIndex(0x60FF, 0x00), 32)
        
        logging.debug("Reading subindex 0 of index 0x6040")
        status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x60FF, 0x00))
        logging.debug('Result: %s', status_word)

        logging.debug('Read Nanotec home page string')
        home_page = self.nanolib_accessor.readString(device_handle, Nanolib.OdIndex(0x6505, 0x00))
        logging.debug('The home page of Nanotec Electronic GmbH & Co. KG is: %s', home_page)

        logging.debug('Read device error stack')
        readarrindex = Nanolib.OdIndex(0x1003, 0x00)
        error_stack = self.nanolib_accessor.readNumberArray(device_handle, readarrindex.getIndex())
        res = error_stack.getResult()
        logging.debug('The error stack has %d elements', res[0])



# ============================================================ #

class ScanBusCallback(Nanolib.NlcScanBusCallback): # override super class
    def __init__(self):
        super().__init__()
    def callback(self, info, devicesFound, data):
        if info == Nanolib.BusScanInfo_Start :
            print('Scan started.')
        elif info == Nanolib.BusScanInfo_Progress :
            if (data & 1) == 0 :
                print('.', end='', flush=True)
        elif info == Nanolib.BusScanInfo_Finished :
            print('\nScan finished.')

        return Nanolib.ResultVoid()

callbackScanBus = ScanBusCallback() # Nanolib 2021

# ============================================================ #

