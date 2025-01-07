#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_controller.py

import os
import json
import time
import asyncio
from nanotec_nanolib import Nanolib

__all__ = ["AdcController"]


class AdcController:
    """
    Interacts with a KSPEC ADC system over a serial port.

    Attributes
    ----------
    CONFIG_FILE : str
        Path to the JSON configuration file.
    logger : logging.Logger
        Logger instance for logging messages.
    nanolib_accessor : Nanolib.NanoLibAccessor
        Instance for accessing the Nanolib API.
    devices : dict
        Dictionary for managing device handles and connection states.
    selected_bus_index : int
        Index of the selected bus hardware.
    """

    CONFIG_FILE = "etc/adc_config.json"

    def __init__(self, logger):
        """
        Initializes the AdcController.

        Parameters
        ----------
        logger : logging.Logger
            Logger instance for debugging and informational logs.
        """
        self.logger = logger
        self.nanolib_accessor = Nanolib.getNanoLibAccessor()
        self.logger.debug("Initializing AdcController")
        self.devices = {
            1: {"handle": None, "connected": False},
            2: {"handle": None, "connected": False},
        }
        self.selected_bus_index = self._load_selected_bus_index()
        self.home_position = None

    def _load_selected_bus_index(self) -> int:
        """
        Loads the selected bus index from a JSON configuration file.

        Returns
        -------
        int
            The selected bus index from the configuration file.
            Defaults to 1 if the file does not exist or is invalid.

        Notes
        -----
        If the configuration file is missing or cannot be read, a warning is logged,
        and the default value is used.
        """
        default_index = 1
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as file:
                    config = json.load(file)
                    return config.get("selected_bus_index", default_index)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error reading configuration file: {e}")
        else:
            self.logger.warning(
                f"Configuration file {self.CONFIG_FILE} not found. Using default index {default_index}."
            )
        return default_index

    def find_devices(self):
        """
        Finds devices connected to the selected bus and initializes them.

        Raises
        ------
        Exception
            If no bus hardware IDs are found or if there is an error during initialization.
        """
        self.logger.info("Starting the process to find devices...")
        list_available_bus = self.nanolib_accessor.listAvailableBusHardware()
        if list_available_bus.hasError():
            raise Exception(
                f"Error: listAvailableBusHardware() - {list_available_bus.getError()}"
            )

        bus_hardware_ids = list_available_bus.getResult()
        if not bus_hardware_ids.size():
            raise Exception("No bus hardware IDs found.")

        for i, bus_id in enumerate(bus_hardware_ids):
            self.logger.info(
                f"ID {i}: {bus_id.toString() if hasattr(bus_id, 'toString') else str(bus_id)}"
            )

        ind = self.selected_bus_index
        self.adc_motor_id = bus_hardware_ids[ind]
        self.logger.info(f"Selected bus hardware ID: {self.adc_motor_id}")

        # Configure options
        self.adc_motor_options = Nanolib.BusHardwareOptions()
        self.adc_motor_options.addOption(
            Nanolib.Serial().BAUD_RATE_OPTIONS_NAME,
            Nanolib.SerialBaudRate().BAUD_RATE_115200,
        )
        self.adc_motor_options.addOption(
            Nanolib.Serial().PARITY_OPTIONS_NAME, Nanolib.SerialParity().EVEN
        )

        # Open bus hardware
        open_bus = self.nanolib_accessor.openBusHardwareWithProtocol(
            self.adc_motor_id, self.adc_motor_options
        )
        if open_bus.hasError():
            raise Exception(
                f"Error: openBusHardwareWithProtocol() - {open_bus.getError()}"
            )

        # Scan devices
        scan_devices = self.nanolib_accessor.scanDevices(
            self.adc_motor_id, callbackScanBus
        )
        if scan_devices.hasError():
            raise Exception(f"Error: scanDevices() - {scan_devices.getError()}")

        self.device_ids = scan_devices.getResult()
        if not self.device_ids.size():
            raise Exception("No devices found during scan.")

        for i, device_id in enumerate(self.device_ids):
            if i + 1 in self.devices:
                handle_result = self.nanolib_accessor.addDevice(device_id)
                if handle_result.hasError():
                    raise Exception(
                        f"Error adding device {i + 1}: {handle_result.getError()}"
                    )
                self.devices[i + 1]["handle"] = handle_result.getResult()
                self.logger.info(f"Device {i + 1} added successfully.")

    def connect(self, motor_number=0):
        """
        Connects the specified motor or all motors to the bus.

        Parameters
        ----------
        motor_number : int, optional
            The motor number to connect (default is 0, which connects all motors).
        """
        self._set_connection_state(motor_number, connect=True)

    def disconnect(self, motor_number=0):
        """
        Disconnects the specified motor or all motors from the bus.

        Parameters
        ----------
        motor_number : int, optional
            The motor number to disconnect (default is 0, which disconnects all motors).
        """
        self._set_connection_state(motor_number, connect=False)

    def _set_connection_state(self, motor_number, connect):
        """
        Generalized method for connecting or disconnecting devices.

        Parameters
        ----------
        motor_number : int
            The motor number to connect or disconnect.
        connect : bool
            True to connect the motor, False to disconnect.

        Raises
        ------
        ValueError
            If the motor number is invalid.
        Exception
            If there is an error during connection or disconnection.
        """
        try:
            if motor_number not in [0, 1, 2]:
                raise ValueError("Invalid motor number. Must be 0, 1, or 2.")

            motors = [motor_number] if motor_number != 0 else [1, 2]
            for motor in motors:
                device = self.devices[motor]
                if connect:
                    if device["connected"]:
                        self.logger.info(f"Device {motor} is already connected.")
                    else:
                        result = self.nanolib_accessor.connectDevice(device["handle"])
                        if result.hasError():
                            raise Exception(
                                f"Error: connectDevice() - {result.getError()}"
                            )
                        device["connected"] = True
                        self.logger.info(f"Device {motor} connected successfully.")
                else:
                    if device["connected"]:
                        result = self.nanolib_accessor.disconnectDevice(
                            device["handle"]
                        )
                        if result.hasError():
                            raise Exception(
                                f"Error: disconnectDevice() - {result.getError()}"
                            )
                        device["connected"] = False
                        self.logger.info(f"Device {motor} disconnected successfully.")
                    else:
                        self.logger.info(f"Device {motor} was not connected.")

        except Exception as e:
            self.logger.exception(
                f"An error occurred while {'connecting' if connect else 'disconnecting'}: {e}"
            )
            raise

    def close(self):
        """
        Closes the bus hardware connection.

        Raises
        ------
        Exception
            If there is an error during closing the bus hardware.
        """
        self.logger.debug("Closing all devices...")
        close_result = self.nanolib_accessor.closeBusHardware(self.adc_motor_id)
        if close_result.hasError():
            raise Exception(f"Error: closeBusHardware() - {close_result.getError()}")
        self.logger.info("Bus hardware closed successfully.")


    def move_motor(self, motor_id, pos, vel):
        """
        Synchronously move the specified motor to a target position
        at a given velocity in Profile Position mode.

        Parameters
        ----------
        motor_id : int
            The identifier of the motor to be moved.
        pos : int
            The target position for the motor.
        vel : int, optional
            The velocity for the movement.

        Returns
        -------
        dict
            A dictionary containing the initial and final positions,
            position change, and execution time of the movement.

        Raises
        ------
        Exception
            If the motor is not connected or an error occurs during movement.
        """
        self.logger.debug(
            f"Moving Motor {motor_id} to position {pos} with velocity {vel}"
        )
        device = self.devices.get(motor_id)

        if not device or not device["connected"]:
            raise Exception(
                f"Error: Motor {motor_id} is not connected. Please connect it before moving."
            )

        try:
            device_handle = device["handle"]
            start_time = time.time()

            # Set Profile Position mode
            self.nanolib_accessor.writeNumber(
                device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8
            )

            # Set velocity and target position
            self.nanolib_accessor.writeNumber(
                device_handle, vel, Nanolib.OdIndex(0x6081, 0x00), 32
            )
            initial_position = self.read_motor_position(motor_id)
            self.nanolib_accessor.writeNumber(
                device_handle, pos, Nanolib.OdIndex(0x607A, 0x00), 32
            )

            # Enable and execute movement
            for command in [6, 7, 0xF]:
                self.nanolib_accessor.writeNumber(
                    device_handle, command, Nanolib.OdIndex(0x6040, 0x00), 16
                )
            self.nanolib_accessor.writeNumber(
                device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16
            )

            # Wait for movement completion
            while True:
                status_word = self.nanolib_accessor.readNumber(
                    device_handle, Nanolib.OdIndex(0x6041, 0x00)
                )
                if (status_word.getResult() & 0x1400) == 0x1400:
                    break
                time.sleep(1)

            final_position = self.read_motor_position(motor_id)
            return {
                "initial_position": initial_position,
                "final_position": final_position,
                "position_change": final_position - initial_position,
                "execution_time": time.time() - start_time,
            }

        except Exception as e:
            self.logger.error(f"Failed to move Motor {motor_id}: {e}")
            raise

    def stop_motor(self, motor_id):
        """
        Stop the specified motor using Controlword.
        
        Parameters
        ----------
        motor_id : int
            The identifier of the motor to be stopped.
        
        Returns
        -------
        dict
            Dictionary containing the motor stop result, including status and error code if any.
        """
        self.logger.debug(f"Stopping Motor {motor_id}")

        device = self.devices.get(motor_id)

        if not device or not device["connected"]:
            raise Exception(f"Error: Motor {motor_id} is not connected. Please connect it before stopping.")

        try:
            # Step 1: 장치 핸들 가져오기
            device_handle = device["handle"]
            if device_handle is None:
                self.logger.error(f"Motor {motor_id}: Device not found.")
                raise ValueError(f"Motor {motor_id} not connected.")

            # Step 2: Controlword 설정 - HALT 비트를 1로 설정하여 멈춤 명령
            self.nanolib_accessor.writeNumber(device_handle, 0x1F, Nanolib.OdIndex(0x6040, 0x00), 16)  # Enable motor
            self.nanolib_accessor.writeNumber(device_handle, 0x01, Nanolib.OdIndex(0x6040, 0x00), 16)  # HALT command

            self.logger.info(f"Motor {motor_id} stopped successfully.")

            # Step 3: 상태 확인
            status_word = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x6041, 0x00))
            result = status_word.getResult()
            
            if result & 0x8000:  # Check for halt status (HALT bit in the statusword)
                self.logger.info(f"Motor {motor_id} halted successfully.")
                return {
                    "status": "success",
                    "error_code": None
                }
            else:
                self.logger.error(f"Motor {motor_id} halt failed.")
                return {
                    "status": "failed",
                    "error_code": status_word
                }
        
        except Exception as e:
            self.logger.error(f"Motor {motor_id}: Error during stopping.")
            raise e

    def homing(self, motor_id: int):
        """
        Perform homing for a specified motor based on sensor value changes.

        Parameters
        ----------
        motor_id : int
            The ID of the motor to perform homing on.
        """
        device = self.devices.get(motor_id)
        self.logger.info(f"device: {device}")
        if not device:
            self.logger.error(f"Motor with ID {motor_id} not found.")
            return
        
        self.home_position_motor1 = None
        self.home_position_motor2 = None

        device_handle = device["handle"]
        home_position_motor1 = self.home_position_motor1  # home position for motor ID 1
        home_position_motor2 = self.home_position_motor2  # home position for motor ID 2
        self.logger.info(f"device_handle: {device_handle}")
        vel = 5

        initial_raw_value = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x3240, 5)).getResult()

        try:
            if motor_id == 1:
                home_position = home_position_motor1
            elif motor_id == 2:
                home_position = home_position_motor2
            else:
                self.logger.error(f"Invalid motor ID {motor_id}.")
                return

            if home_position is None:
                self.logger.info("Home position not set. Initializing homing process...")

                # Move motor while monitoring sensor values
                # Set Profile Position mode
                self.nanolib_accessor.writeNumber(
                    device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8
                )

                # Set velocity and target position
                self.nanolib_accessor.writeNumber(
                    device_handle, vel, Nanolib.OdIndex(0x6081, 0x00), 32
                )
                pos = 16200  # 1 바퀴
                self.nanolib_accessor.writeNumber(
                    device_handle, pos, Nanolib.OdIndex(0x607A, 0x00), 32
                )

                # Enable and execute movement
                for command in [6, 7, 0xF]:
                    self.nanolib_accessor.writeNumber(
                        device_handle, command, Nanolib.OdIndex(0x6040, 0x00), 16
                    )
                self.nanolib_accessor.writeNumber(
                    device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16
                )

                # Monitor Raw Value in real time
                print("\nMonitoring Raw Value in real time (Press Ctrl+C to stop):")
                while True:
                    raw_value = self.nanolib_accessor.readNumber(device_handle, Nanolib.OdIndex(0x3240, 5)).getResult()
                    binary_raw = format(raw_value, "032b")  # Convert to 32-bit binary format
                    if initial_raw_value != raw_value:
                        self.stop_motor(motor_id)
                        print(f"FINEAL Raw Value: {binary_raw}")
                        break

                    time.sleep(0.1)  # Adjust the monitoring interval as needed

                # Save the current position as the home position
                if motor_id == 1:
                    self.home_position_motor1 = self.read_motor_position(motor_id)
                    self.logger.info(f"Home position for motor ID 1 set to: {self.home_position_motor1}")
                elif motor_id == 2:
                    self.home_position_motor2 = self.read_motor_position(motor_id)
                    self.logger.info(f"Home position for motor ID 2 set to: {self.home_position_motor2}")

            else:
                if motor_id == 1:
                    self.logger.info(f"Home position already set for motor ID {motor_id}. Moving to home position...")
                    self.move_motor(motor_id, self.home_position_motor1, vel)  # Move motor to the home position
                elif motor_id == 2:
                    self.logger.info(f"Home position already set for motor ID {motor_id}. Moving to home position...")
                    self.move_motor(motor_id, self.home_position_motor2, vel)  # Move motor to the home position

        except Exception as e:
            self.logger.error(f"Error during homing process: {e}")


    def read_motor_position(self, motor_id: int) -> int:
        """
        Read and return the current position of the specified motor.

        Parameters
        ----------
        motor_id : int
            The identifier of the motor.

        Returns
        -------
        int
            The current position of the motor.

        Raises
        ------
        Exception
            If the motor is not connected or an error occurs while reading
            the position.
        """
        device = self.devices.get(motor_id)
        if not device or not device["connected"]:
            raise Exception(
                f"Error: Motor {motor_id} is not connected. Please connect it before reading the position."
            )

        try:
            device_handle = device["handle"]
            position_result = self.nanolib_accessor.readNumber(
                device_handle, Nanolib.OdIndex(0x6064, 0x00)
            )
            if position_result.hasError():
                raise Exception(f"Error: readNumber() - {position_result.getError()}")
            return position_result.getResult()

        except Exception as e:
            self.logger.error(f"Failed to read position for Motor {motor_id}: {e}")
            raise 

    def device_state(self, motor_id=0):
        """
        Retrieve the state of the specified motor or both motors.

        Parameters
        ----------
        motor_id : int, optional
            The identifier of the motor (default is 0). Use:
            - 0 to check the state of both motors,
            - 1 for motor 1,
            - 2 for motor 2.

        Returns
        -------
        dict
            A dictionary containing the connection states of the motors.

        Raises
        ------
        ValueError
            If an invalid motor number is provided.
        """
        if motor_id not in [0, 1, 2]:
            raise ValueError(
                "Invalid motor number. Use 0 for both motors, 1 for motor 1, or 2 for motor 2."
            )

        res = {}
        motors = [motor_id] if motor_id in [1, 2] else [1, 2]
        for motor in motors:
            position_state = self.read_motor_position(motor)
            device = self.devices.get(motor)
            connection_state = None
            if device and device["handle"]:
                connection_state = self.nanolib_accessor.checkConnectionState(
                    device["handle"]
                ).getResult()

            res[f"motor{motor}"] = {
                "position_state": position_state,
                "connection_state": bool(connection_state)
                if connection_state is not None
                else None
            }

        self.logger.info(f"Device states: {res}")
        return res


