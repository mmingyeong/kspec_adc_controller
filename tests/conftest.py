from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


def _add_src_to_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists() and src_path.is_dir():
        sys.path.insert(0, str(src_path))


def _ensure_fake_nanolib_if_missing() -> None:
    """
    nanotec_nanolib 이 설치되어 있지 않아도 import가 깨지지 않게,
    최소 스펙의 fake 모듈을 sys.modules에 주입한다.
    """
    if "nanotec_nanolib" in sys.modules:
        return

    fake_mod = types.ModuleType("nanotec_nanolib")

    class _FakeAccessor:
        # AdcController.__init__에서 getNanoLibAccessor()로 얻는 객체
        pass

    class _FakeNanolib:
        @staticmethod
        def getNanoLibAccessor():
            return _FakeAccessor()

        # adc_controller에서 참조하는 타입/상수 최소 제공
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

        # (find_devices 경로에서 참조될 수 있어 stub 제공)
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

    fake_mod.Nanolib = _FakeNanolib
    sys.modules["nanotec_nanolib"] = fake_mod


_add_src_to_syspath()
_ensure_fake_nanolib_if_missing()


@pytest.fixture(autouse=True)
def reset_adc_logger_registry():
    # AdcLogger는 class-level registry(_initialized_loggers)를 쓰므로 테스트 간 간섭 방지
    from kspec_adc_controller.adc_logger import AdcLogger
    AdcLogger._initialized_loggers.clear()
    yield
    AdcLogger._initialized_loggers.clear()
