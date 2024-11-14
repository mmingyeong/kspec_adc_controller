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
from pymodbus.client import ModbusSerialClient

__all__ = ["adc_controller"]

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("log/adc_controller.log", encoding='utf-8', errors='ignore'),
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

    def connect(self, motor_number=0):
        logging.debug("Connecting devices")
        try:
            if motor_number not in [0, 1, 2]:
                raise ValueError("Invalid motor number. Must be 0, 1, or 2.")

            if motor_number == 1:
                # Connect only device 1
                if self.device_1_connected:
                    logging.info("Device 1 is already connected.")
                else:
                    res1 = self.nanolib_accessor.connectDevice(self.device_handle_1)
                    if res1.hasError():
                        error_message = 'Error: connectDevice() - ' + res1.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_1_connected = True
                    logging.info("Device 1 connected successfully.")
            elif motor_number == 2:
                # Connect only device 2
                if self.device_2_connected:
                    logging.info("Device 2 is already connected.")
                else:
                    res2 = self.nanolib_accessor.connectDevice(self.device_handle_2)
                    if res2.hasError():
                        error_message = 'Error: connectDevice() - ' + res2.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_2_connected = True
                    logging.info("Device 2 connected successfully.")
            else:
                # Connect both devices if motor_number is 0
                if not self.device_1_connected:
                    res1 = self.nanolib_accessor.connectDevice(self.device_handle_1)
                    if res1.hasError():
                        error_message = 'Error: connectDevice() - ' + res1.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_1_connected = True
                    logging.info("Device 1 connected successfully.")

                if not self.device_2_connected:
                    res2 = self.nanolib_accessor.connectDevice(self.device_handle_2)
                    if res2.hasError():
                        error_message = 'Error: connectDevice() - ' + res2.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_2_connected = True
                    logging.info("Device 2 connected successfully.")

        except ValueError as ve:
            logging.error("ValueError: %s", ve)
            raise
        except Exception as e:
            logging.exception("An error occurred during connect: %s", e)

    def disconnect(self, motor_number=0):
        logging.debug("Disconnecting devices")
        try:
            if motor_number not in [0, 1, 2]:
                raise ValueError("Invalid motor number. Must be 0, 1, or 2.")

            if motor_number == 1:
                # Disconnect only device 1
                if self.device_1_connected:
                    res1 = self.nanolib_accessor.disconnectDevice(self.device_handle_1)
                    if res1.hasError():
                        error_message = 'Error: disconnectDevice() - ' + res1.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_1_connected = False
                    logging.info("Device 1 disconnected successfully.")
                else:
                    logging.info("Device 1 was not connected.")
            elif motor_number == 2:
                # Disconnect only device 2
                if self.device_2_connected:
                    res2 = self.nanolib_accessor.disconnectDevice(self.device_handle_2)
                    if res2.hasError():
                        error_message = 'Error: disconnectDevice() - ' + res2.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_2_connected = False
                    logging.info("Device 2 disconnected successfully.")
                else:
                    logging.info("Device 2 was not connected.")
            else:
                # Disconnect both devices if motor_number is 0
                if self.device_1_connected:
                    res1 = self.nanolib_accessor.disconnectDevice(self.device_handle_1)
                    if res1.hasError():
                        error_message = 'Error: disconnectDevice() - ' + res1.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_1_connected = False
                    logging.info("Device 1 disconnected successfully.")
                else:
                    logging.info("Device 1 was not connected.")

                if self.device_2_connected:
                    res2 = self.nanolib_accessor.disconnectDevice(self.device_handle_2)
                    if res2.hasError():
                        error_message = 'Error: disconnectDevice() - ' + res2.getError()
                        logging.error(error_message)
                        raise Exception(error_message)
                    self.device_2_connected = False
                    logging.info("Device 2 disconnected successfully.")
                else:
                    logging.info("Device 2 was not connected.")

        except ValueError as ve:
            logging.error("ValueError: %s", ve)
            raise
        except Exception as e:
            logging.exception("An error occurred during disconnect: %s", e)


            
    def close(self):
        logging.debug("close all")

        close_result = self.nanolib_accessor.closeBusHardware(self.adc_motor_id)
        
        if close_result.hasError():
            error_message = 'Error: closeBusHardware() - ' + close_result.getError()
            logging.error(error_message)
            raise Exception(error_message)

    def move_motor(self, MotorNum, pos, vel=10):
        """
        Synchronously move the specified motor to a target position at a given velocity in Profile Position mode.

        Parameters:
        ----------
        MotorNum : int
            The motor number to control. Use `1` for `device_handle_1` and `2` for `device_handle_2`.
        pos : int
            The target position for the motor in encoder counts. The range is -4096 to 4096 for a full rotation,
            where positive values move the motor clockwise and negative values move it counterclockwise.
            Each encoder count corresponds to approximately 0.088 degrees (360 degrees / 4096 counts).
        vel : int, optional
            The target velocity in RPM for the motor. Default is 10 RPM.

        Returns:
        -------
        dict
            A dictionary containing the initial position, final position, the position change in encoder counts,
            and the total execution time in seconds.

        Raises:
        ------
        Exception
            If an error occurs during motor movement, such as an invalid handle or failure to set
            control parameters, an exception is raised with an appropriate error message.
        """
        logging.debug(f"Moving Motor {MotorNum} to position {pos} with velocity {vel}")

        # Check if the motor is connected
        if MotorNum == 1 and not self.device_1_connected:
            raise Exception("Error: Motor 1 is not connected. Please connect it before moving.")
        elif MotorNum == 2 and not self.device_2_connected:
            raise Exception("Error: Motor 2 is not connected. Please connect it before moving.")

        start_time = time.time()  # Start time recording
        res = {}  # Initialize result dictionary

        try:
            # Set device handle based on MotorNum
            device_handle = self.device_handle_1 if MotorNum == 1 else self.device_handle_2
            if not device_handle:
                raise Exception(f"Device handle for Motor {MotorNum} not found.")
            
            # Stop any running NanoJ program
            self.nanolib_accessor.writeNumber(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)

            # Set Profile Position mode
            self.nanolib_accessor.writeNumber(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)

            # Set velocity (in rpm)
            self.nanolib_accessor.writeNumber(device_handle, vel, Nanolib.OdIndex(0x6081, 0x00), 32)

            # Set target position
            init_pos = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6064, 0x00))
            initial_position = init_pos.getResult()
            self.nanolib_accessor.writeNumber(device_handle, pos, Nanolib.OdIndex(0x607A, 0x00), 32)

            # Enable operation state
            for command in [6, 7, 0xF]:
                self.nanolib_accessor.writeNumber(device_handle, command, Nanolib.OdIndex(0x6040, 0x00), 16)

            # Move motor to target position
            self.nanolib_accessor.writeNumber(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)

            # Monitor until movement is complete
            while True:
                status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                logging.debug(f"Motor {MotorNum} status_word = {status_word.getResult()}")
                if (status_word.getResult() & 0x1400) == 0x1400:
                    logging.info(f"Motor {MotorNum} reached target position.")
                    break
                time.sleep(5)  # Small delay
            
            final_pos = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6064, 0x00))
            final_position = final_pos.getResult() 
            
            # Populate result dictionary
            res = {
                "initial_position": initial_position,
                "final_position": final_position,
                "position_change": final_position - initial_position,
                "execution_time": time.time() - start_time
            }

        except Exception as e:
            logging.error(f"Failed to move Motor {MotorNum}: {e}")
            raise
        finally:
            # Log the execution time and results
            execution_time = time.time() - start_time
            logging.info(f"Total execution time for move_motor (Motor {MotorNum}): {execution_time:.2f} seconds")
            logging.info(res)

        return res



    def DeviceState(self, motor_num=0):
        logging.debug("Checking device and connection states, including Modbus RTU network status")
        res = {"motor1": {}, "motor2": {}}

        # Check motor status based on motor_num
        if motor_num == 0 or motor_num == 1:
            # Check and store the connection state for motor1
            connection_state1 = self.nanolib_accessor.checkConnectionState(self.device_handle_1).getResult()
            res["motor1"]["connection_state"] = bool(connection_state1)

            # Get and store the device state for motor1
            device_state1 = self.nanolib_accessor.getDeviceState(self.device_handle_1).getResult()
            res["motor1"]["device_state"] = device_state1

            # Get and store additional state for motor1
            extra_state1 = self.nanolib_accessor.getConnectionState(self.device_handle_1).getResult()
            res["motor1"]["extra_state"] = bool(extra_state1)

        if motor_num == 0 or motor_num == 2:
            # Check and store the connection state for motor2
            connection_state2 = self.nanolib_accessor.checkConnectionState(self.device_handle_2).getResult()
            res["motor2"]["connection_state"] = bool(connection_state2)

            # Get and store the device state for motor2
            device_state2 = self.nanolib_accessor.getDeviceState(self.device_handle_2).getResult()
            res["motor2"]["device_state"] = device_state2

            # Get and store additional state for motor2
            extra_state2 = self.nanolib_accessor.getConnectionState(self.device_handle_2).getResult()
            res["motor2"]["extra_state"] = bool(extra_state2)

        # If an invalid motor number is provided, raise an error
        if motor_num not in [0, 1, 2]:
            raise ValueError("Invalid motor number. Use 0 for both motors, 1 for motor 1, or 2 for motor 2.")

        logging.info("Device states: %s", res)
        return res

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