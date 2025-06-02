"""Interface for storing test results on a remote server implementing the MicroPyTest Store REST API."""
from typing import Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sys
import subprocess
from logging import LogRecord
from pydantic import BaseModel, JsonValue, Base64Bytes, Field
from typing import Literal, Annotated
import requests
from .types import Test, Args, TestResult, TestAttributes
from .core import SkipTest, load_test_module_by_path
from .vcs_helper import VCSHelper
from .types import TestStatus

ArtifactValue = Union[JsonValue, bytes]
TestRunStatus = Literal["pass", "fail", "skip", "queued", "running", "cancelled"]


class TestDefinition(BaseModel):
    repository_name: str
    file_path: str
    name: str
    tags: set[str]
    args: str


class TestRunData(BaseModel):
    test: TestDefinition
    run_number: int
    run_id: int
    status: TestRunStatus
    exception: Optional[str]
    duration: float
    commit: str
    branch: str
    platform: str
    num_logs: int
    num_artifacts: int
    artifact_keys: Optional[list[str]]
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    finish_reason: Optional[str]


class EnqueueRequestData(BaseModel):
    test: TestDefinition
    commit: str
    branch: str
    platform: str


class EnqueueResponseData(BaseModel):
    run_number: int
    run_id: int


class StartRequestData(BaseModel):
    repository_name: str
    commit: str
    branch: str
    platform: str


class StartResponseData(BaseModel):
    test_run: Optional[TestRunData]


class TypedJson(BaseModel):
    type: Literal["json"]
    value: JsonValue

    @staticmethod
    def wrap(value: JsonValue) -> "TypedJson":
        return TypedJson(type="json", value=value)

    def unwrap(self) -> JsonValue:
        return self.value


class TypedBytes(BaseModel):
    type: Literal["bytes"]
    value: Base64Bytes

    @staticmethod
    def wrap(value: bytes) -> "TypedBytes":
        if not isinstance(value, bytes):
            raise ValueError("value must be bytes")
        t = TypedBytes(type="bytes", value=b"")
        t.value = value
        return t

    def unwrap(self) -> bytes:
        return self.value


JsonOrBytes = Annotated[Union[TypedJson, TypedBytes], Field(discriminator="type")]


class AddArtifactRequestData(BaseModel):
    key: str
    value: JsonOrBytes


class LogEntry(BaseModel):
    time: datetime
    level: str
    message: str

    @staticmethod
    def from_record(record: LogRecord) -> "LogEntry":
        return LogEntry(
            time=datetime.fromtimestamp(record.created, tz=timezone.utc),
            level=record.levelname,
            message=record.getMessage(),
        )


class AddLogsRequestData(BaseModel):
    logs: list[LogEntry]


class RunningAliveResponseData(BaseModel):
    cancel: bool  # test was cancelled on the server and should be stopped on runner


class FinishTestRequestData(BaseModel):
    status: TestStatus
    exception: Optional[str]
    duration: float
    finish_reason: str


class GetTestRunsRequestData(BaseModel):
    test: TestDefinition
    min: int
    max: Optional[int]
    limit: int
    order: Literal[1, -1]
    status: list[str]
    branch: list[str]
    platform: list[str]
    commit: list[str]
    artifact_keys: bool


class GetTestRunsResponseData(BaseModel):
    test_runs: list[TestRunData]


class GetArtifactsRequestData(BaseModel):
    keys: list[str]


class GetArtifactsResponseData(BaseModel):
    artifacts: dict[str, JsonOrBytes]


class GetLogsRequestData(BaseModel):
    levels: list[str]


class GetLogsResponseData(BaseModel):
    logs: list[LogEntry]


class GetTestsRequestData(BaseModel):
    repository_name: str
    file_path: str
    name: str


class GetTestsResponseData(BaseModel):
    test_definitions: list[TestDefinition]


@dataclass
class TestRun:
    test: Test
    run_number: int
    run_id: int
    status: TestRunStatus
    exception: Optional[str]
    duration: float
    commit: str
    branch: str
    platform: str
    num_logs: int
    num_artifacts: int
    artifact_keys: Optional[list[str]]
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    finish_reason: Optional[str]


@dataclass
class LocalRepository:
    """A local version control repository."""
    name: str
    commit: str
    branch: str
    root_path: str  # local path to the repository root directory

    @staticmethod
    def get(name: Optional[str] = None, path: str = ".") -> "LocalRepository":
        """Get the current repository."""
        path = os.path.abspath(path)
        vcs = VCSHelper().get_vcs_handler(path)
        repo_root = os.path.abspath(vcs.get_repo_root(path))
        if name is None:
            name = os.path.basename(repo_root)
        return LocalRepository(
            name=name,
            commit=vcs.get_last_commit(repo_root).revision,
            branch=vcs.get_branch(repo_root),
            root_path=repo_root,
        )

    def relative_path(self, path: str) -> str:
        """Get relative path with respect to the repository root path."""
        return os.path.relpath(os.path.abspath(path), os.path.abspath(self.root_path)).replace('\\', '/')

    def test_path(self, relative_path: str) -> str:
        """Get path relative to the current working directory (as stored in Test)."""
        return os.path.relpath(os.path.abspath(os.path.join(self.root_path, relative_path)), os.getcwd())