class ScanBusCallback(Nanolib.NlcScanBusCallback):
    """
    Callback class for handling bus scanning progress and results.
    """

    def __init__(self):
        super().__init__()

    def callback(self, info, devicesFound, data):
        """
        Handles scanning events.

        Parameters
        ----------
        info : Nanolib.BusScanInfo
            Information about the current scan state.
        devicesFound : int
            The number of devices found during the scan.
        data : int
            Additional data relevant to the scan event.

        Returns
        -------
        Nanolib.ResultVoid
            The result indicating the callback execution.
        """
        if info == Nanolib.BusScanInfo_Start:
            print("Scan started.")
        elif info == Nanolib.BusScanInfo_Progress:
            if (data & 1) == 0:
                print(".", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Finished:
            print("\nScan finished.")

        return Nanolib.ResultVoid()


callbackScanBus = ScanBusCallback()  # Nanolib 2021


"""

    async def homing(self):
        """"""
        Move both motors to their home position (Position actual value = 0).

        This method checks the connection state of each motor and moves them to
        the home position concurrently if they are not already in position.
        It logs the process and measures the execution time.

        Returns
        -------
        None
            If all motors are successfully moved to the home position or
            already at the home position.

        Raises
        ------
        Exception
            If any motor is not connected or if there is an error during
            the homing process.
        """"""
        self.logger.debug("Starting the homing process for both motors...")
        start_time = time.time()
        target_velocity = 1

        async def move_motor_async(motor_num, position, velocity):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.move_motor, motor_num, position, velocity
            )

        try:
            # Check if all required devices are connected
            for motor_id, device in self.devices.items():
                if not device["connected"]:
                    raise Exception(
                        f"Error: Motor {motor_id} is not connected. Please connect it before homing."
                    )

            tasks = []
            max_position = 4_294_967_296

            for motor_id, device in self.devices.items():
                current_pos = self.read_motor_position(motor_id)
                if current_pos != 0:
                    target_pos = (
                        -current_pos
                        if current_pos < 1_000_000
                        else max_position - current_pos
                    )
                    self.logger.info(
                        f"Motor {motor_id} target position calculated as: {target_pos}"
                    )
                    tasks.append(
                        move_motor_async(motor_id, target_pos, target_velocity)
                    )

            if not tasks:
                self.logger.info(
                    "All motors are already at their home position. No movement needed."
                )
                return

            # Execute tasks concurrently
            results = await asyncio.gather(*tasks)
            for motor_id, result in enumerate(results, start=1):
                self.logger.info(f"Motor {motor_id} move result: {result}")

            execution_time = time.time() - start_time
            self.logger.info(
                f"Homing process completed in {execution_time:.2f} seconds"
            )

        except Exception as e:
            self.logger.error(f"Failed to home motors: {e}")
            raise

"""