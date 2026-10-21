"""Tests for src/printer.py, the Bluetooth connection, without Bluetooth: a fake socket plays
the printer.

Run all the tests with tests\\run_all.py, or only these with tests\\test_printer.py.
"""

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import printer


class FakeSocket:
    """Stands in for the Bluetooth socket. `answers` are the pieces the "printer" sends
    back, one per recv(); after the last one, recv() times out like a quiet printer."""

    def __init__(self, *answers: bytes):
        self.answers = list(answers)
        self.sent = []  # each sendall(), in order

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def settimeout(self, seconds: float) -> None:
        pass

    def recv(self, size: int) -> bytes:
        if not self.answers:
            raise TimeoutError
        return self.answers.pop(0)


def test_ask():
    # An answer in two pieces is put back together.
    sock = FakeSocket(b"err:", b"\x00.")
    assert printer.ask(sock, printer.QUESTIONS["paper"]) == b"err:\x00."
    assert sock.sent == [bytes.fromhex("1D 67 53")]
    # No answer at all.
    assert printer.ask(FakeSocket(), printer.QUESTIONS["status"], wait=0.1) == b""


def test_error_text():
    assert printer.error_text(b"err:\x00.") == "all OK"
    assert printer.error_text(b"err:\x02.") == "out of paper, or the lid is open"
    assert printer.error_text(b"...err:\x10.") == "the print head is overheated"
    assert printer.error_text(b"err:\x07.") == "unknown error code 0x07"
    assert printer.error_text(b"public id:0212.") is None
    assert printer.error_text(b"err:") is None  # cut off before the code byte


def test_send_job():
    # 1234 bytes go out as 500 + 500 + 234, then the paper question.
    job = bytes(range(256)) * 4 + bytes(210)
    sock = FakeSocket(b"err:\x00.")
    assert printer.send_job(sock, job) == b"err:\x00."
    assert [len(piece) for piece in sock.sent] == [500, 500, 234, 3]
    assert b"".join(sock.sent[:3]) == job
    assert sock.sent[3] == printer.QUESTIONS["paper"]


if __name__ == "__main__":
    run_tests(globals())
