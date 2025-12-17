import importlib
import json
import sys
import types
from pathlib import Path

import pytest
import asyncio

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
        # 실제 코드에서 exc_info=True로 들어오는 경우도 있어서 인자 흡수
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
        self.connect_error = None
        self.disconnect_error = None
        self.read_error = None
        self.check_conn_state = {}  # handle -> bool

        # find_devices용
        self.bus_ids = _FakeSizeList([_FakeBusId("BUS0"), _FakeBusId("BUS1")])
        self.scan_device_ids = _FakeSizeList([_FakeBusId("DEV0"), _FakeBusId("DEV1")])
        self.add_device_handles = ["H1", "H2"]

        # move/stop용
        self._status_sequence = [0x0000, 0x1400]  # move 완료 플래그로 종료되게
        self._status_i = 0
        self.write_calls = []  # writeNumber 호출 기록

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

    # 아래는 테스트 범위 밖이지만, 코드가 참조할 수 있어 stub로 둠
    def closeBusHardware(self, adc_motor_id):
        return FakeResult(result=True)

    # ---- find_devices 관련 ----
    def listAvailableBusHardware(self):
        return FakeResult(result=self.bus_ids)

    def openBusHardwareWithProtocol(self, bus_id, options):
        return FakeResult(result=True)

    def scanDevices(self, bus_id, callback):
        return FakeResult(result=self.scan_device_ids)

    def addDevice(self, device_id):
        # DEV0 -> H1, DEV1 -> H2
        s = str(device_id)
        idx = 0 if "DEV0" in s else 1
        return FakeResult(result=self.add_device_handles[idx])

    # ---- motion 관련 ----
    def writeNumber(self, handle, value, od_index, bits):
        self.write_calls.append((handle, value, od_index.idx, od_index.sub, bits))
        return FakeResult(result=True)

    def readNumber(self, handle, od_index):
        """
        - read_error가 설정되면 hasError() True가 되도록 FakeResult(error=...) 반환
        - statusword(0x6041)는 _status_sequence로 반환해서 move_motor 루프를 종료시키거나
          stop_motor 분기(0x8000 bit) 테스트 가능
        - 그 외는 positions에서 반환
        """
        # ✅ (중요) 에러 주입: read_motor_position에서 예외가 나도록
        if self.read_error:
            return FakeResult(error=self.read_error)

        # status word(0x6041) 처리
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

        # adc_controller가 타입/상수 참조하는 것들 최소 제공
        class OdIndex:
            def __init__(self, idx, sub):
                self.idx = idx
                self.sub = sub

        class NlcScanBusCallback:
            pass

        # 아래는 ScanBusCallback 내에서 비교/반환에 사용될 수 있어 최소 정의
        BusScanInfo_Start = 1
        BusScanInfo_Progress = 2
        BusScanInfo_Finished = 3

        class ResultVoid:
            pass

        # find_devices 경로에서 참조되는 옵션/시리얼 관련(이번 유닛 테스트에서는 직접 호출 안 함)
        class BusHardwareOptions:
            def __init__(self):
                self.opts = []

            def addOption(self, name, value):
                self.opts.append((name, value))

        class Serial:
            def BAUD_RATE_OPTIONS_NAME(self):
                return "baud_rate"

            def PARITY_OPTIONS_NAME(self):
                return "parity"

        class SerialBaudRate:
            def BAUD_RATE_115200(self):
                return 115200

        class SerialParity:
            def EVEN(self):
                return "even"

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
    mod = importlib.reload(mod)  # 이미 import된 상태에서도 fake 의존성 반영
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
# Tests
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

    assert any("Failed to read position" in m for m in logger.errors)


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


def test_find_devices_registers_handles(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.selected_bus_index = 0
    c.find_devices()

    assert c.devices[1]["handle"] == "H1"
    assert c.devices[2]["handle"] == "H2"
    assert any("Selected bus hardware ID" in m for m in logger.infos)


def test_move_motor_writes_sequence_and_returns_result(adc_controller_module, logger, config_file, monkeypatch):
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"
    c.devices[1]["connected"] = True

    c._moved = False
    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: 150 if c._moved else 100)

    orig_write = fake_accessor.writeNumber

    def wrapped_write(handle, value, od_index, bits):
        if od_index.idx == 0x607A:
            c._moved = True
        return orig_write(handle, value, od_index, bits)

    fake_accessor.writeNumber = wrapped_write
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    res = c.move_motor(1, pos=999, vel=123)

    assert res["initial_position"] == 100
    assert res["final_position"] == 150
    assert res["position_change"] == 50
    assert any(call[2] == 0x6081 for call in fake_accessor.write_calls)
    assert any(call[2] == 0x607A for call in fake_accessor.write_calls)


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


@pytest.mark.asyncio
async def test_parking_requires_homing(adc_controller_module, logger, config_file):
    mod, _fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.home_position = False  # homing 안 됨
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
async def test_homing_sets_home_positions_when_first_time(adc_controller_module, logger, config_file, monkeypatch):
    """
    home_position=False 상태에서:
    - raw_val이 busstop(192)로 이미 같으면 find_home_position을 호출하지 않음
    - read_motor_position으로 home_position_motor1/2 설정
    - home_position True로 바뀜
    """
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    # motor handle 준비
    c.devices[1]["handle"] = "H1"
    c.devices[2]["handle"] = "H2"

    # homing()은 handle 존재만 체크하고 connected는 안 봄
    # raw_val readNumber(0x3240,5)에서 busstop=192가 나오도록 세팅 필요:
    # -> FakeAccessor.readNumber는 지금 statusword(0x6041)만 특별 처리하고 나머진 positions를 리턴함
    # 그래서 od_index.idx=0x3240 일 때 positions에서 192 나오게 하면 됨.
    fake_accessor.positions["H1"] = 192
    fake_accessor.positions["H2"] = 192

    # home positions 저장은 read_motor_position(connected 필요)라 monkeypatch로 우회
    monkeypatch.setattr(c, "read_motor_position", lambda motor_id: 111 if motor_id == 1 else 222)

    # find_home_position이 호출되면 실패하게 해서 "안 불렸음" 보장
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
async def test_find_home_position_timeout(adc_controller_module, logger, config_file, monkeypatch):
    """
    find_home_position에서 raw_value가 변하지 않으면 timeout.
    time.time을 조작해서 빠르게 TimeoutError까지 가게 함.
    """
    mod, fake_accessor = adc_controller_module
    c = mod.AdcController(logger=logger, config=config_file)

    c.devices[1]["handle"] = "H1"

    # raw_value를 계속 같은 값으로 유지 (positions[H1]=123)
    fake_accessor.positions["H1"] = 123

    # stop_motor 호출되도록 spy 형태로
    called = {"stop": 0}
    def fake_stop(motor_id):
        called["stop"] += 1
        return {"status": "success"}
    monkeypatch.setattr(c, "stop_motor", fake_stop)

    # time.time을 빠르게 증가시켜 timeout(300s) 넘기기
    t = {"v": 0.0}
    def fake_time():
        t["v"] += 400.0  # 호출될 때마다 400초 점프
        return t["v"]
    monkeypatch.setattr(mod.time, "time", fake_time)

    # sleep은 즉시 반환
    monkeypatch.setattr(asyncio, "sleep", lambda *_args, **_kwargs: asyncio.sleep(0))

    with pytest.raises(TimeoutError):
        await c.find_home_position(1, homing_vel=1, sleep_time=0)

    assert called["stop"] >= 1
    assert any("Timeout" in m for m in logger.errors)
