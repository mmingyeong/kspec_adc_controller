#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: adc_actions.py

from adc_controller import adc_controller

class adc_actions:
    """adc flow chart"""

    def __init__(self):
        self.controller = adc_controller()
        pass

    def poweron(self):
        self.controller.find_devices()
        self.controller.connect()

    # adc_parking 타겟 관측 끝
    def poweroff(self):
        self.controller.disconnect()
        self.controller.close()
        
    def connect(self):
        self.controller.connect()

    # adc_parking 타겟 관측 끝
    def disconnect(self):
        self.controller.disconnect()

    # adc_init
    def homing(method: int, SwitchSpeed:int, ZeroSpeed:int, set=False):
        """Homing mode의 방법과 속도 값을 설정
        
        Homing? 모터 대기 상태
        Turning? 모터가 가동되고 있는 상태
        """
        # SwitchSpeed: limit switch를 찾아가는 속도
        # ZeroSpeed: limit swtich 내부에서 속도
        
    def homing_status():
        """Homing mode에서 현재 진행 상태를 체크.
        """
        
    # adc_on 타겟 관측 시작
    def activate(opmode: int, timeout: int):
        """각 모드에서 모터 회전을 명령한다.

        Args:
            opmode (int): mode of operation
            - 1: Profile position
            - 3: Profile velocity
            - 6: Homing
            timeout (int): waiting time
        """
        
    # adc_manual 조동 시작, 목표 z 값 수령
    # z가 뭐지?
    def vel_set(vel:int, acc:int, dec:int):
        """Profile velocity mode의 속도값을 설정

        Args:
            vel (int): Target velocity
            acc (int): Profile acceleration
            dec (int): Profile deceleration
        """
    
    # adc_move 추적 시작, 다음 초의 z값 수령, 계산
    def pos_set(pos:int, vel:int, acc:int, dec:int, mode:int):
        """Profile position mode의 위치 및 속도값을 설정

        Args:
            pos (int): Target position
            vel (int): Profile velocity
            acc (int): Profile acceleration
            dec (int): Profile deceleration
            mode (int): 0=absolute mode, 1=relative mode
        """
        
    # adc_off 타겟 관측 끝
    def deactivate(timeout: int):
        """Power state에서 SwitchedOn 상태로 변경하여 모터를 정지

        Args:
            timeout (int): waiting time
        """
        