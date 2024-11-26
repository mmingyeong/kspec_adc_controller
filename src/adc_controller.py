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
        logging.info("Starting the process to find devices...")
        
        # Listing available bus hardware
        logging.info("Calling listAvailableBusHardware()...")
        listAvailableBus = self.nanolib_accessor.listAvailableBusHardware()
        if listAvailableBus.hasError():
            error_message = 'Error: listAvailableBusHardware() - ' + listAvailableBus.getError()
            logging.error(error_message)
            raise Exception(error_message)

        bus_hardware_ids = listAvailableBus.getResult()
        logging.info(f"Number of available bus hardware IDs: {bus_hardware_ids.size()}")
        logging.info("Available Bus Hardware IDs:")
        for i in range(bus_hardware_ids.size()):
            bus_id = bus_hardware_ids[i]
            logging.info(f"ID {i}: {bus_id.toString() if hasattr(bus_id, 'toString') else str(bus_id)}")

        # Selecting a bus hardware ID
        ind = 0  # Index for initial setup; verify correctness
        logging.info(f"Selecting bus hardware ID at index {ind}.")
        try:
            self.adc_motor_id = bus_hardware_ids[ind]
            logging.info(f"Selected bus hardware ID: {self.adc_motor_id}")
        except IndexError as e:
            error_message = f"IndexError: Unable to select bus hardware ID at index {ind}."
            logging.error(error_message)
            raise Exception(error_message) from e

        # Setting up options
        logging.info("Configuring ADC motor options...")
        self.adc_motor_options = Nanolib.BusHardwareOptions()
        self.adc_motor_options.addOption(
            Nanolib.Serial().BAUD_RATE_OPTIONS_NAME,
            Nanolib.SerialBaudRate().BAUD_RATE_115200
        )
        self.adc_motor_options.addOption(
            Nanolib.Serial().PARITY_OPTIONS_NAME,
            Nanolib.SerialParity().EVEN
        )
        logging.info("ADC motor options configured successfully.")

        # Opening bus hardware
        logging.info("Opening bus hardware with protocol...")
        open_bus = self.nanolib_accessor.openBusHardwareWithProtocol(self.adc_motor_id, self.adc_motor_options)
        if open_bus.hasError():
            error_message = 'Error: openBusHardwareWithProtocol() - ' + open_bus.getError()
            logging.error(error_message)
            raise Exception(error_message)
        logging.info("Bus hardware opened successfully.")

        # Scanning devices on the bus
        logging.info("Scanning for devices on the bus...")
        scan_devices = self.nanolib_accessor.scanDevices(self.adc_motor_id, callbackScanBus)
        if scan_devices.hasError():
            error_message = 'Error: scanDevices() - ' + scan_devices.getError()
            logging.error(error_message)
            raise Exception(error_message)

        self.device_ids = scan_devices.getResult()
        logging.info(f"Number of devices found: {self.device_ids.size()}")
        logging.info("Device IDs found:")
        for i in range(self.device_ids.size()):
            logging.info(f"ID {i}: {self.device_ids[i]}")

        if not self.device_ids.size():
            error_message = "No devices found during scan."
            logging.error(error_message)
            raise Exception(error_message)

        # Adding devices
        logging.info("Adding devices to the system...")
        self.handles = []
        try:
            self.device_handle_1 = self.nanolib_accessor.addDevice(self.device_ids[0]).getResult()
            logging.info(f"Device 1 added successfully with handle: {self.device_handle_1}")
            self.device_handle_2 = self.nanolib_accessor.addDevice(self.device_ids[1]).getResult()
            logging.info(f"Device 2 added successfully with handle: {self.device_handle_2}")
            self.handles.append(self.device_handle_1)
            self.handles.append(self.device_handle_2)
        except IndexError as e:
            error_message = "IndexError: Not enough devices found to add to the system."
            logging.error(error_message)
            raise Exception(error_message) from e

        # Initializing connection status
        logging.info("Initializing device connection statuses...")
        self.device_1_connected = False
        self.device_2_connected = False
        logging.info("Device connection statuses initialized. Process completed successfully.")

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

    async def homing(self):
        """
        Move both motors to their home position (Position actual value = 0).

        This function checks if motor 1 and motor 2 are already at their home positions.
        If not, it uses the `move_motor` method to move them to Position actual value = 0.
        If they are already at home, it logs a message indicating that no movement is needed.

        Raises:
        ------
        Exception
            If an error occurs during the homing process, an exception is raised
            with an appropriate error message.
        """
        logging.debug("Starting the homing process for both motors...")

        try:
            # Check if both motors are connected
            if not self.device_1_connected or not self.device_2_connected:
                raise Exception("Error: Both motors must be connected before performing homing.")
            logging.info("Both motors are confirmed to be connected.")

            # Read the current positions of both motors
            device_handle_1 = self.device_handle_1
            device_handle_2 = self.device_handle_2

            logging.debug("Reading the initial position of Motor 1...")
            current_abs_pos_1 = self.nanolib_accessor.readNumber(device_handle_1, Nanolib.OdIndex(0x6064, 0x00)).getResult()
            logging.info(f"Motor 1 initial position read as: {current_abs_pos_1}")

            logging.debug("Reading the initial position of Motor 2...")
            current_abs_pos_2 = self.nanolib_accessor.readNumber(device_handle_2, Nanolib.OdIndex(0x6064, 0x00)).getResult()
            logging.info(f"Motor 2 initial position read as: {current_abs_pos_2}")

            # Check if both motors are already at the home position
            if current_abs_pos_1 == 0 and current_abs_pos_2 == 0:
                logging.info("Both motors are already at the home position. No movement needed.")
                return
            elif current_abs_pos_1 == 0:
                logging.info("Motor 1 is already at the home position. Only Motor 2 will be moved.")
            elif current_abs_pos_2 == 0:
                logging.info("Motor 2 is already at the home position. Only Motor 1 will be moved.")

            start_time = time.time()  # Record the start time
            
            async def move_motor_async(MotorNum, pos):
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.move_motor, MotorNum, pos)

            # Define async tasks for moving motors
            max_position = 4_294_967_296  

            # Motor 1 target position calculation
            if current_abs_pos_1 != 0:
                if current_abs_pos_1 < 1_000_000:
                    target_pos_1 = -current_abs_pos_1
                else:
                    target_pos_1 = max_position - current_abs_pos_1
                logging.info(f"Motor 1 target position calculated as: {target_pos_1}")
                logging.info("Moving Motor 1 to home position (0)...")
                motor1_task = move_motor_async(1, target_pos_1)
                logging.info(f"Motor 1 move result: {motor1_task}")

            # Motor 2 target position calculation
            if current_abs_pos_2 != 0:
                if current_abs_pos_2 < 1_000_000:
                    target_pos_2 = -current_abs_pos_2
                else:
                    target_pos_2 = max_position - current_abs_pos_2
                logging.info(f"Motor 2 target position calculated as: {target_pos_2}")
                logging.info("Moving Motor 2 to home position (0)...")
                motor2_task = move_motor_async(2, target_pos_2)  # Use move_motor to move Motor 2 to position 0
                logging.info(f"Motor 2 move result: {motor2_task}")

            results = await asyncio.gather(motor1_task, motor2_task)
            
             # Log results for each motor
            for motor_id, result in enumerate(results, start=1):
                logging.info(f"Motor {motor_id} move result: {result}")

            execution_time = time.time() - start_time
            logging.info(f"Homing process completed in {execution_time:.2f} seconds")

        except Exception as e:
            logging.error(f"Failed to home motors: {e}")
            raise

    def move_motor(self, MotorNum, pos, vel=5):
        """
        Synchronously move the specified motor to a target position at a given velocity in Profile Position mode.

        Parameters:
        ----------
        MotorNum : int
            The motor number to control. Use `1` for `device_handle_1` and `2` for `device_handle_2`.
        pos : int
            The target position for the motor in encoder counts. The range is -16,200 to 16,200 for a full rotation,
            where positive values move the motor counterclockwise and negative values move it clockwise.
            Each encoder count corresponds to approximately 0.088 degrees (360 degrees / 16,200 counts).
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
            # NanoJ Control: 0x2300
            # 0: false, 1: true
            self.nanolib_accessor.writeNumber(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)

            # Set Profile Position mode
            # Modes of operation
            # Modes of operation: 0x6060
            # Modes of operation display: 0x6061
            res = self.nanolib_accessor.writeNumber(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)
            operation = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6061, 0x00))
            logging.info(f"Modes of operation display: {operation.getResult()}")

            # Set velocity (in rpm)
            # Profile velocity: 0x6081
            res = self.nanolib_accessor.writeNumber(device_handle, vel, Nanolib.OdIndex(0x6081, 0x00), 32)
            logging.info(f"{res}")

            # Set target position
            # Target Position: 0x607A
            init_pos = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6064, 0x00))
            initial_position = init_pos.getResult()
            res = self.nanolib_accessor.writeNumber(device_handle, pos, Nanolib.OdIndex(0x607A, 0x00), 32)
            logging.info(f"{res}")

            # Enable operation state
            for command in [6, 7, 0xF]:
                res = self.nanolib_accessor.writeNumber(device_handle, command, Nanolib.OdIndex(0x6040, 0x00), 16)
                logging.info(f"{res}")

            # Move motor to target position
            res = self.nanolib_accessor.writeNumber(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
            logging.info(f"{res}")

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

    def read_motor_position(self, motor_number):
        """
        Read and return the current position of the specified motor.

        Parameters:
        ----------
        motor_number : int
            The motor number to read from. Use `1` for `device_handle_1` and `2` for `device_handle_2`.

        Returns:
        -------
        int
            The current position of the motor in encoder counts.

        Raises:
        ------
        Exception
            If the motor is not connected or if an error occurs during the read operation.
        """
        logging.debug(f"Reading position of Motor {motor_number}")

        # Check if the motor is connected
        if motor_number == 1 and not self.device_1_connected:
            raise Exception("Error: Motor 1 is not connected. Please connect it before reading the position.")
        elif motor_number == 2 and not self.device_2_connected:
            raise Exception("Error: Motor 2 is not connected. Please connect it before reading the position.")

        try:
            # Select the appropriate device handle
            device_handle = self.device_handle_1 if motor_number == 1 else self.device_handle_2
            if not device_handle:
                raise Exception(f"Device handle for Motor {motor_number} not found.")

            # Read the current position from the motor
            # Position actual value: 0x6064
            position_result = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6064, 0x00))
            if position_result.hasError():
                error_message = f"Error: readNumber() - {position_result.getError()}"
                logging.error(error_message)
                raise Exception(error_message)

            # Get and return the current position
            current_position = position_result.getResult()
            logging.info(f"Motor {motor_number} current position: {current_position}")
            return current_position

        except Exception as e:
            logging.error(f"Failed to read position for Motor {motor_number}: {e}")
            raise

    def device_state(self, motor_num=0):
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