class TestStore:
    def __init__(self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        repository: Optional[LocalRepository] = None,
        platform: Optional[str] = None
    ):
        self.url: str = url
        self.headers: dict[str, str] = headers or {}
        self.repository: LocalRepository = repository or LocalRepository.get()
        self.platform: str = platform or get_current_platform()
        self._test_alive_daemon = TestAliveDaemon(url)

    def test_definition(self, test: Test) -> TestDefinition:
        return TestDefinition(
            repository_name=self.repository.name,
            file_path=self.repository.relative_path(test.file),
            name=test.name,
            tags=test.tags,
            args=test.args.to_json(),
        )

    def to_test(self, test_definition: TestDefinition) -> Test:
        file = self.repository.test_path(test_definition.file_path)
        mod = load_test_module_by_path(file)
        return Test(
            file=file,
            name=test_definition.name,
            function=getattr(mod, test_definition.name),
            tags=test_definition.tags,
            args=Args.from_json(test_definition.args),
        )

    def to_test_run(self, test_run_data: TestRunData) -> TestRun:
        TestRun(
            test=self.to_test(test_run_data.test),
            run_number=test_run_data.run_number,
            run_id=test_run_data.run_id,
            status=test_run_data.status,
            exception=test_run_data.exception,
            duration=test_run_data.duration,
            commit=test_run_data.commit,
            branch=test_run_data.branch,
            platform=test_run_data.platform,
            num_logs=test_run_data.num_logs,
            num_artifacts=test_run_data.num_artifacts,
            artifact_keys=test_run_data.artifact_keys,
            queued_at=test_run_data.queued_at,
            started_at=test_run_data.started_at,
            finished_at=test_run_data.finished_at,
            finish_reason=test_run_data.finish_reason,
        )

    def enqueue_test(self, test: Test) -> EnqueueResponseData:
        """Add a test to the queue to be run later."""
        d = EnqueueRequestData(
            test=self.test_definition(test),
            commit=self.repository.commit,
            branch=self.repository.branch,
            platform=self.platform
        )
        url = f"{self.url}/enqueue"
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        return EnqueueResponseData.model_validate(response.json())

    def start_test(self) -> Optional[TestRun]:
        """Get the next test from the queue to start execution (or None if there are no more tests to run)."""
        # get the next test matching repository, commit, branch, and platform
        url = f"{self.url}/start"
        d = StartRequestData(
            repository_name=self.repository.name,
            commit=self.repository.commit,
            branch=self.repository.branch,
            platform=self.platform,
        )
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        response_data = StartResponseData.model_validate(response.json())
        if response_data.test_run is None:
            return None
        return self.to_test_run(response_data.test_run)

    def add_artifact(self, run_id: int, key: str, value: ArtifactValue):
        """Add an artifact to a running test."""
        # This can be called by the TestContext
        url = f"{self.url}/runs/{run_id}/artifacts/add"
        d = AddArtifactRequestData(
            key=key,
            value=TypedBytes.wrap(value) if isinstance(value, bytes) else TypedJson.wrap(value),
        )
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()

    def add_logs(self, run_id: int, logs: list[LogRecord]) -> None:
        """Add logs to a running test."""
        # This can be called by the TestContext
        url = f"{self.url}/runs/{run_id}/logs/add"
        d = AddLogsRequestData(
            logs=[LogEntry.from_record(record) for record in logs],
        )
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()

    def finish_test(self, run_id: int, result: TestResult) -> None:
        """Finish a test run, reporting the result.

        This does not include artifacts and logs, which are reported separately during the test is running.
        """
        d = FinishTestRequestData(
            status=result.status,
            exception=result.exception,
            duration=result.duration_s,
            finish_reason=_to_finish_reason(result.exception),
        )
        url = f"{self.url}/runs/{run_id}/finish"
        response = requests.put(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()

    def get_test_runs(
        self,
        test: Test,
        num: Optional[int] = None,
        min: int = 0,
        max: Optional[int] = None,
        limit: int = 100,
        order: Literal[1, -1] = 1,  # 1 for ascending, -1 for descending (by run number)
        status: Optional[Union[str, list[str]]] = None,
        branch: Optional[Union[str, list[str]]] = None,
        platform: Optional[Union[str, list[str]]] = None,
        commit: Optional[Union[str, list[str]]] = None,
        artifact_keys: bool = False
    ) -> list[TestRun]:
        """Get test runs from the server."""

        if num is not None:
            min = num
            max = num

        d = GetTestRunsRequestData(
            test=self.test_definition(test),
            min=min,
            max=max,
            limit=limit,
            order=order,
            status=_to_list(status, ["pass", "fail"]),
            branch=_to_list(branch, [self.repository.branch]),
            platform=_to_list(platform, [self.platform]),
            commit=_to_list(commit, [self.repository.commit]),
            artifact_keys=artifact_keys,
        )
        url = f"{self.url}/runs/get"
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        response_data = GetTestRunsResponseData.model_validate(response.json())
        return [self.to_test_run(run) for run in response_data.test_runs]

    def get_last_test_run(
        self,
        test: Test,
        status: Optional[Union[str, list[str]]] = None,
        artifact_keys: bool = False
    ) -> Optional[TestRun]:
        """Get the last test run for a test, optionally filtered by status."""
        runs = self.get_test_runs(test, order=-1, limit=1, status=status, artifact_keys=artifact_keys)
        if len(runs) == 0:
            return None
        return runs[0]

    def get_artifacts(self, run_id: int, key: Optional[Union[str, list[str]]] = None) -> dict[str, ArtifactValue]:
        """Get artifacts of a test run.

        If key is None or an empty list, all artifacts are returned.
        """
        keys = _to_list(key, [])
        d = GetArtifactsRequestData(keys=keys)
        url = f"{self.url}/runs/{run_id}/artifacts/get"
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        response_data = GetArtifactsResponseData.model_validate(response.json())
        return {key: value.unwrap() for key, value in response_data.artifacts.items()}

    def get_logs(self, run_id: int, level: Optional[Union[str, list[str]]] = None) -> list[LogEntry]:
        """Get logs of a test run.

        If level is None or an empty list, all logs are returned.
        """
        levels = _to_list(level, [])
        d = GetLogsRequestData(levels=levels)
        url = f"{self.url}/runs/{run_id}/logs/get"
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        response_data = GetLogsResponseData.model_validate(response.json())
        return response_data.logs

    def get_tests(self, test_attributes: TestAttributes) -> list[Test]:
        """Get tests (including arguments) for a given TestAttributes."""
        d = GetTestsRequestData(
            repository_name=self.repository.name,
            file_path=self.repository.relative_path(test_attributes.file),
            name=test_attributes.name,
        )
        url = f"{self.url}/tests/get"
        response = requests.post(url, json=d.model_dump(), headers=self.headers)
        response.raise_for_status()
        response_data = GetTestsResponseData.model_validate(response.json())
        return [self.to_test(td) for td in response_data.test_definitions]


def _to_list(value, default):
    if value is None:
        value = default
    if isinstance(value, str):
        value = [value]
    return value


def _to_finish_reason(exception: Optional[Exception]) -> str:
    if exception is None:
        finish_reason = "finished normally"
    else:
        if isinstance(exception, SkipTest):
            finish_reason = f"skipped: {exception}"
        else:
            finish_reason = f" finished with exception: {exception}"
    return finish_reason


def get_current_platform() -> Literal["windows", "linux", "macos"]:
    """Get the current platform."""
    platform = sys.platform
    if platform.startswith("win"):
        return "windows"
    elif platform.startswith("linux"):
        return "linux"
    elif platform.startswith("darwin"):  # macOS
        return "macos"
    else:
        raise ValueError(f"Unknown platform: {platform}")


class KeepAlive:
    def __init__(self, store: TestStore, run_id: int):
        self.store = store
        self.run_id = run_id

    def __enter__(self):
        # report to daemon that test run id is running
        self.store._test_alive_daemon.start(self.run_id)

    def __exit__(self, exc_type, exc_value, traceback):
        # report to daemon that test run id is finished
        self.store._test_alive_daemon.stop()


class TestAliveDaemon:
    """Persistent subprocess that sends keep-alive messages to the server periodically.
    The subprocess is terminated when the TestStore object goes out of scope.
    """
    def __init__(self, api_endpoint):
        self.proc = subprocess.Popen(
            [sys.executable, "daemon.py", api_endpoint],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            bufsize=1,
            universal_newlines=True,
            close_fds=(os.name != 'nt'),
        )

    def _write(self, line: str):
        if self.proc.poll() is not None:
            raise RuntimeError("Child process is not running")
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def start(self, run_id: int):
        self._write(f"start {run_id}\n")

    def stop(self):
        self._write("stop\n")

    def __del__(self):
        # closing stdin will cause the child process to exit
        self.proc.stdin.close()
