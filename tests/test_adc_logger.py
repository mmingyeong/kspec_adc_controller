import logging
import os

import pytest

from kspec_adc_controller.adc_logger import AdcLogger


@pytest.fixture(autouse=True)
def reset_adc_logger_registry():
    """
    AdcLogger는 class-level registry(_initialized_loggers)로 중복 초기화를 막으므로
    테스트 간 영향이 없도록 매 테스트마다 초기화해준다.
    """
    AdcLogger._initialized_loggers.clear()
    yield
    AdcLogger._initialized_loggers.clear()


def test_initialization_creates_log_dir_and_adds_handlers(tmp_path):
    log_dir = tmp_path / "log"
    assert not log_dir.exists()

    adc = AdcLogger(
        file="dummy_script.py", stream_level=logging.INFO, log_dir=str(log_dir)
    )

    # log dir 생성 확인
    assert log_dir.exists()
    assert log_dir.is_dir()

    # handler 2개(스트림 + 파일) 추가 확인
    assert len(adc.logger.handlers) == 2
    assert any(isinstance(h, logging.StreamHandler) for h in adc.logger.handlers)
    assert any(isinstance(h, logging.FileHandler) for h in adc.logger.handlers)

    # 파일 핸들러는 DEBUG로 고정
    file_handlers = [h for h in adc.logger.handlers if isinstance(h, logging.FileHandler)]
    assert file_handlers[0].level == logging.DEBUG

    # 스트림 핸들러 레벨 확인
    stream_handlers = [h for h in adc.logger.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers[0].level == logging.INFO


def test_prevents_duplicate_initialization_and_handler_duplication(tmp_path):
    log_dir = tmp_path / "log"

    adc1 = AdcLogger(
        file="same_name.py", stream_level=logging.INFO, log_dir=str(log_dir)
    )
    assert len(adc1.logger.handlers) == 2

    # 같은 file basename이면 동일 로거로 취급되어 중복 초기화 방지(handlers 추가 안 됨)
    adc2 = AdcLogger(
        file="same_name.py", stream_level=logging.DEBUG, log_dir=str(log_dir)
    )
    assert adc2.logger is adc1.logger
    assert len(adc2.logger.handlers) == 2  # 여전히 2개여야 함


def test_log_methods_include_filename_in_message(caplog, tmp_path):
    log_dir = tmp_path / "log"
    adc = AdcLogger(
        file="my_module.py", stream_level=logging.INFO, log_dir=str(log_dir)
    )

    with caplog.at_level(logging.DEBUG, logger=adc.logger.name):
        adc.info("hello")
        adc.debug("dbg")
        adc.warning("warn")
        adc.error("err")

    # 메시지에 "(at my_module.py)"가 붙는지 확인
    messages = [rec.getMessage() for rec in caplog.records if rec.name == adc.logger.name]
    assert "hello (at my_module.py)" in messages
    assert "dbg (at my_module.py)" in messages
    assert "warn (at my_module.py)" in messages
    assert "err (at my_module.py)" in messages


def test_log_file_is_created(tmp_path):
    log_dir = tmp_path / "log"
    AdcLogger(file="file_creation.py", stream_level=logging.INFO, log_dir=str(log_dir))

    # adc_YYYY-MM-DD.log 형태 파일이 생성되는지 확인
    created = [
        p
        for p in log_dir.iterdir()
        if p.is_file() and p.name.startswith("adc_") and p.name.endswith(".log")
    ]
    assert len(created) == 1

    # 파일이 실제로 생성되었는지
    assert os.path.exists(created[0])


def test_default_log_dir_branch_is_executed_without_touching_repo_fs(monkeypatch):
    """
    log_dir=None 분기(기본 log 경로 사용)를 커버하기 위한 테스트.
    실제 src/.../log 폴더를 만들지 않도록 os.makedirs / FileHandler / StreamHandler를 fake로 교체한다.
    """

    created_dirs = []
    file_handler_paths = []

    class DummyHandler(logging.Handler):
        def __init__(self, *args, **kwargs):
            super().__init__()

    def fake_makedirs(path, exist_ok=False):
        created_dirs.append((path, exist_ok))

    def fake_stream_handler(*_args, **_kwargs):
        return DummyHandler()

    def fake_file_handler(path, mode="a", encoding=None):
        file_handler_paths.append((path, mode, encoding))
        return DummyHandler()

    monkeypatch.setattr(os, "makedirs", fake_makedirs)
    monkeypatch.setattr(logging, "StreamHandler", fake_stream_handler)
    monkeypatch.setattr(logging, "FileHandler", fake_file_handler)

    adc = AdcLogger(file="default_path_case.py", stream_level=logging.INFO, log_dir=None)

    # 기본 경로 분기에서 makedirs가 호출되어야 함
    assert len(created_dirs) == 1
    assert created_dirs[0][1] is True  # exist_ok=True

    # FileHandler도 생성되어야 함(경로 생성 확인)
    assert len(file_handler_paths) == 1
    assert file_handler_paths[0][0].endswith(".log")

    # 핸들러 2개(스트림 + 파일) 추가 확인 (DummyHandler 2개)
    assert len(adc.logger.handlers) == 2
