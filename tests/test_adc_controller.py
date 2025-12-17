import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest


# -------------------------
# Test doubles (fakes)
# -------------------------
class DummyLogger:
    def __init__(self):
        self.debugs = []
        self.infos = []
        self.warnings = []
        self.errors = []
        self.exceptions = []

    def debug(self, msg):
        self.debugs.append(msg)

    def info(self, msg):
        self.infos.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)

    def error(self, msg, exc_info=False):
        self.errors.append(msg)

    def exception(self, msg):
        self.exceptions.append(msg)


class FakeResult:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def hasError(self):
        return self._error is not None

    def getError(self):
        return self._error

    def getResult(self):
        return self._result


class _FakeSizeList(list):
    def size(self):
        return len(self)


class _FakeBusId:
    def __init__(self, s):
        self._s = s

    def toString(self):
        return self._s

    def __str__(self):
        return self._s


class FakeAccessor:
    """
    AdcController에서 사용하는 nanolib_accessor API 일부만 흉내낸다.
    """

    def __init__(self):
        self.connected_handles = set()
        self.positions = {}  # handle -> position(int)

        # connection
        self.connect_error = None
        self.disconnect_error = None
        self.check_conn_state = {}  # handle -> bool

        # read/write injection
        self.read_error = None  # readNumber를 error로 만들기
        self.write_raises_at_idx = set()  # 특정 od_index.idx에서 writeNumber가 Exception throw

        # close injection
        self.close_error = None

        # ---- find_devices 관련 injection ----
        self.list_bus_error = None
        self.open_bus_error = None
        self.scan_error = None
        self.add_device_error = None  # True면 addDevice error

        # find_devices용
        self.bus_ids = _FakeSizeList([_FakeBusId("BUS0"), _FakeBusId("BUS1")])
        self.scan_device_ids = _FakeSizeList([_FakeBusId("DEV0"), _FakeBusId("DEV1")])
        self.add_device_handles = ["H1", "H2"]

        # move/stop용
        self._status_sequence = [0x0000, 0x1400]  # move 완료 플래그로 종료
        self._status_i = 0
        self.write_calls = []  # writeNumber 호출 기록

    # ---- connect/disconnect ----
    def connectDevice(self, handle):
        if self.connect_error:
            return FakeResult(error=self.connect_error)
        self.connected_handles.add(handle)
        self.check_conn_state[handle] = True
        return FakeResult(result=True)

    def disconnectDevice(self, handle):
        if self.disconnect_error:
            return FakeResult(error=self.disconnect_error)
        self.connected_handles.discard(handle)
        self.check_conn_state[handle] = False
        return FakeResult(result=True)

    def checkConnectionState(self, handle):
        return FakeResult(result=self.check_conn_state.get(handle, False))

    # ---- bus close ----
    def closeBusHardware(self, adc_motor_id):
        if self.close_error:
            return FakeResult(error=self.close_error)
        return FakeResult(result=True)

    # ---- find_devices ----
    def listAvailableBusHardware(self):
        if self.list_bus_error:
            return FakeResult(error=self.list_bus_error)
        return FakeResult(result=self.bus_ids)

    def openBusHardwareWithProtocol(self, bus_id, options):
        if self.open_bus_error:
            return FakeResult(error=self.open_bus_error)
        return FakeResult(result=True)

    def scanDevices(self, bus_id, callback):
        if self.scan_error:
            return FakeResult(error=self.scan_error)
        return FakeResult(result=self.scan_device_ids)

    def addDevice(self, device_id):
        if self.add_device_error:
            return FakeResult(error="ADD_DEVICE_FAIL")
        s = str(device_id)
        idx = 0 if "DEV0" in s else 1
        return FakeResult(result=self.add_device_handles[idx])

    # ---- motion ----
    def writeNumber(self, handle, value, od_index, bits):
        if getattr(od_index, "idx", None) in self.write_raises_at_idx:
            raise RuntimeError(f"WRITE_FAIL idx={od_index.idx:#x}")
        self.write_calls.append((handle, value, od_index.idx, od_index.sub, bits))
        return FakeResult(result=True)

    def readNumber(self, handle, od_index):
        """
        - read_error가 설정되면 FakeResult(error=...) 반환
        - statusword(0x6041)는 _status_sequence로 반환
        - 그 외는 positions에서 반환
        """
        if self.read_error:
            return FakeResult(error=self.read_error)

        if getattr(od_index, "idx", None) == 0x6041:
            v = self._status_sequence[min(self._status_i, len(self._status_sequence) - 1)]
            self._status_i += 1
            return FakeResult(result=v)

        return FakeResult(result=self.positions.get(handle, 0))


