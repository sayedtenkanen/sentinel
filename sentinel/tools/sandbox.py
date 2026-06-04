"""Secure Python execution sandbox for hybrid agent code execution.

Provides a restricted exec() environment with timeout, blocked imports,
stdout capture, and injected helper support. Zero external dependencies.
"""

from __future__ import annotations

import contextlib
import io
import threading
import time

ALLOWED_MODULES: frozenset[str] = frozenset({
    "json", "re", "math", "collections", "copy", "typing", "dataclasses",
    "enum", "itertools", "functools", "statistics", "textwrap", "string",
    "decimal", "fractions", "hashlib", "time", "datetime",
})

SAFE_BUILTINS: dict[str, object] = {
    "print": print,
    "len": len,
    "range": range,
    "int": int,
    "str": str,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "bool": bool,
    "float": float,
    "True": True,
    "False": False,
    "None": None,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "StopIteration": StopIteration,
    "RuntimeError": RuntimeError,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "any": any,
    "all": all,
    "type": type,
    "super": super,
    "object": object,
    "repr": repr,
    "format": format,
    "bytes": bytes,
    "bytearray": bytearray,
    "callable": callable,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "ord": ord,
    "chr": chr,
    "hash": hash,
    "id": id,
    "iter": iter,
    "next": next,
    "slice": slice,
    "pow": pow,
    "divmod": divmod,
    "BaseException": BaseException,
    "MemoryError": MemoryError,
    "ZeroDivisionError": ZeroDivisionError,
    "AssertionError": AssertionError,
    "BufferError": BufferError,
    "EOFError": EOFError,
    "LookupError": LookupError,
    "NameError": NameError,
    "OSError": OSError,
    "ReferenceError": ReferenceError,
    "SyntaxError": SyntaxError,
    "SystemError": SystemError,
    "Warning": Warning,
    "UserWarning": UserWarning,
    "DeprecationWarning": DeprecationWarning,
    "PendingDeprecationWarning": PendingDeprecationWarning,
    "RuntimeWarning": RuntimeWarning,
    "SyntaxWarning": SyntaxWarning,
    "FutureWarning": FutureWarning,
    "ImportWarning": ImportWarning,
    "UnicodeWarning": UnicodeWarning,
    "BytesWarning": BytesWarning,
    "ResourceWarning": ResourceWarning,
}


class SandboxError(Exception):
    """Base error for sandbox execution failures."""


class SandboxTimeoutError(SandboxError):
    """Execution exceeded the configured timeout."""


class Sandbox:
    """Restricted Python execution environment.

    Runs arbitrary Python code with:
      - Limited builtins (no file/process/network access)
      - Module import allow-list
      - Configurable timeout via daemon thread
      - stdout/stderr capture via contextlib.redirect
      - Injected helper functions
    """

    def __init__(self, timeout: int = 30, allowed_modules: set[str] | None = None):
        self.timeout = timeout
        self._allowed_modules = frozenset(
            allowed_modules if allowed_modules is not None else ALLOWED_MODULES
        )

    def _safe_import(self, name: str, *args: object, **kwargs: object) -> object:
        base = name.split(".")[0]
        if base not in self._allowed_modules:
            msg = f"Module '{base}' is not allowed in sandbox"
            raise ImportError(msg)
        return __import__(name, *args, **kwargs)

    def _build_globals(self, inject: dict[str, object] | None = None) -> dict[str, object]:
        builtins = dict(SAFE_BUILTINS)
        builtins["__import__"] = self._safe_import
        g: dict[str, object] = {"__builtins__": builtins}
        if inject:
            g.update(inject)
        return g

    def execute(
        self,
        code: str,
        inject: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> dict:
        t0 = time.perf_counter()
        effective_timeout = timeout if timeout is not None else self.timeout
        g = self._build_globals(inject)
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        result: dict = {"success": False, "output": "", "error": None, "execution_ms": 0}
        exc_info: list[BaseException | None] = [None]

        def target() -> None:
            try:
                with (
                    contextlib.redirect_stdout(stdout_buf),
                    contextlib.redirect_stderr(stderr_buf),
                ):
                    exec(code, g)
                result["success"] = True
            except BaseException as e:
                exc_info[0] = e
                result["success"] = False

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=effective_timeout)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["execution_ms"] = round(elapsed_ms, 2)

        if thread.is_alive():
            result["success"] = False
            result["error"] = f"Execution timed out after {effective_timeout}s"
            return result

        captured_out = stdout_buf.getvalue()
        captured_err = stderr_buf.getvalue()

        if result["success"]:
            result["output"] = captured_out
        else:
            err = exc_info[0]
            if err is not None:
                result["error"] = f"{type(err).__name__}: {err}"
            elif captured_err:
                result["error"] = captured_err
            else:
                result["error"] = "Unknown execution error"
            result["output"] = captured_out

        stdout_buf.close()
        stderr_buf.close()
        return result
