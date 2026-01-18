import asyncio
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

        # failure injection
        self.find_devices_raises = None
        self.connect_raises = None
        self.disconnect_raises = None
        self.close_raises = None
        self.device_state_raises = None

        # move/stop injection: motor_id -> exception
        self.move_motor_raises_for = set()
        self.stop_motor_raises_for = set()

        self.homing_raises = None
        self.parking_raises = None
        self.zeroing_raises = None

    def find_devices(self):
        self.find_devices_called += 1
        if self.find_devices_raises:
            raise self.find_devices_raises

    def connect(self):
        self.connect_called += 1
        if self.connect_raises:
            raise self.connect_raises

    def disconnect(self):
        self.disconnect_called += 1
        if self.disconnect_raises:
            raise self.disconnect_raises

    def close(self):
        self.close_called += 1
        if self.close_raises:
            raise self.close_raises

    def device_state(self, motor_num):
        self.device_state_called.append(motor_num)
        if self.device_state_raises:
            raise self.device_state_raises

        # AdcActions.homing()이 기대하는 형태로 리턴
        if motor_num == 0:
            return {
                "motor1": {"position_state": 200, "connection_state": True},
                "motor2": {"position_state": 200, "connection_state": True},
            }
        elif motor_num == 1:
            return {"motor1": {"position_state": 200, "connection_state": True}}
        elif motor_num == 2:
            return {"motor2": {"position_state": 200, "connection_state": True}}
        else:
            raise ValueError("Invalid motor number")

    def move_motor(self, motor_id, pos, vel):
        if motor_id in self.move_motor_raises_for:
            raise RuntimeError(f"move fail motor {motor_id}")
        self.move_motor_calls.append((motor_id, pos, vel))
        return {"motor_id": motor_id, "pos": pos, "vel": vel}

    def stop_motor(self, motor_id):
        if motor_id in self.stop_motor_raises_for:
            raise RuntimeError(f"stop fail motor {motor_id}")
        self.stop_motor_calls.append(motor_id)
        return {"motor_id": motor_id, "stopped": True}

    async def homing(self, vel):
        if self.homing_raises:
            raise self.homing_raises
        self.homing_calls.append(vel)

    async def parking(self, vel):
        if self.parking_raises:
            raise self.parking_raises
        self.parking_calls.append(vel)

    async def zeroing(self, vel):
        if self.zeroing_raises:
            raise self.zeroing_raises
        self.zeroing_calls.append(vel)


class FakeCalc:
    def __init__(self, logger):
        self.logger = logger
        self.calc_from_za_calls = []
        self.degree_to_count_calls = []

        # failure injection
        self.calc_from_za_raises = None
        self.degree_to_count_raises = None

    def calc_from_za(self, za):
        if self.calc_from_za_raises:
            raise self.calc_from_za_raises
        self.calc_from_za_calls.append(za)
        return 10.0  # degrees

    def degree_to_count(self, degree):
        if self.degree_to_count_raises:
            raise self.degree_to_count_raises
        self.degree_to_count_calls.append(degree)
        return 100  # counts


@pytest.fixture
def actions_module(monkeypatch):
    """
    AdcActions 모듈 import 후, 내부에서 참조하는 AdcLogger/AdcController/ADCCalc를 fake로 교체.
    """
    mod = importlib.import_module("kspec_adc_controller.adc_actions")
    mod = importlib.reload(mod)

    monkeypatch.setattr(mod, "AdcLogger", lambda *_args, **_kwargs: DummyLogger())
    monkeypatch.setattr(mod, "AdcController", lambda logger: FakeController(logger))
    monkeypatch.setattr(mod, "ADCCalc", lambda logger: FakeCalc(logger))

    return mod


@pytest.fixture
def actions(actions_module):
    return actions_module.AdcActions()


