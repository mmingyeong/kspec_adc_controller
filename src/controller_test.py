#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong Yang (mmingyeong@kasi.re.kr)
# @Date: 2024-06-26
# @Filename: test.py

import click
import asyncio
from adc_controller import adc_controller

controller = adc_controller()

# 비동기 함수 호출을 위한 헬퍼 함수
def run_async(async_func):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        return loop.create_task(async_func)
    return loop.run_until_complete(async_func)

@click.group()
def cli():
    """Command Line Interface to control the motor."""
    pass

@cli.command()
@click.option('--MotorNum', type=int, default=2, help="Specify the motor number (1 or 2)")
@click.option('--pos', type=int, default=4000, help="The target position for move_motor command (in encoder counts)")
@click.option('--vel', type=int, default=100, help="The target velocity in RPM for the motor (default: 100 RPM)")
def move_motor(MotorNum, pos, vel):
    """Move the specified motor to a target position at a given velocity."""
    click.echo(f"Moving Motor {MotorNum} to position {pos} with velocity {vel}")
    run_async(controller.move_motor(MotorNum=MotorNum, pos=pos, vel=vel))

@cli.command()
@click.option('--MotorNum', type=int, required=True, help="Specify the motor number (1 or 2)")
def stop_motor(MotorNum):
    """Stop the specified motor."""
    click.echo(f"Stopping Motor {MotorNum}")
    run_async(controller.stop_motor(MotorNum=MotorNum))

@cli.command()
def connect():
    """Connect to the motors and check connection state."""
    controller.find_devices()
    controller.connect()
    connection_state = controller.checkConnectionState()
    click.echo(f"Connection State: {connection_state}")
    # 연결 상태를 확인한 후에도 유지하므로 disconnect/close를 수행하지 않음

@cli.command()
def close():
    """Disconnect and close the connection to the motors."""
    controller.disconnect()
    controller.close()
    click.echo("Disconnected and closed connection to motors.")

if __name__ == "__main__":
    cli()
