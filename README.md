# KSPEC ADC Controller

[![codecov](https://codecov.io/github/mmingyeong/kspec_adc_controller/graph/badge.svg?token=YOFIOHG94E)](https://codecov.io/github/mmingyeong/kspec_adc_controller)
[![tests](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/tests.yml/badge.svg)](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/tests.yml)
[![ruff-lint](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/ruff-lint.yml/badge.svg)](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/ruff-lint.yml)
![python>=3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue)

## Overview

`kspec_adc_controller` is a Python-based control software for the **K-SPEC Atmospheric Dispersion Corrector (ADC)**.  
It provides remote, real-time control of the ADC system, which compensates for atmospheric dispersion during spectroscopic observations by driving a pair of counter-rotating wedge prism motors.

The software is designed to operate as part of the **K-SPEC Instrument Control System (ICS)**, translating telescope metadata (e.g., zenith distance) into precise prism motor setpoints and executing coordinated motor commands with logging and safety checks.

## Key Capabilities

- **Atmospheric dispersion correction** using two counter-rotating prism motors
- **Zenith-angle–based prism angle computation** via precomputed lookup tables
- **Asynchronous motor control** for non-blocking operations
- **Initialization and homing procedures** for repeatable zero-point calibration
- **Status monitoring and diagnostics** with structured logging
- **Fault handling** for communication and motion errors

## Software Structure

The control system is organized into three main layers:

- **`AdcActions`**  
  ICS-facing command interface that validates inputs, orchestrates operations, and returns standardized responses.

- **`AdcController`**  
  Core hardware control layer responsible for device discovery, connection management, motor motion, homing, parking, and safety handling.

- **`ADCCalc` / `AdcLogger`**  
  Utility modules for prism-angle computation (with multiple interpolation methods) and consistent system logging.

## Intended Use

This package is intended for astronomers and engineers operating the K-SPEC instrument, and for development, testing, and integration of ADC control logic within the K-SPEC software ecosystem.
