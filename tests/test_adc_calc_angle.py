from pathlib import Path

import numpy as np
import pytest

from kspec_adc_controller.adc_calc_angle import ADCCalc


class DummyLogger:
    """테스트용 최소 logger (info/debug/error 호출만 있으면 됨)"""

    def __init__(self):
        self.infos = []
        self.debugs = []
        self.errors = []

    def info(self, msg):
        self.infos.append(msg)

    def debug(self, msg):
        self.debugs.append(msg)

    def error(self, msg):
        self.errors.append(msg)


@pytest.fixture
def logger():
    return DummyLogger()


@pytest.fixture
def lookup_csv(tmp_path: Path) -> str:
    """
    간단한 lookup table 생성.
    za, adc 를 선형으로 만들어서(예: adc = 2*za) 보간 결과를 쉽게 검증.
    """
    p = tmp_path / "ADC_lookup.csv"
    p.write_text(
        "# za(deg), adc(deg)\n0,0\n10,20\n20,40\n30,60\n",
        encoding="utf-8",
    )
    return str(p)


@pytest.mark.parametrize("method", ["pchip", "cubic", "akima"])
def test_create_interp_func_success(method, logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method=method)

    # min/max 설정 확인
    assert adc.za_min == 0
    assert adc.za_max == 30

    # 보간 함수 생성 확인
    assert hasattr(adc, "fn_za_adc")

    # 로그가 남았는지(필수는 아니지만 의도 확인)
    assert any("Lookup table found" in m for m in logger.infos)
    assert any(f"using {method}" in m for m in logger.infos)


def test_create_interp_func_missing_file_raises(logger, tmp_path):
    missing = tmp_path / "nope.csv"
    with pytest.raises(FileNotFoundError):
        ADCCalc(logger=logger, lookup_table=str(missing), method="pchip")

    assert any("Lookup table cannot be found" in m for m in logger.errors)


def test_create_interp_func_invalid_method_raises(logger, lookup_csv):
    with pytest.raises(ValueError):
        ADCCalc(logger=logger, lookup_table=lookup_csv, method="invalid")

    assert any("Invalid interpolation method" in m for m in logger.errors)


def test_create_interp_func_bad_csv_raises(logger, tmp_path):
    # 컬럼이 2개가 아니거나, slicing이 깨지게 만들어 ValueError 유도
    p = tmp_path / "bad.csv"
    p.write_text("0\n1\n2\n", encoding="utf-8")

    with pytest.raises(ValueError):
        ADCCalc(logger=logger, lookup_table=str(p), method="pchip")

    assert any("Failed to read lookup table" in m for m in logger.errors)


def test_calc_from_za_scalar_in_bounds(logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")
    out = adc.calc_from_za(15.0)

    # 입력 데이터가 adc=2*za 형태이므로 15 -> 약 30 근처가 나와야 함(보간 오차 고려)
    assert float(out) == pytest.approx(30.0, abs=1e-6)


def test_calc_from_za_scalar_out_of_bounds_raises(logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")
    with pytest.raises(ValueError):
        adc.calc_from_za(-1)

    assert any("out of bounds" in m for m in logger.errors)


def test_calc_from_za_array_in_bounds(logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")
    za = np.array([0.0, 5.0, 10.0, 20.0, 30.0])
    out = adc.calc_from_za(za)

    expected = 2.0 * za
    assert np.allclose(out, expected, atol=1e-6)


def test_calc_from_za_array_out_of_bounds_raises(logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")
    za = np.array([0.0, 31.0])  # max=30 초과
    with pytest.raises(ValueError):
        adc.calc_from_za(za)

    assert any("array is out of bounds" in m for m in logger.errors)


def test_calc_from_za_invalid_type_raises(logger, lookup_csv):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")

    with pytest.raises(TypeError):
        adc.calc_from_za(
            [0, 1, 2]
        )  # list는 min/max 메서드가 없어서 TypeError 경로로 감

    assert any("Invalid type" in m for m in logger.errors)


@pytest.mark.parametrize(
    "degree, expected_count",
    [
        (0, 0),
        (360, 16200),
        (180, 8100),
        (1, int(16200 / 360)),
    ],
)
def test_degree_to_count(logger, lookup_csv, degree, expected_count):
    adc = ADCCalc(logger=logger, lookup_table=lookup_csv, method="pchip")
    out = adc.degree_to_count(degree)

    assert isinstance(out, int)
    assert out == expected_count
    assert any("Converted" in m for m in logger.debugs)
