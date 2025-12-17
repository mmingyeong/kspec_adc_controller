import importlib

import pytest


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.debugs = []
        self.warnings = []
        self.errors = []

    def info(self, msg):
        self.infos.append(msg)

    def debug(self, msg):
        self.debugs.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)

    def error(self, msg):
        self.errors.append(msg)


class FakeController:
    def __init__(self, logger):
        self.logger = logger
        self.find_devices_called = 0
        self.connect_called = 0
        self.disconnect_called = 0
        self.close_called = 0
        self.device_state_called = []
        self.move_motor_calls = []
        self.stop_motor_calls = []
        self.homing_calls = []
        self.parking_calls = []
        self.zeroing_calls = []

    def find_devices(self):
        self.find_devices_called += 1

    def connect(self):
        self.connect_called += 1

    def disconnect(self):
        self.disconnect_called += 1

    def close(self):
        self.close_called += 1

    def device_state(self, motor_num):
        self.device_state_called.append(motor_num)
        return {"motor": motor_num, "ok": True}

    def move_motor(self, motor_id, pos, vel):
        self.move_motor_calls.append((motor_id, pos, vel))
        return {"motor_id": motor_id, "pos": pos, "vel": vel}

    def stop_motor(self, motor_id):
        self.stop_motor_calls.append(motor_id)
        return {"motor_id": motor_id, "stopped": True}

    async def homing(self, vel):
        self.homing_calls.append(vel)

    async def parking(self, vel):
        self.parking_calls.append(vel)

    async def zeroing(self, vel):
        self.zeroing_calls.append(vel)


class FakeCalc:
    def __init__(self, logger):
        self.logger = logger
        self.calc_from_za_calls = []
        self.degree_to_count_calls = []

    def calc_from_za(self, za):
        self.calc_from_za_calls.append(za)
        return 10.0  # degrees (임의)

    def degree_to_count(self, degree):
        self.degree_to_count_calls.append(degree)
        return 100  # counts (임의)


@pytest.fixture
def actions_module(monkeypatch):
    """
    AdcActions 모듈 import 후, 내부에서 참조하는 AdcLogger/AdcController/ADCCalc를 fake로 교체.
    (AdcActions.__init__이 강하게 의존하므로 필수)
    """
    mod = importlib.import_module("kspec_adc_controller.adc_actions")
    mod = importlib.reload(mod)

    # AdcLogger(__file__)가 실제 파일 핸들러를 만들지 않도록 fake logger로 대체
    monkeypatch.setattr(mod, "AdcLogger", lambda *_args, **_kwargs: DummyLogger())

    # Controller/Calc도 fake로 대체
    monkeypatch.setattr(mod, "AdcController", lambda logger: FakeController(logger))
    monkeypatch.setattr(mod, "ADCCalc", lambda logger: FakeCalc(logger))

    return mod


@pytest.fixture
def actions(actions_module):
    # patched된 상태로 AdcActions 생성
    return actions_module.AdcActions()


def test_init_creates_controller_and_calls_find_devices(actions):
    assert isinstance(actions.logger, DummyLogger)
    assert isinstance(actions.controller, FakeController)
    assert isinstance(actions.calculator, FakeCalc)

    assert actions.controller.find_devices_called == 1
    assert any("Initializing AdcActions class" in m for m in actions.logger.debugs)


def test_generate_response_includes_kwargs(actions):
    res = actions._generate_response("success", "ok", a=1, b="x")
    assert res == {"status": "success", "message": "ok", "a": 1, "b": "x"}


def test_connect_success(actions):
    res = actions.connect()
    assert actions.controller.connect_called == 1
    assert res["status"] == "success"
    assert "Connected to devices" in res["message"]


def test_connect_error_returns_error(monkeypatch, actions):
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(actions.controller, "connect", boom)

    res = actions.connect()
    assert res["status"] == "error"
    assert "Failed to connect" in res["message"]
    assert any("Error in connect" in m for m in actions.logger.errors)


def test_status_success(actions):
    res = actions.status(2)
    assert actions.controller.device_state_called == [2]
    assert res["status"] == "success"
    assert "Motor 2 status retrieved" in res["message"]


def test_status_error(monkeypatch, actions):
    def boom(_motor):
        raise ValueError("bad")

    monkeypatch.setattr(actions.controller, "device_state", boom)

    res = actions.status(1)
    assert res["status"] == "error"
    assert "Error retrieving motor 1 status" in res["message"]


@pytest.mark.asyncio
async def test_move_motor_id_0_moves_both_with_negative_pos(actions):
    res = await actions.move(0, pos_count=123, vel_set=2)

    # motor1: -pos_count, motor2: -pos_count
    assert (1, -123, 2) in actions.controller.move_motor_calls
    assert (2, -123, 2) in actions.controller.move_motor_calls

    assert res["status"] == "success"
    assert "Both motors moved to position 123" in res["message"]
    assert "motor_1" in res and "motor_2" in res


