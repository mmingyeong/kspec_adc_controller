#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-11-13
# @Filename: adc_calculater.py

import os
import time
import logging

import math

__all__ = ["adc_calculater"]

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("log/adc_calculater.log", encoding='utf-8', errors='ignore'),
        logging.StreamHandler()
    ]
)

class adc_calculater:
    def __init__(self):
        pass

    def zenith_distance(self, alt):
        """
        Calculate the zenith distance given the altitude.

        Parameters:
        altitude (float): Altitude in degrees

        Returns:
        float: Zenith distance in degrees
        """
        return 90 - alt
    
    def return_ang(self, z_dist:float):
        # input: z_dist
        # calculation...
        # dict = {
        #    [motor_1 : ang_1],
        #    [motor_2 : ang_2]    
        #}
        # return dict
        pass
    
    def ang_to_pos(self, ang: float) -> int:
        """
        Convert angle to target motor position in counts.

        Parameters:
        ang (float): Angle in degrees (+ for clockwise, - for counterclockwise)

        Returns:
        int: Target position in counts
        """
        # 16,200 counts correspond to 360 degrees
        counts_per_degree = 16200 / 360
        # Convert angle to counts
        target_position = int(round(ang * counts_per_degree))
        
        return target_position