# -------------------------
# __init__ coverage
# -------------------------
def test_init_creates_controller_and_calls_find_devices(actions):
    assert isinstance(actions.logger, DummyLogger)
    assert isinstance(actions.controller, FakeController)
    assert isinstance(actions.calculator, FakeCalc)

    assert actions.controller.find_devices_called == 1
    assert any("Initializing AdcActions class" in m for m in actions.logger.debugs)


def test_init_find_devices_raises_propagates(actions_module, monkeypatch):
    """
    __init__ 안에서 controller.find_devices()가 실패하면 생성 자체가 실패하는게 정상.
    """
    ctrl = FakeController(DummyLogger())
    ctrl.find_devices_raises = RuntimeError("find fail")

    monkeypatch.setattr(actions_module, "AdcController", lambda logger: ctrl)

    with pytest.raises(RuntimeError):
        actions_module.AdcActions()


# -------------------------
# helper
# -------------------------
def test_generate_response_includes_kwargs(actions):
    res = actions._generate_response("success", "ok", a=1, b="x")
    assert res == {"status": "success", "message": "ok", "a": 1, "b": "x"}


# -------------------------
# connect / status
# -------------------------
def test_connect_success(actions):
    res = actions.connect()
    assert actions.controller.connect_called == 1
    assert res["status"] == "success"
    assert "Connected to devices" in res["message"]


def test_connect_error_returns_error(actions):
    actions.controller.connect_raises = RuntimeError("nope")
    res = actions.connect()
    assert res["status"] == "error"
    assert "Failed to connect" in res["message"]
    assert any("Error in connect" in m for m in actions.logger.errors)


def test_status_success(actions):
    res = actions.status(2)
    assert actions.controller.device_state_called == [2]
    assert res["status"] == "success"
    assert "Motor 2 status retrieved" in res["message"]


def test_status_error(actions):
    actions.controller.device_state_raises = ValueError("bad")
    res = actions.status(1)
    assert res["status"] == "error"
    assert "Error retrieving motor 1 status" in res["message"]
    assert any("Error in status" in m for m in actions.logger.errors)


# -------------------------
# move() coverage
# -------------------------
@pytest.mark.asyncio
async def test_move_motor_id_0_moves_both_with_negative_pos(actions):
    res = await actions.move(0, pos_count=123, vel_set=2)

    assert (1, -123, 2) in actions.controller.move_motor_calls
    assert (2, -123, 2) in actions.controller.move_motor_calls

    assert res["status"] == "success"
    assert "Both motors moved to position 123" in res["message"]
    assert "motor_1" in res and "motor_2" in res


