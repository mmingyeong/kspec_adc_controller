#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_controller.py

import os
import time
import logging

import asyncio

from nanotec_nanolib import Nanolib

__all__ = ["adc_controller"]

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("adc_controller.log", encoding='utf-8', errors='ignore'),
        logging.StreamHandler()
    ]
)

class adc_controller:
    """Talk to an KSPEC ADC system over Serial Port."""

    def __init__(self):
        self.nanolib_accessor: Nanolib.NanoLibAccessor = Nanolib.getNanoLibAccessor()
        logging.debug("Initializing adc_controller")
        
    def find_devices(self):
        listAvailableBus = self.nanolib_accessor.listAvailableBusHardware()
        if listAvailableBus.hasError():
            error_message = 'Error: listAvailableBusHardware() - ' + listAvailableBus.getError()
            logging.error(error_message)
            raise Exception(error_message)

        bus_hardware_ids = listAvailableBus.getResult()
        logging.info("Available Bus Hardware IDs:")
        for i in range(bus_hardware_ids.size()):
            bus_id = bus_hardware_ids[i]
            logging.info(f"ID {i}: {bus_id.toString() if hasattr(bus_id, 'toString') else str(bus_id)}")

        ind = 6
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
        logging.info("Device IDs found:")
        for i in range(self.device_ids.size()):
            logging.info(f"ID {i}: {self.device_ids[i]}")

        if not self.device_ids:
            error_message = "No devices found during scan."
            logging.error(error_message)
            raise Exception(error_message)

        self.handles = []
        self.device_handle_1 = self.nanolib_accessor.addDevice(self.device_ids[0]).getResult()
        self.device_handle_2 = self.nanolib_accessor.addDevice(self.device_ids[1]).getResult()
        logging.info(self.device_handle_1)
        logging.info(self.device_handle_2)
        self.handles.append(self.device_handle_1)
        self.handles.append(self.device_handle_2)
        self.device_1_connected = False  # Attribute to track device 1 connection status
        self.device_2_connected = False  # Attribute to track device 2 connection status

    def connect(self):
        logging.debug("Connecting devices")
        try:
            # Check if device 1 is already connected
            if self.device_1_connected:
                logging.info("Device 1 is already connected.")
            else:
                res1 = self.nanolib_accessor.connectDevice(self.device_handle_1)
                if res1.hasError():
                    error_message = 'Error: connectDevice() - ' + res1.getError()
                    logging.error(error_message)
                    raise Exception(error_message)
                self.device_1_connected = True  # Set connection status to True upon success

            # Check if device 2 is already connected
            if self.device_2_connected:
                logging.info("Device 2 is already connected.")
            else:
                res2 = self.nanolib_accessor.connectDevice(self.device_handle_2)
                if res2.hasError():
                    error_message = 'Error: connectDevice() - ' + res2.getError()
                    logging.error(error_message)
                    raise Exception(error_message)
                self.device_2_connected = True  # Set connection status to True upon success

        except Exception as e:
            logging.exception("An error occurred during connect: %s", e)


    def disconnect(self):
        logging.debug("Disconnecting devices")
        try:
            # Check if device 1 is connected before disconnecting
            if self.device_1_connected:
                res1 = self.nanolib_accessor.disconnectDevice(self.device_handle_1)
                if res1.hasError():
                    error_message = 'Error: disconnectDevice() - ' + res1.getError()
                    logging.error(error_message)
                    raise Exception(error_message)
                self.device_1_connected = False  # Set connection status to False upon successful disconnect
                logging.info("Device 1 disconnected successfully.")
            else:
                logging.info("Device 1 was not connected.")

            # Check if device 2 is connected before disconnecting
            if self.device_2_connected:
                res2 = self.nanolib_accessor.disconnectDevice(self.device_handle_2)
                if res2.hasError():
                    error_message = 'Error: disconnectDevice() - ' + res2.getError()
                    logging.error(error_message)
                    raise Exception(error_message)
                self.device_2_connected = False  # Set connection status to False upon successful disconnect
                logging.info("Device 2 disconnected successfully.")
            else:
                logging.info("Device 2 was not connected.")

        except Exception as e:
            logging.exception("An error occurred during disconnect: %s", e)

            
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

    def read_obj(self, MotorNum):
        if MotorNum == 1:
            logging.debug(f'Read Motor {MotorNum}')
            logging.debug("Reading subindex 0 of index 0x6040")
            status_word = self.nanolib_accessor.readNumber(self.device_handle_1, Nanolib.OdIndex(0x6040, 0x00))
            logging.debug('Result: %s', status_word)
        elif MotorNum == 2:
            logging.debug(f'Read Motor {MotorNum}')
            logging.debug("Reading subindex 0 of index 0x6040")
            status_word = self.nanolib_accessor.readNumber(self.device_handle_2, Nanolib.OdIndex(0x6040, 0x00))
            logging.debug('Result: %s', status_word)
        else:
            error_message = 'Error: wrong MotorNum'
            logging.error(error_message)
            raise Exception(error_message)

    async def move_motor(self, MotorNum, pos, vel=100):
        """
        Asynchronously move the specified motor to a target position at a given velocity in Profile Position mode.

        Parameters:
        ----------
        MotorNum : int
            The motor number to control. Use `1` for `device_handle_1` and `2` for `device_handle_2`.
        pos : int
            The target position for the motor in encoder counts. The range is -4096 to 4096 for a full rotation,
            where positive values move the motor clockwise and negative values move it counterclockwise.
            Each encoder count corresponds to approximately 0.088 degrees (360 degrees / 4096 counts).
        vel : int, optional
            The target velocity in RPM for the motor. Default is 100 RPM, a moderate speed suitable for general use.

        Returns:
        -------
        dict
            A dictionary containing the initial position, final position, and the position change in encoder counts,
            along with the total execution time in seconds.

        Raises:
        ------
        Exception
            If an error occurs during motor movement, such as an invalid handle or failure to set
            control parameters, an exception is raised with an appropriate error message.
        """
        logging.debug(f"Moving Motor {MotorNum} to position {pos} with velocity {vel}")
        
        start_time = time.time()  # 시작 시간 기록
        
        try:
            # Set device handle based on MotorNum
            device_handle = self.device_handle_1 if MotorNum == 1 else self.device_handle_2
            if not device_handle:
                raise Exception(f"Device handle for Motor {MotorNum} not found.")
            
            # Stop any running NanoJ program (optional step)
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)

            # Set Profile Position mode
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)

            # Set velocity (in rpm)
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, vel, Nanolib.OdIndex(0x6081, 0x00), 32)

            # Set target position
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, pos, Nanolib.OdIndex(0x607A, 0x00), 32)

            # Enable operation state
            for command in [6, 7, 0xF]:
                await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, command, Nanolib.OdIndex(0x6040, 0x00), 16)

            # Move motor to target position
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)

            # Monitor until movement is complete
            while True:
                status_word = await asyncio.to_thread(self.nanolib_accessor.readNumber, device_handle, Nanolib.OdIndex(0x6041, 0x00))
                logging.debug(f"Motor {MotorNum} status_word = {status_word.getResult()}")
                if (status_word.getResult() & 0x1400) == 0x1400:
                    logging.info(f"Motor {MotorNum} reached target position.")
                    break
                await asyncio.sleep(0.1)  # Small delay to allow other async tasks to run

        except Exception as e:
            logging.error(f"Failed to move Motor {MotorNum}: {e}")
            raise
        finally:
            # 함수 실행 시간 기록
            execution_time = time.time() - start_time
            logging.info(f"Total execution time for move_motor (Motor {MotorNum}): {execution_time:.2f} seconds")


    async def stop_motor(self, MotorNum):
        """
        Asynchronously stop the specified motor and log any errors from the error stack.

        Parameters:
        ----------
        MotorNum : int
            The motor number to stop. Use `1` for `device_handle_1` and `2` for `device_handle_2`.

        Raises:
        ------
        Exception
            If an error occurs while stopping the motor or accessing the device handle, an exception
            is raised with an appropriate error message.
        """
        logging.debug(f"Stopping Motor {MotorNum}")

        start_time = time.time()  # 시작 시간 기록
        
        try:
            # Set device handle based on MotorNum
            device_handle = self.device_handle_1 if MotorNum == 1 else self.device_handle_2
            if not device_handle:
                raise Exception(f"Device handle for Motor {MotorNum} not found.")

            # Send stop command
            await asyncio.to_thread(self.nanolib_accessor.writeNumber, device_handle, -200, Nanolib.OdIndex(0x60FF, 0x00), 32)

            # Log current status word
            status_word = await asyncio.to_thread(self.nanolib_accessor.readNumber, device_handle, Nanolib.OdIndex(0x60FF, 0x00))
            logging.debug(f"Motor {MotorNum} stopped with status word: {status_word}")

            # Read and log the error stack
            readarrindex = Nanolib.OdIndex(0x1003, 0x00)
            error_stack = await asyncio.to_thread(self.nanolib_accessor.readNumberArray, device_handle, readarrindex.getIndex())
            error_count = error_stack.getResult()[0] if error_stack.getResult() else 0
            logging.debug(f"Motor {MotorNum} error stack contains {error_count} elements")

        except Exception as e:
            logging.error(f"Failed to stop Motor {MotorNum}: {e}")
            raise
        finally:
            # 함수 실행 시간 기록
            execution_time = time.time() - start_time
            logging.info(f"Total execution time for stop_motor (Motor {MotorNum}): {execution_time:.2f} seconds")



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