@pytest.mark.asyncio
async def test_move_motor_id_minus1_moves_opposite_directions(actions):
    res = await actions.move(-1, pos_count=50, vel_set=1)

    # motor1: -pos_count, motor2: +pos_count
    assert (1, -50, 1) in actions.controller.move_motor_calls
    assert (2, 50, 1) in actions.controller.move_motor_calls

    assert res["status"] == "success"
    assert res["motor_1"]["motor_id"] == 1
    assert res["motor_2"]["motor_id"] == 2


@pytest.mark.asyncio
async def test_move_single_motor(actions):
    res = await actions.move(1, pos_count=77, vel_set=3)

    assert actions.controller.move_motor_calls[-1] == (1, -77, 3)
    assert res["status"] == "success"
    assert "Motor 1 moved to position 77" in res["message"]


@pytest.mark.asyncio
async def test_move_error(monkeypatch, actions):
    def boom(*_args, **_kwargs):
        raise RuntimeError("move fail")

    monkeypatch.setattr(actions.controller, "move_motor", boom)

    res = await actions.move(1, pos_count=10, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to move motor 1" in res["message"]


@pytest.mark.asyncio
async def test_stop_both(actions):
    res = await actions.stop(0)

    assert actions.controller.stop_motor_calls.count(1) == 1
    assert actions.controller.stop_motor_calls.count(2) == 1
    assert res["status"] == "success"
    assert "Both motors stopped successfully" in res["message"]


@pytest.mark.asyncio
async def test_stop_single(actions):
    res = await actions.stop(2)

    assert actions.controller.stop_motor_calls[-1] == 2
    assert res["status"] == "success"
    assert "Motor 2 stopped successfully" in res["message"]


@pytest.mark.asyncio
async def test_stop_invalid_motor_id(actions):
    res = await actions.stop(99)
    assert res["status"] == "error"
    assert "Failed to stop motor 99" in res["message"]


@pytest.mark.asyncio
async def test_activate_caps_velocity_and_uses_calculator(actions):
    # vel_set=99 -> 5로 cap
    res = await actions.activate(za=12.3, vel_set=99)

    assert res["status"] == "success"
    assert actions.calculator.calc_from_za_calls == [12.3]
    assert actions.calculator.degree_to_count_calls == [
        10.0
    ]  # FakeCalc.calc_from_za returns 10.0

    # move_motor은 motor1, motor2 모두 -pos(= -100), vel=5로 호출돼야 함
    assert (1, -100, 5) in actions.controller.move_motor_calls
    assert (2, -100, 5) in actions.controller.move_motor_calls

    assert any("exceeds the limit of 5 RPM" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_activate_negative_velocity_sets_default_1(actions):
    res = await actions.activate(za=1.0, vel_set=-3)
    assert res["status"] == "success"
    assert (1, -100, 1) in actions.controller.move_motor_calls
    assert (2, -100, 1) in actions.controller.move_motor_calls
    assert any("is negative" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_activate_calc_error_returns_error(monkeypatch, actions):
    def boom(_za):
        raise ValueError("calc fail")

    monkeypatch.setattr(actions.calculator, "calc_from_za", boom)

    res = await actions.activate(za=5.0, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to calculate motor position" in res["message"]


@pytest.mark.asyncio
async def test_homing_velocity_caps_and_calls_controller(actions):
    res = await actions.homing(homing_vel=10)
    assert res["status"] == "success"
    assert actions.controller.homing_calls == [5]
    assert any("exceeds the limit of 5 RPM" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_parking_calls_controller(actions):
    res = await actions.parking(parking_vel=2)
    assert res["status"] == "success"
    assert actions.controller.parking_calls == [2]


@pytest.mark.asyncio
async def test_zeroing_calls_controller(actions):
    res = await actions.zeroing(zeroing_vel=2)
    assert res["status"] == "success"
    assert actions.controller.zeroing_calls == [2]


def test_disconnect_success(actions):
    res = actions.disconnect()
    assert actions.controller.disconnect_called == 1
    assert res["status"] == "success"


def test_power_off_success(actions):
    res = actions.power_off()
    assert actions.controller.disconnect_called == 1
    assert actions.controller.close_called == 1
    assert res["status"] == "success"


def test_calc_from_za_success(actions):
    res = actions.calc_from_za(za=3.0)
    assert res["status"] == "success"
    assert res["message"] == 10.0


def test_degree_to_count_success(actions):
    res = actions.degree_to_count(180.0)
    assert res["status"] == "success"
    assert res["message"] == 100
