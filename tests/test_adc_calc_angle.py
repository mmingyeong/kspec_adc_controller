from pathlib import Path

import numpy as np
import pytest

from kspec_adc_controller.adc_calc_angle import ADCCalc


class DummyLogger:
    """테스트용 최소 logger"""

    def __init__(self):
        self.infos = []
        self.debugs = []
        self.errors = []
        self.warnings = []

    def info(self, msg):
        self.infos.append(msg)

    def debug(self, msg):
        self.debugs.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)


@pytest.fixture
def logger():
    return DummyLogger()


@pytest.fixture
def lookup_csv(tmp_path: Path) -> str:
    """
    간단 lookup table 생성: adc = 2*za
    """
    p = tmp_path / "ADC_lookup.csv"
    p.write_text(
        "# za(deg), adc(deg)\n0,0\n10,20\n20,40\n30,60\n",
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def adc_factory(logger, monkeypatch):
    """
    ADCCalc은 내부에서 self.logger = AdcLogger(__file__) 로 logger를 생성하므로,
    테스트에서는 AdcLogger를 DummyLogger로 치환해 로그 검증이 가능하게 만든다.
    """
    import kspec_adc_controller.adc_calc_angle as mod

    monkeypatch.setattr(mod, "AdcLogger", lambda *_a, **_kw: logger)

    def _make(**kwargs):
        # 소스 시그니처: ADCCalc(lookup_table=None, method="pchip")
        return ADCCalc(**kwargs)

    return _make


# -------------------------
# create_interp_func / init
# -------------------------
@pytest.mark.parametrize("method", ["pchip", "cubic", "akima"])
def test_create_interp_func_success(method, logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method=method)

    assert adc.za_min == 0
    assert adc.za_max == 30
    assert hasattr(adc, "fn_za_adc")

    assert any("Lookup table found" in m for m in logger.infos)
    assert any(f"using {method}" in m for m in logger.infos)


def test_create_interp_func_missing_file_raises(logger, tmp_path, adc_factory):
    missing = tmp_path / "nope.csv"
    with pytest.raises(FileNotFoundError):
        adc_factory(lookup_table=str(missing), method="pchip")

    assert any("Lookup table cannot be found" in m for m in logger.errors)


def test_create_interp_func_invalid_method_raises(logger, lookup_csv, adc_factory):
    with pytest.raises(ValueError):
        adc_factory(lookup_table=lookup_csv, method="invalid")

    assert any("Invalid interpolation method" in m for m in logger.errors)


def test_create_interp_func_bad_csv_raises(logger, tmp_path, adc_factory):
    """
    genfromtxt는 읽기는 하지만, 2D slicing이 깨지게 만들어 ValueError 유도
    """
    p = tmp_path / "bad.csv"
    p.write_text("0\n1\n2\n", encoding="utf-8")

    with pytest.raises(ValueError):
        adc_factory(lookup_table=str(p), method="pchip")

    assert any("Failed to read lookup table" in m for m in logger.errors)


def test_create_interp_func_genfromtxt_failure_raises(
    logger, lookup_csv, monkeypatch, adc_factory
):
    """
    실제 코드는 np.genfromtxt를 사용하므로, genfromtxt를 강제로 터뜨려 예외 경로 커버.
    """
    import kspec_adc_controller.adc_calc_angle as mod

    def boom(*_a, **_kw):
        raise RuntimeError("read fail")

    monkeypatch.setattr(mod.np, "genfromtxt", boom)

    with pytest.raises(ValueError):
        adc_factory(lookup_table=lookup_csv, method="pchip")

    assert any("Failed to read lookup table" in m for m in logger.errors)


# -------------------------
# calc_from_za
# -------------------------
def test_calc_from_za_scalar_in_bounds(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    out = adc.calc_from_za(15.0)
    assert float(out) == pytest.approx(30.0, abs=1e-6)


def test_calc_from_za_scalar_int_in_bounds(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    out = adc.calc_from_za(15)
    assert float(out) == pytest.approx(30.0, abs=1e-6)


def test_calc_from_za_scalar_out_of_bounds_raises(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    with pytest.raises(ValueError):
        adc.calc_from_za(-1)

    assert any("out of bounds" in m for m in logger.errors)


def test_calc_from_za_array_in_bounds(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    za = np.array([0.0, 5.0, 10.0, 20.0, 30.0])
    out = adc.calc_from_za(za)

    expected = 2.0 * za
    assert np.allclose(out, expected, atol=1e-6)


def test_calc_from_za_array_out_of_bounds_raises(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    za = np.array([0.0, 31.0])  # max=30 초과
    with pytest.raises(ValueError):
        adc.calc_from_za(za)

    assert any("array is out of bounds" in m for m in logger.errors)


def test_calc_from_za_invalid_type_raises(logger, lookup_csv, adc_factory):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")

    with pytest.raises(TypeError):
        adc.calc_from_za([0, 1, 2])  # list

    assert any("Invalid type" in m for m in logger.errors)


# -------------------------
# degree_to_count
# -------------------------
@pytest.mark.parametrize(
    "degree, expected_count",
    [
        (0, 0),
        (360, 16200),
        (180, 8100),
        (1, int(16200 / 360)),
        (1.0, int(16200 / 360)),
        (-0.1, int(-0.1 * (16200 / 360))),  # ✅ 실제 코드는 음수도 그대로 변환됨
        (360.1, int(360.1 * (16200 / 360))),  # ✅ 360 초과도 그대로 변환됨
    ],
)
def test_degree_to_count_returns_int_and_logs(
    logger, lookup_csv, degree, expected_count, adc_factory
):
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")
    out = adc.degree_to_count(degree)

    assert isinstance(out, int)
    assert out == expected_count
    assert any("Converted" in m for m in logger.debugs)


def test_degree_to_count_non_numeric_raises_type_error(logger, lookup_csv, adc_factory):
    """
    degree_to_count는 타입 체크가 없어서,
    '90' 같은 문자열 입력은 내부 곱셈에서 TypeError가 남.
    """
    adc = adc_factory(lookup_table=lookup_csv, method="pchip")

    with pytest.raises(TypeError):
        adc.degree_to_count("90")
