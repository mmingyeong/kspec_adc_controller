# kspec_adc_controller

[![codecov](https://codecov.io/github/mmingyeong/kspec_adc_controller/graph/badge.svg?token=YOFIOHG94E)](https://codecov.io/github/mmingyeong/kspec_adc_controller)
[![tests](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/tests.yml)
[![ruff-lint](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/ruff-lint.yml/badge.svg)](https://github.com/mmingyeong/kspec_adc_controller/actions/workflows/ruff-lint.yml)
![python>=3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue)

KSPEC-ADC control software for atmospheric dispersion correction during KSPEC observations.  
It drives two prism rotation motors (counter-rotating wedge prisms), computes prism setpoints from telescope metadata (zenith distance; provided by the K-SPEC ICS), and exposes a unified command-style interface for integration with the K-SPEC ICS.

## Hardware (summary)

- 2 × prism rotation axes (counter-rotating wedge prisms)
- Typical deployment: shared fieldbus motor drivers (serial-over-Ethernet or TCP/IP depending on configuration)
- Lookup-table–based setpoints generated from optical simulations (e.g., Zemax)

## Core capabilities

- Centralized control of the ADC motor system (dual-axis)
- Zenith-angle–based prism angle computation using a precomputed lookup table
- Multiple interpolation methods for smooth setpoints (cubic / PCHIP / Akima)
- Asynchronous motion control (non-blocking) for coordinated dual-axis moves
- Initialization and homing procedures for repeatable zero-point calibration
- Monitoring/diagnostics (motor states, positions, errors) with structured logging
- Fault handling with safe stop / error reporting to the ICS

## Command-style API (implemented)

- `connect` — connect to motor(s)
- `disconnect` — disconnect motor(s)
- `homing` — perform homing procedure (velocity-limited)
- `activate` — compute prism angles from zenith distance and apply dual-axis motion
- `stop` — halt motor motion
- `status` — retrieve current motor states (position/connection/error info)
- `power_off` — disconnect devices and release bus resources safely  
  *(exact naming/behavior may vary by integration layer; see `AdcActions`)*

## Installation

Clone the repository:

```bash
git clone https://github.com/mmingyeong/kspec_adc_controller.git
```

## Notes

This project is designed to interface with the K-SPEC ICS through a minimal set of operations.
Hardware communication is encapsulated in AdcController, while the ICS-facing interface is provided by AdcActions.
For development and CI, unit tests are designed to run with mocked hardware dependencies.