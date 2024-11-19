#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_actions.py

import asyncio
import json
import logging
from adc_controller import adc_controller

__all__ = ["adc_actions"]

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("log/adc_action.log", encoding='utf-8', errors='ignore'),
        logging.StreamHandler()
    ]
)

class adc_actions:
    """Class to manage ADC actions including connecting, powering on/off, and motor control."""

    def __init__(self):
        """Initialize the adc_actions class and set up the ADC controller."""
        logging.debug("Initializing adc_actions class.")
        self.controller = adc_controller()

    def poweron(self):
        """
        Power on and connect to all devices.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        logging.info("Powering on and connecting to devices.")
        response = {}
        try:
            self.controller.find_devices()
            self.controller.connect()
            response = {
                "status": "success",
                "message": "Power on and devices connected."
            }
            logging.info("Power on successful.")
        except Exception as e:
            logging.error(f"Error in poweron: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return json.dumps(response)

    def poweroff(self):
        """
        Power off and disconnect from all devices.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        logging.info("Powering off and disconnecting from devices.")
        response = {}
        try:
            self.controller.disconnect()
            self.controller.close()
            response = {
                "status": "success",
                "message": "Power off and devices disconnected."
            }
            logging.info("Power off successful.")
        except Exception as e:
            logging.error(f"Error in poweroff: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return json.dumps(response)

    def connect(self):
        """
        Connect to the ADC controller.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        logging.info("Connecting to devices.")
        response = {}
        try:
            self.controller.connect()
            response = {
                "status": "success",
                "message": "Connected to devices."
            }
            logging.info("Connection successful.")
        except Exception as e:
            logging.error(f"Error in connect: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return json.dumps(response)

    def disconnect(self):
        """
        Disconnect from the ADC controller.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        logging.info("Disconnecting from devices.")
        response = {}
        try:
            self.controller.disconnect()
            response = {
                "status": "success",
                "message": "Disconnected from devices."
            }
            logging.info("Disconnection successful.")
        except Exception as e:
            logging.error(f"Error in disconnect: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return json.dumps(response)

    def status(self, motor_num=0):
        """
        Get the status of a specified motor.

        Parameters:
        ----------
        motor_num : int, optional
            The motor number to check. Default is 0.

        Returns:
        -------
        str
            A JSON string indicating the status or any error encountered.
        """
        logging.info(f"Retrieving status for motor {motor_num}.")
        response = {}
        try:
            state = self.controller.DeviceState(motor_num)
            response = {
                "status": "success",
                "message": f"Motor {motor_num} status retrieved.",
                "DeviceState": state
            }
            logging.info(f"Motor {motor_num} status: {state}")
        except Exception as e:
            logging.error(f"Error in status: {str(e)}")
            response = {
                "status": "error",
                "message": str(e),
                "motor_num": motor_num
            }
        return json.dumps(response)

    async def activate(self, pos:int, vel1=5, vel2=5):
        """
        Activate both motors simultaneously with specified velocities.

        Parameters:
        ----------
        vel1 : int, optional
            The target velocity for motor 1. Default is 5.
        vel2 : int, optional
            The target velocity for motor 2. Default is 5.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the activation.
        """
        logging.info("Activating motors.")
        response = {}

        async def move_motor_async(MotorNum, pos, vel):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.controller.move_motor, MotorNum, pos, vel)

        try:
            motor1_task = move_motor_async(1, pos, vel1)
            motor2_task = move_motor_async(2, pos, vel2)

            results = await asyncio.gather(motor1_task, motor2_task)

            response = {
                "status": "success",
                "message": "Motors activated successfully.",
                "motor_1": results[0],
                "motor_2": results[1]
            }
            logging.info("Motors activated successfully.")
        except Exception as e:
            logging.error(f"Failed to activate motors: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }

        return json.dumps(response)

    def homing(self):
        """
        Perform homing operation with specified parameters.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        logging.info("Starting homing operation.")
        response = {}
        try:
            state = self.controller.homing()
            response = {
                "status": "success",
                "message": "Homing completed.",
            }
            logging.info("Homing completed successfully.")
        except Exception as e:
            logging.error(f"Error in homing: {str(e)}")
            response = {
                "status": "error",
                "message": str(e),
            }
        return json.dumps(response)