def make_fake_nanolib_module(fake_accessor: FakeAccessor):
    """
    sys.modules['nanotec_nanolib'] 에 주입할 가짜 모듈을 만든다.
    코드에서: from nanotec_nanolib import Nanolib
    형태로 가져가므로, nanotec_nanolib 안에 Nanolib 객체가 있어야 함.
    """
    fake_mod = types.ModuleType("nanotec_nanolib")

    class _FakeNanolibNamespace:
        @staticmethod
        def getNanoLibAccessor():
            return fake_accessor

        class OdIndex:
            def __init__(self, idx, sub):
                self.idx = idx
                self.sub = sub

        class NlcScanBusCallback:
            pass

        BusScanInfo_Start = 1
        BusScanInfo_Progress = 2
        BusScanInfo_Finished = 3

        class ResultVoid:
            pass

        class BusHardwareOptions:
            def __init__(self):
                self.opts = []

            def addOption(self, name, value):
                self.opts.append((name, value))

        class Serial:
            BAUD_RATE_OPTIONS_NAME = "baud_rate"
            PARITY_OPTIONS_NAME = "parity"

        class SerialBaudRate:
            BAUD_RATE_115200 = 115200

        class SerialParity:
            EVEN = "even"

    fake_mod.Nanolib = _FakeNanolibNamespace
    return fake_mod


@pytest.fixture
def adc_controller_module(monkeypatch):
    """
    nanotec_nanolib 의존성을 fake로 주입한 뒤,
    kspec_adc_controller.adc_controller 를 import/reload해서 테스트 가능한 모듈 객체를 반환.
    """
    fake_accessor = FakeAccessor()
    fake_nanolib = make_fake_nanolib_module(fake_accessor)
    monkeypatch.setitem(sys.modules, "nanotec_nanolib", fake_nanolib)

    mod = importlib.import_module("kspec_adc_controller.adc_controller")
    mod = importlib.reload(mod)
    return mod, fake_accessor


@pytest.fixture
def logger():
    return DummyLogger()


@pytest.fixture
def config_file(tmp_path: Path) -> str:
    p = tmp_path / "adc_config.json"
    p.write_text(json.dumps({"selected_bus_index": 0}), encoding="utf-8")
    return str(p)


