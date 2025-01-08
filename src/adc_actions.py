#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_actions.py

import asyncio
from adc_controller import AdcController
from adc_logger import AdcLogger
from adc_calc_angle import ADCCalc

__all__ = ["AdcActions"]


class AdcActions:
    """Class to manage ADC actions including connecting, powering on/off, and motor control."""

    def __init__(self, logger=None):
        """
        Initialize the AdcActions class and set up the ADC controller.

        Parameters
        ----------
        logger : AdcLogger, optional
            Logger instance for logging operations. If None, a default AdcLogger instance is created.
        """
        self.logger = logger or AdcLogger(
            __file__
        )  # Use provided logger or create a default one
        self.logger.debug("Initializing AdcActions class.")
        self.controller = AdcController(self.logger)
        self.controller.find_devices()
        self.calculator = ADCCalc(self.logger) # method 변경 line

    def connect(self):
        """
        Connect to the ADC controller.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        self.logger.info("Connecting to devices.")
        response = {}
        try:
            self.controller.connect()
            response = {
                "status": "success",
                "message": "Connected to devices."
            }
            self.logger.info("Connection successful.")
        except Exception as e:
            self.logger.error(f"Error in connect: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return response

    def _generate_response(self, status: str, message: str, **kwargs) -> dict:
        """
        Generate a response dictionary.

        Parameters
        ----------
        status : str
            Status of the operation ('success' or 'error').
        message : str
            Message describing the operation result.
        **kwargs : dict
            Additional data to include in the response.

        Returns
        -------
        dict
            A dictionary representing the response.
        """
        response = {"status": status, "message": message}
        response.update(kwargs)
        return response

    def status(self, motor_num: int = 0) -> dict:
        """
        Get the status of a specified motor.

        Parameters
        ----------
        motor_num : int, optional
            The motor number to check. Default is 0.

        Returns
        -------
        dict
            A dictionary indicating the status or any error encountered.
        """
        self.logger.info(f"Retrieving status for motor {motor_num}.")
        try:
            state = self.controller.device_state(motor_num)
            self.logger.info(f"Motor {motor_num} status: {state}")
            return self._generate_response(
                "success", f"Motor {motor_num} status retrieved.", DeviceState=state
            )
        except Exception as e:
            self.logger.error(f"Error in status: {e}")
            return self._generate_response("error", str(e), motor_num=motor_num)

    async def move(self, motor_id, pos_count, vel_set=1):
        """
        Move motors to a target position with the specified velocity.

        Parameters
        ----------
        motor_id : int
            The motor ID to move. If `0`, both motors 1 and 2 are moved simultaneously.
        pos_count : int
            The target position for the motor(s).
        vel_set : int, optional
            The velocity at which to move the motor(s). Defaults to 1.

        Returns
        -------
        dict
            A response dictionary indicating success or failure, along with results.
        """
        try:
            if motor_id == 0:
                self.logger.debug(
                    f"Starting simultaneous move for motors 1 and 2 to position {pos_count} with velocity {vel_set}."
                )

                async def move_motor_async(motor_num, position, velocity):
                    """
                    Asynchronously move a single motor using the controller.

                    Parameters
                    ----------
                    motor_num : int
                        The motor ID to move.
                    position : int
                        The target position for the motor.
                    velocity : int
                        The velocity at which to move the motor.

                    Returns
                    -------
                    object
                        The result of the motor movement operation.
                    """
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, self.controller.move_motor, motor_num, position, velocity
                    )

                motor1_task = move_motor_async(1, pos_count, vel_set)
                motor2_task = move_motor_async(2, pos_count, vel_set)

                # Wait for both motors to complete
                results = await asyncio.gather(motor1_task, motor2_task)

                self.logger.info("Both motors moved successfully.")
                return {
                    "status": "success",
                    "message": "Motors activated successfully.",
                    "motor_1": results[0],
                    "motor_2": results[1],
                }
            else:
                self.logger.debug(
                    f"Moving motor {motor_id} to position {pos_count} with velocity {vel_set}."
                )
                result = self.controller.move_motor(motor_id, pos_count, vel_set)
                self.logger.info(f"Motor {motor_id} moved successfully.")
                return {
                    "status": "success",
                    "message": f"Motor {motor_id} activated successfully.",
                    "result": result,
                }
        except Exception as e:
            self.logger.error(f"Error moving motor {motor_id}: {e}", exc_info=True)
            return {
                "status": "failure",
                "message": f"Error activating motor {motor_id}.",
                "error": str(e),
            }
        
    # stop motor
    async def stop(self, motor_id):
        try:
            if motor_id==0:
                self.logger.debug("Stopping both motors.")
                async def stop_motor_async(motor_num):
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, self.controller.stop_motor, motor_num)
                motor1_task = stop_motor_async(1)
                motor2_task = stop_motor_async(2)
                results = await asyncio.gather(motor1_task, motor2_task)
                self.logger.info("Both motors stopped successfully.")
                return {
                    "status": "success",
                    "message": "Both motors stopped successfully.",
                    "motor_1": results[0],
                    "motor_2": results[1],
                }
            elif motor_id in [1, 2]:
                self.logger.debug(f"Stopping motor {motor_id}.")
                result = self.controller.stop_motor(motor_id)
                self.logger.info(f"Motor {motor_id} stopped successfully.")
                return {
                    "status": "success",
                    "message": f"Motor {motor_id} stopped successfully.",
                    "result": result,
                }
            else:
                raise ValueError(f"Invalid motor ID: {motor_id}")
        except Exception as e:
            self.logger.error(f"Error stopping motor {motor_id}: {e}", exc_info=True)
            return {
                "status": "failure",
                "message": f"Error stopping motor {motor_id}.",
                "error": str(e),
            }
        

    async def activate(self, za, vel_set=1) -> dict:
        """
        Activate both motors simultaneously with specified velocities.

        Parameters
        ----------
        za_angle : float or array(float)
            Input zenith angle (degree)

        Returns
        -------
        dict
            A dictionary indicating the success or failure of the activation.
        """
        self.logger.info(f"Activating motors. za_angle={za}")
        vel = vel_set  # deafault

        ang = self.calculator.calc_from_za(za)
        pos = self.calculator.degree_to_count(ang)

        try:
            #self.controller.connect()

            async def move_motor_async(motor_num, position, velocity):
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self.controller.move_motor, motor_num, position, velocity
                )

            motor1_task = move_motor_async(1, -pos, vel) # motor 1 L4 위치, 시계 방향 회전전
            motor2_task = move_motor_async(2, pos, vel) # motor 2 L3 위치, 반시계 방향 회전

            results = await asyncio.gather(motor1_task, motor2_task)

            self.logger.info("Motors activated successfully.")
            return self._generate_response(
                "success",
                "Motors activated successfully.",
                motor_1=results[0],
                motor_2=results[1],
            )
        except Exception as e:
            self.logger.error(f"Failed to activate motors: {e}")
            return self._generate_response("error", str(e))

    async def homing(self):
        """
        Perform a homing operation with the motor controller.

        The operation attempts to initialize the motor to its home position.

        Returns:
        -------
        dict
            JSON-like dictionary with the following structure:
            {
                "status": "success" | "error",
                "message": str,  # Only present if "status" is "error".
            }
        """
        self.logger.info("Starting homing operation.")
        response = {}
        try:
            self.logger.debug("Calling homing method on controller.")
            await self.controller.homing()
            response = {"status": "success"}
            self.logger.info("Homing completed successfully.")
        except Exception as e:
            self.logger.error(f"Error in homing operation: {str(e)}", exc_info=True)
            response = {
                "status": "error",
                "message": str(e),
            }
        return response

    async def zeroing(self):
        """
        Perform a zeroing operation by adjusting motor positions.

        This operation sets the motor's position offsets as specified.

        Returns:
        -------
        dict
            JSON-like dictionary with the following structure:
            {
                "status": "success" | "error",
                "message": str,  # Only present if "status" is "error".
            }
        """
        zero_offset_motor1 = 8000  # Adjust this value based on calibration.
        zero_offset_motor2 = 2000   # Adjust this value based on calibration.

        self.logger.info("Starting zeroing operation.")
        response = {}
        try:
            self.logger.debug("Initiating homing as part of zeroing.")
            await self.controller.homing()
            self.logger.debug(f"Moving motor 1 by {zero_offset_motor1} counts.")
            self.logger.debug(f"Moving motor 2 by {zero_offset_motor2} counts.")
            await asyncio.gather(
                asyncio.to_thread(self.controller.move_motor, 1, zero_offset_motor1, 5),
                asyncio.to_thread(self.controller.move_motor, 2, zero_offset_motor2, 5)
            )
            response = {"status": "success"}
            self.logger.info("Zeroing completed successfully.")
        except Exception as e:
            self.logger.error(f"Error in zeroing operation: {str(e)}", exc_info=True)
            response = {
                "status": "error",
                "message": str(e),
            }
        return response

    def disconnect(self):
        """
        Disconnect from the ADC controller.

        Returns:
        -------
        str
            A JSON string indicating the success or failure of the operation.
        """
        self.logger.info("Disconnecting from devices.")
        response = {}
        try:
            self.controller.disconnect()
            response = {
                "status": "success",
                "message": "Disconnected from devices."
            }
            self.logger.info("Disconnection successful.")
        except Exception as e:
            self.logger.error(f"Error in disconnect: {str(e)}")
            response = {
                "status": "error",
                "message": str(e)
            }
        return response

    def power_off(self) -> dict:
        """
        Power off and disconnect from all devices.

        Returns
        -------
        dict
            A dictionary indicating the success or failure of the operation.
        """
        self.logger.info("Powering off and disconnecting from devices.")
        try:
            self.controller.disconnect()
            self.controller.close()
            self.logger.info("Power off successful.")
            return self._generate_response(
                "success", "Power off and devices disconnected."
            )
        except Exception as e:
            self.logger.error(f"Error in power off: {e}")
            return self._generate_response("error", str(e))

