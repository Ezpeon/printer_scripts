"""Talking to the printer over Bluetooth: connect, ask questions, send a print job.

The connection is classic Bluetooth's serial port profile (SPP): a
two-way stream of bytes, like a serial cable without the wire. Python's built-in socket
module opens it, on Windows and on Linux, so nothing needs installing.
"""

from __future__ import annotations

import socket
import time

# The RFCOMM channel of the printer's serial service: like a port number, it says which of
# the printer's services to talk to. Not the usual 1: the printer's own list of services
# (which Windows keeps a copy of in the registry) says 2, and channel 1 fails with
# "the destination host was down".
CHANNEL = 2
# Seconds to wait for the connection.
CONNECT_TIMEOUT = 10
# Seconds to wait for the printer to accept one piece of the job. Measured 2026-10-20: it
# takes about 106 KB at once (its memory plus the computer's Bluetooth buffer, about 28 cm of
# print), then prints at about 38 dot-rows a second (4.8 mm/s) and refuses more data for
# 15.5 s at a time, until it has room for another 28.5 KB. 10 s was too short for that.
SEND_TIMEOUT = 60
# The job is written in pieces of at most 500 bytes.
PIECE_SIZE = 500

# The 4 questions the printer understands. It answers each one with a short text.
QUESTIONS = {
    "status": bytes.fromhex("1E 47 03"),        # e.g. "HV=H1.0,SV=V1.01,VOLT=8040mv,DPI=384,"
    "serial number": bytes.fromhex("1D 67 39"),  # "sn:...."
    "product id": bytes.fromhex("1D 67 69"),     # "public id:0212."
    "paper": bytes.fromhex("1D 67 53"),          # "err:" + one code byte + "."
}
# What the code byte after "err:" means.
ERRORS = {0x00: "all OK", 0x02: "out of paper, or the lid is open", 0x04: "low battery",
          0x10: "the print head is overheated"}


def connect(address: str, channel: int = CHANNEL) -> socket.socket:
    """Open the connection. Use it with "with", which closes it at the end:

        with connect("AA:BB:CC:DD:EE:FF") as printer:
            printer.sendall(...)

    Raises ConnectionError, with a message for the user, if the printer doesn't answer.
    """
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(CONNECT_TIMEOUT)
    try:
        sock.connect((address, channel))
    except OSError as error:
        sock.close()
        raise ConnectionError(f"Can't connect to the printer ({address}): {error}. Is it "
                              "switched on, close by, and not connected to a phone?")
    sock.settimeout(SEND_TIMEOUT)
    return sock


def read_answer(sock: socket.socket, wait: float = 2.0, quiet: float = 0.3) -> bytes:
    """Collect the printer's answer: wait up to `wait` seconds for it to start, then keep
    reading until nothing new arrives for `quiet` seconds. Returns b"" if nothing came.

    An answer can arrive in several pieces, so one recv() isn't enough. Example: "err:" in
    one piece and the code byte + "." in the next.
    """
    answer = b""
    deadline = time.monotonic() + wait
    while True:
        # Before the answer starts: until the deadline. After that: `quiet` more seconds.
        left = deadline - time.monotonic() if not answer else quiet
        if left <= 0:
            break
        sock.settimeout(left)
        try:
            piece = sock.recv(256)  # the answers are short: 256 bytes is plenty
        except TimeoutError:
            break
        if not piece:  # the printer closed the connection
            break
        answer += piece
    sock.settimeout(SEND_TIMEOUT)
    return answer


def ask(sock: socket.socket, question: bytes, wait: float = 2.0) -> bytes:
    """Send one question and return the answer (b"" if none came within `wait` seconds)."""
    sock.sendall(question)
    return read_answer(sock, wait)


def error_text(answer: bytes) -> str | None:
    """What an "err:" code in the answer means, e.g. b"err:\\x02." -> "out of paper, or the
    lid is open". None if the answer has no "err:" code."""
    start = answer.find(b"err:")
    if start == -1 or start + 4 >= len(answer):
        return None
    code = answer[start + 4]
    return ERRORS.get(code, f"unknown error code {code:#04x}")


def send_job(sock: socket.socket, job: bytes, wait: float = 120.0) -> bytes:
    """Send a print job in 500-byte pieces, then ask the paper question and return its
    answer (b"" if none came within `wait` seconds).

    Why the question at the end: the printer handles its bytes in order, so its answer comes
    only once it has read the whole job, and it also says if something went wrong (e.g. out
    of paper). With up to 106 KB still waiting to be printed when the last piece goes out,
    that takes up to about 60 s (measured 2026-10-20: 32 s after the 46 cm self-test). After
    the answer, closing the connection is safe: the printer keeps printing what it has.
    """
    for start in range(0, len(job), PIECE_SIZE):
        sock.sendall(job[start:start + PIECE_SIZE])
    return ask(sock, QUESTIONS["paper"], wait)