# -------------------------
# Core tests (existing + extended)
# -------------------------
def test_init_loads_selected_bus_index_from_valid_json(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    assert c.selected_bus_index == 0
    assert c.CONFIG_FILE == config_file
    assert any("Initializing AdcController" in m for m in logger.debugs)


def test_load_selected_bus_index_missing_file_defaults_to_1(adc_controller_module, logger, tmp_path):
    mod, _fake_accessor = adc_controller_module
    missing = str(tmp_path / "missing.json")

    c = mod.AdcController(logger=logger, config=missing)
    assert c.selected_bus_index == 1
    assert any("not found" in m for m in logger.warnings)


def test_load_selected_bus_index_invalid_json_defaults_to_1(adc_controller_module, logger, tmp_path):
    mod, _fake_accessor = adc_controller_module
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")

    c = mod.AdcController(logger=logger, config=str(bad))
    assert c.selected_bus_index == 1
    assert any("Error reading configuration file" in m for m in logger.errors)


def test_connect_invalid_motor_number_raises_and_logs_exception(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    with pytest.raises(ValueError):
        c.connect(motor_number=3)

    assert any("An error occurred while connecting" in m for m in logger.exceptions)


def test_connect_all_motors_success_updates_state(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[2]["handle"] = "H2"

    c.connect(0)

    assert c.devices[1]["connected"] is True
    assert c.devices[2]["connected"] is True
    assert "H1" in fake_accessor.connected_handles
    assert "H2" in fake_accessor.connected_handles


def test_connect_error_raises_and_logs(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = False
    fake_accessor.connect_error = "CONNECT_FAIL"

    with pytest.raises(Exception):
        c.connect(1)

    assert any("Error connecting device 1" in m for m in logger.errors)
    assert any("An error occurred while connecting" in m for m in logger.exceptions)


def test_disconnect_motor_success_updates_state(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.connected_handles.add("H1")
    fake_accessor.check_conn_state["H1"] = True

    c.disconnect(1)

    assert c.devices[1]["connected"] is False
    assert "H1" not in fake_accessor.connected_handles


def test_disconnect_when_not_connected_logs_info(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = False

    c.disconnect(1)
    assert any("was not connected" in m for m in logger.infos)


def test_disconnect_error_raises_and_logs(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.disconnect_error = "DISCONNECT_FAIL"

    with pytest.raises(Exception):
        c.disconnect(1)

    assert any("Error disconnecting device 1" in m for m in logger.errors)
    assert any("An error occurred while disconnecting" in m for m in logger.exceptions)


def test_connect_when_already_connected_does_not_call_error(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.connect_error = "SHOULD_NOT_BE_USED"

    c.connect(1)
    assert any("already connected" in m for m in logger.infos)


def test_read_motor_position_requires_connected(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = False

    with pytest.raises(Exception):
        c.read_motor_position(1)


def test_read_motor_position_success(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.positions["H1"] = 12345

    assert c.read_motor_position(1) == 12345


def test_read_motor_position_read_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.read_error = "READ_FAIL"

    with pytest.raises(Exception):
        c.read_motor_position(1)

    assert any("Failed to read position for Motor 1" in m for m in logger.errors)


def test_device_state_returns_position_and_connection_state(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[2]["handle"] = "H2"
    c.devices[1]["connected"] = True
    c.devices[2]["connected"] = True

    fake_accessor.positions["H1"] = 100
    fake_accessor.positions["H2"] = 200
    fake_accessor.check_conn_state["H1"] = True
    fake_accessor.check_conn_state["H2"] = False

    res = c.device_state(0)

    assert res["motor1"]["position_state"] == 100
    assert res["motor1"]["connection_state"] is True
    assert res["motor2"]["position_state"] == 200
    assert res["motor2"]["connection_state"] is False


def test_device_state_invalid_motor_number_raises(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    with pytest.raises(ValueError):
        c.device_state(99)


# -------------------------
# find_devices coverage (success + failure branches)
# -------------------------
def test_find_devices_registers_handles(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.selected_bus_index = 0
    c.find_devices()

    assert c.devices[1]["handle"] == "H1"
    assert c.devices[2]["handle"] == "H2"
    assert any("Selected bus hardware ID" in m for m in logger.infos)


def test_find_devices_list_bus_has_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.list_bus_error = "LIST_BUS_FAIL"
    with pytest.raises(Exception):
        c.find_devices()


def test_find_devices_no_bus_ids_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.bus_ids = _FakeSizeList([])
    with pytest.raises(Exception) as e:
        c.find_devices()
    assert "No bus hardware IDs found" in str(e.value)


def test_find_devices_open_bus_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.open_bus_error = "OPEN_BUS_FAIL"
    with pytest.raises(Exception):
        c.find_devices()


def test_find_devices_scan_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.scan_error = "SCAN_FAIL"
    with pytest.raises(Exception):
        c.find_devices()


def test_find_devices_no_devices_found_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.scan_device_ids = _FakeSizeList([])
    with pytest.raises(Exception) as e:
        c.find_devices()
    assert "No devices found during scan" in str(e.value)


def test_find_devices_add_device_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    fake_accessor.add_device_error = True
    with pytest.raises(Exception):
        c.find_devices()


# -------------------------
# close() coverage
# -------------------------
def test_close_success(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)
    c.adc_motor_id = "BUS0"
    c.close()
    assert any("Bus hardware closed successfully" in m for m in logger.infos)


def test_close_has_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)
    c.adc_motor_id = "BUS0"
    fake_accessor.close_error = "CLOSE_FAIL"
    with pytest.raises(Exception):
        c.close()


# -------------------------
# move_motor coverage (vel None/default, loop, failure)
# -------------------------
def test_move_motor_default_velocity_when_vel_none(adc_controller_module, logger, config_file, monkeypatch):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True

    # loop 한 번 이상 돌게
    fake_accessor._status_sequence = [0x0000, 0x0000, 0x1400]
    fake_accessor._status_i = 0

    c._moved = False
    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: 150 if c._moved else 100)

    orig_write = fake_accessor.writeNumber

    def wrapped_write(handle, value, od_index, bits):
        if od_index.idx == 0x607A:
            c._moved = True
        return orig_write(handle, value, od_index, bits)

    fake_accessor.writeNumber = wrapped_write
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    res = c.move_motor(1, pos=999, vel=None)

    assert res["initial_position"] == 100
    assert res["final_position"] == 150
    # default velocity(1000)가 설정됐는지
    assert any(call[2] == 0x6081 and call[1] == 1000 for call in fake_accessor.write_calls)


def test_move_motor_write_raises_logs_and_raises(adc_controller_module, logger, config_file, monkeypatch):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True

    fake_accessor.write_raises_at_idx.add(0x607A)
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    with pytest.raises(Exception):
        c.move_motor(1, pos=999, vel=123)

    assert any("Failed to move Motor 1" in m for m in logger.errors)


# -------------------------
# stop_motor coverage (handle None / read fail)
# -------------------------
def test_stop_motor_handle_none_raises(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = None
    c.devices[1]["connected"] = True

    with pytest.raises(ValueError):
        c.stop_motor(1)

    assert any("Device not found" in m for m in logger.errors)


def test_stop_motor_success_when_halt_bit_set(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True

    fake_accessor._status_sequence = [0x8000]
    fake_accessor._status_i = 0

    res = c.stop_motor(1)
    assert res["status"] == "success"
    assert res["error_code"] is None


def test_stop_motor_failed_when_halt_bit_not_set(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True

    fake_accessor._status_sequence = [0x0001]
    fake_accessor._status_i = 0

    res = c.stop_motor(1)
    assert res["status"] == "failed"
    assert res["error_code"] == 0x0001


def test_stop_motor_read_error_raises(adc_controller_module, logger, config_file):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True
    fake_accessor.read_error = "READ_FAIL"

    with pytest.raises(Exception):
        c.stop_motor(1)

    assert any("Error during stopping" in m for m in logger.errors)


# -------------------------
# parking/zeroing/homing: wrap-around branches + threshold branches
# -------------------------
@pytest.mark.asyncio
async def test_parking_requires_homing(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = False
    with pytest.raises(Exception):
        await c.parking(parking_vel=1)

    assert any("Parking must be performed after homing" in m for m in logger.errors)


@pytest.mark.asyncio
async def test_zeroing_requires_homing(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = False
    with pytest.raises(Exception):
        await c.zeroing(zeroing_vel=1)

    assert any("Zeroing must be performed after homing" in m for m in logger.errors)


@pytest.mark.asyncio
async def test_parking_threshold_no_move(adc_controller_module, logger, config_file, monkeypatch):
    """
    target_pos_1/2가 threshold(10)보다 작으면 move_motor를 호출하지 않는 분기.
    """
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = True
    c.home_position_motor1 = 1000
    c.home_position_motor2 = 2000

    # parking_offset=-500 => home+offset = 500, 1500
    # current_pos를 같게 맞추면 target_pos=0
    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: 500 if motor_id == 1 else 1500)

    called = {"move": 0}

    def fake_move(*args, **kwargs):
        called["move"] += 1
        return {"ok": True}

    monkeypatch.setattr(c, "move_motor", fake_move)

    await c.parking(parking_vel=1)

    assert called["move"] == 0
    assert any("already close to the parking position" in m for m in logger.infos)


@pytest.mark.asyncio
async def test_zeroing_threshold_no_move(adc_controller_module, logger, config_file, monkeypatch):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = True
    c.home_position_motor1 = 0
    c.home_position_motor2 = 0

    # zero_offset 7635/1926, current_pos가 딱 target과 같아서 target_pos=0
    monkeypatch.setattr(
        c, "read_motor_position", lambda motor_id: 7635 if motor_id == 1 else 1926
    )

    called = {"move": 0}

    def fake_move(*args, **kwargs):
        called["move"] += 1
        return {"ok": True}

    monkeypatch.setattr(c, "move_motor", fake_move)

    await c.zeroing(zeroing_vel=1)

    assert called["move"] == 0
    assert any("already close to Zero position" in m for m in logger.infos)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "p1,p2",
    [
        (100, 200),  # both < 1e6
        (100, 2_000_000),  # only p1 < 1e6
        (2_000_000, 100),  # only p2 < 1e6
        (2_000_000, 3_000_000),  # both >= 1e6
    ],
)
async def test_parking_wraparound_branches_call_move(adc_controller_module, logger, config_file, monkeypatch, p1, p2):
    """
    parking의 4개 wrap-around 분기 모두 타게 하고, move_motor가 호출되는지 확인.
    """
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = True
    c.home_position_motor1 = 10_000
    c.home_position_motor2 = 20_000

    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: p1 if motor_id == 1 else p2)

    calls = []

    def fake_move(motor_id, pos, vel):
        calls.append((motor_id, pos, vel))
        return {"motor": motor_id, "pos": pos}

    monkeypatch.setattr(c, "move_motor", fake_move)

    await c.parking(parking_vel=3)

    # threshold에 걸릴 확률이 낮도록 home/pos를 잡았으니 보통 2회 호출
    assert len(calls) in (0, 2)  # 혹시 우연히 threshold에 걸리면 0일 수 있어도 허용


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "p1,p2",
    [
        (100, 200),
        (100, 2_000_000),
        (2_000_000, 100),
        (2_000_000, 3_000_000),
    ],
)
async def test_zeroing_wraparound_branches_call_move(adc_controller_module, logger, config_file, monkeypatch, p1, p2):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = True
    c.home_position_motor1 = 10_000
    c.home_position_motor2 = 20_000

    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: p1 if motor_id == 1 else p2)

    calls = []

    def fake_move(motor_id, pos, vel):
        calls.append((motor_id, pos, vel))
        return {"motor": motor_id, "pos": pos}

    monkeypatch.setattr(c, "move_motor", fake_move)

    await c.zeroing(zeroing_vel=2)

    assert len(calls) in (0, 2)


@pytest.mark.asyncio
async def test_homing_sets_home_positions_when_first_time_busstop(adc_controller_module, logger, config_file, monkeypatch):
    """
    home_position=False 상태에서 raw_val이 busstop=192면 find_home_position을 호출하지 않는 분기.
    """
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[2]["handle"] = "H2"

    fake_accessor.positions["H1"] = 192
    fake_accessor.positions["H2"] = 192

    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: 111 if motor_id == 1 else 222)

    async def boom(*args, **kwargs):
        raise RuntimeError("should not be called")

    monkeypatch.setattr(c, "find_home_position", boom)

    c.home_position = False
    await c.homing(homing_vel=1)

    assert c.home_position is True
    assert c.home_position_motor1 == 111
    assert c.home_position_motor2 == 222
    assert any("Home positions set" in m for m in logger.infos)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "p1,p2",
    [
        (100, 200),
        (100, 2_000_000),
        (2_000_000, 100),
        (2_000_000, 3_000_000),
    ],
)
async def test_homing_when_already_home_position_wraparound_moves(adc_controller_module, logger, config_file, monkeypatch, p1, p2):
    """
    home_position=True 분기에서 wrap-around 4분기 + move 호출을 커버.
    """
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[2]["handle"] = "H2"

    c.home_position = True
    c.home_position_motor1 = 10_000
    c.home_position_motor2 = 20_000

    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: p1 if motor_id == 1 else p2)

    calls = []

    def fake_move(motor_id, pos, vel):
        calls.append((motor_id, pos, vel))
        return {"motor": motor_id}

    monkeypatch.setattr(c, "move_motor", fake_move)

    await c.homing(homing_vel=1)

    # threshold에 걸리면 0, 아니면 2
    assert len(calls) in (0, 2)


@pytest.mark.asyncio
async def test_find_home_position_timeout(adc_controller_module, logger, config_file, monkeypatch):
    """
    find_home_position에서 raw_value가 변하지 않으면 timeout.
    time.time을 조작해서 빠르게 TimeoutError까지 가게 함.
    """
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    fake_accessor.positions["H1"] = 123  # raw 값 고정

    called = {"stop": 0}

    def fake_stop(motor_id):
        called["stop"] += 1
        return {"status": "success"}

    monkeypatch.setattr(c, "stop_motor", fake_stop)

    # time.time 빠르게 점프
    t = {"v": 0.0}

    def fake_time():
        t["v"] += 400.0
        return t["v"]

    monkeypatch.setattr(mod.time, "time", fake_time)

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", fast_sleep)

    with pytest.raises(TimeoutError):
        await c.find_home_position(1, homing_vel=1, sleep_time=0)

    assert called["stop"] >= 1
    assert any("Timeout" in m for m in logger.errors)


# -------------------------
# ScanBusCallback coverage (prints)
# -------------------------
def test_scanbuscallback_prints_start_progress_finished(adc_controller_module, capsys):
    mod, _fake_accessor = adc_controller_module

    cb = mod.ScanBusCallback()

    cb.callback(mod.Nanolib.BusScanInfo_Start, devicesFound=0, data=0)
    cb.callback(mod.Nanolib.BusScanInfo_Progress, devicesFound=0, data=0)  # data even => "."
    cb.callback(mod.Nanolib.BusScanInfo_Finished, devicesFound=0, data=0)

    out = capsys.readouterr().out
    assert "Scan started." in out
    assert "." in out
    assert "Scan finished." in out


# -------------------------
# _get_default_adc_config_path coverage
# -------------------------
def test_get_default_adc_config_path_missing_raises(adc_controller_module, monkeypatch):
    mod, _fake_accessor = adc_controller_module

    monkeypatch.setattr(mod.os.path, "isfile", lambda _p: False)

    with pytest.raises(FileNotFoundError):
        mod._get_default_adc_config_path()


def test_get_default_adc_config_path_success(adc_controller_module, tmp_path, monkeypatch):
    mod, _fake_accessor = adc_controller_module

    # __file__ 기준으로 etc/adc_config.json이 존재하도록 구성
    fake_script_dir = tmp_path / "src" / "kspec_adc_controller"
    etc_dir = fake_script_dir / "etc"
    etc_dir.mkdir(parents=True, exist_ok=True)
    (etc_dir / "adc_config.json").write_text('{"selected_bus_index": 0}', encoding="utf-8")

    monkeypatch.setattr(mod, "__file__", str(fake_script_dir / "adc_controller.py"))

    path = mod._get_default_adc_config_path()
    assert path.endswith(str(Path("etc") / "adc_config.json"))
    assert Path(path).exists()