@pytest.mark.asyncio
async def test_move_motor_id_0_one_motor_fails_returns_error(actions):
    actions.controller.move_motor_raises_for.add(2)

    res = await actions.move(0, pos_count=10, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to move motor 0" in res["message"]
    assert any("Error moving motor 0" in m for m in actions.logger.errors)


@pytest.mark.asyncio
async def test_move_motor_id_minus1_moves_opposite_directions(actions):
    res = await actions.move(-1, pos_count=50, vel_set=1)

    assert (1, -50, 1) in actions.controller.move_motor_calls
    assert (2, 50, 1) in actions.controller.move_motor_calls

    assert res["status"] == "success"
    assert res["motor_1"]["motor_id"] == 1
    assert res["motor_2"]["motor_id"] == 2


@pytest.mark.asyncio
async def test_move_motor_id_minus1_one_motor_fails_returns_error(actions):
    actions.controller.move_motor_raises_for.add(1)

    res = await actions.move(-1, pos_count=50, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to move motor -1" in res["message"]
    assert any("Error moving motor -1" in m for m in actions.logger.errors)


@pytest.mark.asyncio
async def test_move_single_motor(actions):
    res = await actions.move(1, pos_count=77, vel_set=3)

    assert actions.controller.move_motor_calls[-1] == (1, -77, 3)
    assert res["status"] == "success"
    assert "Motor 1 moved to position 77" in res["message"]


@pytest.mark.asyncio
async def test_move_error(actions):
    actions.controller.move_motor_raises_for.add(1)

    res = await actions.move(1, pos_count=10, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to move motor 1" in res["message"]


# -------------------------
# stop() coverage
# -------------------------
@pytest.mark.asyncio
async def test_stop_both(actions):
    res = await actions.stop(0)

    assert actions.controller.stop_motor_calls.count(1) == 1
    assert actions.controller.stop_motor_calls.count(2) == 1
    assert res["status"] == "success"
    assert "Both motors stopped successfully" in res["message"]


@pytest.mark.asyncio
async def test_stop_both_one_motor_fails_returns_error(actions):
    actions.controller.stop_motor_raises_for.add(2)
    res = await actions.stop(0)
    assert res["status"] == "error"
    assert "Failed to stop motor 0" in res["message"]
    assert any("Error stopping motor 0" in m for m in actions.logger.errors)


@pytest.mark.asyncio
async def test_stop_single(actions):
    res = await actions.stop(2)

    assert actions.controller.stop_motor_calls[-1] == 2
    assert res["status"] == "success"
    assert "Motor 2 stopped successfully" in res["message"]


@pytest.mark.asyncio
async def test_stop_single_controller_raises(actions):
    actions.controller.stop_motor_raises_for.add(1)
    res = await actions.stop(1)
    assert res["status"] == "error"
    assert "Failed to stop motor 1" in res["message"]


@pytest.mark.asyncio
async def test_stop_invalid_motor_id(actions):
    res = await actions.stop(99)
    assert res["status"] == "error"
    assert "Failed to stop motor 99" in res["message"]


# -------------------------
# activate() coverage
# -------------------------
@pytest.mark.asyncio
async def test_activate_caps_velocity_and_uses_calculator(actions):
    # vel_set=99 -> 5로 cap
    res = await actions.activate(za=12.3, vel_set=99)

    assert res["status"] == "success"
    assert actions.calculator.calc_from_za_calls == [12.3]
    assert actions.calculator.degree_to_count_calls == [10.0]

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
async def test_activate_calc_error_returns_error(actions):
    actions.calculator.calc_from_za_raises = ValueError("calc fail")

    res = await actions.activate(za=5.0, vel_set=1)
    assert res["status"] == "error"
    assert "Failed to calculate motor position" in res["message"]


@pytest.mark.asyncio
async def test_activate_one_motor_fails_returns_error(actions):
    """
    activate()는 gather(return_exceptions=True)라서 한쪽 모터만 실패하면
    results에 Exception이 들어오고 error response로 리턴해야 함.
    """
    actions.controller.move_motor_raises_for.add(2)

    res = await actions.activate(za=5.0, vel_set=1)
    assert res["status"] == "error"
    assert "activation failed" in res["message"]
    assert any("Motor 2 failed" in m for m in actions.logger.errors)


@pytest.mark.asyncio
async def test_activate_outer_except_branch_is_covered(monkeypatch, actions_module):
    """
    activate()의 바깥 try/except(모터 실행 부분)에서,
    예기치 못한 예외가 발생할 때의 except 분기를 커버.
    (asyncio.gather 자체를 강제로 터뜨림)
    """
    actions = actions_module.AdcActions()

    # 계산 파트는 성공하게 두고, gather가 터지게 만든다.
    orig_gather = asyncio.gather

    async def boom_gather(*aws, **_kwargs):
        # 생성된 to_thread 코루틴들을 await해서 warning 방지
        for aw in aws:
            try:
                await aw
            except Exception:
                pass
        raise RuntimeError("gather blew up")

    monkeypatch.setattr(asyncio, "gather", boom_gather)
    try:
        res = await actions.activate(za=1.0, vel_set=1)
        assert res["status"] == "error"
        assert "Failed to activate motors" in res["message"]
        assert "gather blew up" in res["message"]
    finally:
        monkeypatch.setattr(asyncio, "gather", orig_gather)


# -------------------------
# homing/parking/zeroing coverage
# -------------------------
@pytest.mark.asyncio
async def test_homing_velocity_caps_and_calls_controller(actions):
    res = await actions.homing(homing_vel=10)
    assert res["status"] == "success"
    assert actions.controller.homing_calls == [5]
    assert any("exceeds the limit of 5 RPM" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_homing_negative_velocity_defaults_to_1(actions):
    res = await actions.homing(homing_vel=-10)
    assert res["status"] == "success"
    assert actions.controller.homing_calls == [1]
    assert any("is negative" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_homing_controller_raises_returns_error(actions):
    actions.controller.homing_raises = RuntimeError("homing fail")
    res = await actions.homing(homing_vel=1)
    assert res["status"] == "error"
    assert "homing fail" in res["message"]


@pytest.mark.asyncio
async def test_parking_calls_controller(actions):
    res = await actions.parking(parking_vel=2)
    assert res["status"] == "success"
    assert actions.controller.parking_calls == [2]


@pytest.mark.asyncio
async def test_parking_negative_velocity_defaults_to_1(actions):
    res = await actions.parking(parking_vel=-2)
    assert res["status"] == "success"
    assert actions.controller.parking_calls == [1]
    assert any("is negative" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_parking_controller_raises_returns_error(actions):
    actions.controller.parking_raises = RuntimeError("parking fail")
    res = await actions.parking(parking_vel=1)
    assert res["status"] == "error"
    assert "parking fail" in res["message"]


@pytest.mark.asyncio
async def test_zeroing_calls_controller(actions):
    res = await actions.zeroing(zeroing_vel=2)
    assert res["status"] == "success"
    assert actions.controller.zeroing_calls == [2]


@pytest.mark.asyncio
async def test_zeroing_negative_velocity_defaults_to_1(actions):
    res = await actions.zeroing(zeroing_vel=-2)
    assert res["status"] == "success"
    assert actions.controller.zeroing_calls == [1]
    assert any("is negative" in m for m in actions.logger.warnings)


@pytest.mark.asyncio
async def test_zeroing_controller_raises_returns_error(actions):
    actions.controller.zeroing_raises = RuntimeError("zeroing fail")
    res = await actions.zeroing(zeroing_vel=1)
    assert res["status"] == "error"
    assert "zeroing fail" in res["message"]


# -------------------------
# disconnect / power_off coverage
# -------------------------
def test_disconnect_success(actions):
    res = actions.disconnect()
    assert actions.controller.disconnect_called == 1
    assert res["status"] == "success"


def test_disconnect_error(actions):
    actions.controller.disconnect_raises = RuntimeError("disc fail")
    res = actions.disconnect()
    assert res["status"] == "error"
    assert "disc fail" in res["message"]


def test_power_off_success(actions):
    res = actions.power_off()
    assert actions.controller.disconnect_called == 1
    assert actions.controller.close_called == 1
    assert res["status"] == "success"


def test_power_off_disconnect_raises(actions):
    actions.controller.disconnect_raises = RuntimeError("disc fail")
    res = actions.power_off()
    assert res["status"] == "error"
    assert "disc fail" in res["message"]


def test_power_off_close_raises(actions):
    actions.controller.close_raises = RuntimeError("close fail")
    res = actions.power_off()
    assert res["status"] == "error"
    assert "close fail" in res["message"]


# -------------------------
# calc wrappers coverage
# -------------------------
def test_calc_from_za_success(actions):
    res = actions.calc_from_za(za=3.0)
    assert res["status"] == "success"
    assert res["message"] == 10.0


def test_calc_from_za_error(actions):
    actions.calculator.calc_from_za_raises = RuntimeError("za fail")
    res = actions.calc_from_za(za=3.0)
    assert res["status"] == "error"
    assert "za fail" in res["message"]


def test_degree_to_count_success(actions):
    res = actions.degree_to_count(180.0)
    assert res["status"] == "success"
    assert res["message"] == 100


def test_degree_to_count_error(actions):
    actions.calculator.degree_to_count_raises = RuntimeError("deg fail")
    res = actions.degree_to_count(180.0)
    assert res["status"] == "error"
    assert "deg fail" in res["message"]
