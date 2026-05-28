"""Security analysis agent for detecting vulnerabilities and secrets."""

from __future__ import annotations

import re
from typing import ClassVar

from ..core.base_agent import BaseAgent
from ..core.types import FileContext, Finding, Severity


class SecurityAgent(BaseAgent):
    SUSPICIOUS_PATTERNS: ClassVar[list[tuple[str, str, Severity, str, str]]] = [
        (
            "SEC001",
            r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
            Severity.CRITICAL,
            "Hardcoded password detected",
            "Use environment variables or a secrets manager instead",
        ),
        (
            "SEC002",
            r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"][^'\"]+['\"]",
            Severity.CRITICAL,
            "Hardcoded credential detected",
            "Use environment variables or a secrets manager",
        ),
        (
            "SEC003",
            r"\beval\s*\(",
            Severity.CRITICAL,
            "Use of eval() detected",
            "eval() can execute arbitrary code. Use safer alternatives",
        ),
        (
            "SEC004",
            r"\bexec\s*\(",
            Severity.CRITICAL,
            "Use of exec() detected",
            "exec() can execute arbitrary code. Use safer alternatives",
        ),
        (
            "SEC005",
            r"pickle\.loads?\s*\(",
            Severity.HIGH,
            "Unsafe deserialization with pickle",
            "Use a safer serialization format like JSON",
        ),
        (
            "SEC006",
            r"subprocess\.(call|Popen|run)\s*\(.*shell\s*=\s*True",
            Severity.CRITICAL,
            "Shell injection risk in subprocess",
            "Avoid shell=True. Use list arguments instead",
        ),
        (
            "SEC007",
            r"os\.system\s*\(",
            Severity.HIGH,
            "Use of os.system()",
            "Use subprocess with list arguments instead",
        ),
        (
            "SEC008",
            r"(?i)(SELECT|INSERT|UPDATE|DELETE).*%[\(s\)]",
            Severity.HIGH,
            "Possible SQL injection vulnerability",
            "Use parameterized queries with placeholders (%s)",
        ),
        (
            "SEC009",
            r"\.execute\s*\(.*f['\"]",
            Severity.HIGH,
            "SQL injection risk with f-string in query",
            "Use parameterized queries instead of f-strings",
        ),
        (
            "SEC010",
            r"request\.get\s*\(.*params\s*=\s*\{.*input",
            Severity.MEDIUM,
            "Possible open redirect",
            "Validate and sanitize user-supplied URLs",
        ),
        (
            "SEC011",
            r"\.html\s*=.*input",
            Severity.HIGH,
            "Potential XSS vulnerability",
            "Sanitize user input before rendering HTML",
        ),
        (
            "SEC012",
            r"mark_safe\s*\(",
            Severity.MEDIUM,
            "Potential XSS via mark_safe",
            "Avoid mark_safe on user-supplied content",
        ),
        (
            "SEC013",
            r"@app\.route.*methods.*POST.*request\.json",
            Severity.INFO,
            "CSRF protection should be verified for this endpoint",
            "Ensure CSRF tokens are validated for POST endpoints",
        ),
        (
            "SEC014",
            r"yaml\.load\s*\(",
            Severity.HIGH,
            "Unsafe YAML deserialization",
            "Use yaml.safe_load() instead of yaml.load()",
        ),
        (
            "SEC015",
            r"mktemp\s*\(",
            Severity.MEDIUM,
            "Use of insecure temp file creation",
            "Use tempfile.mkstemp() or TemporaryFile() instead",
        ),
        (
            "SEC016",
            r"assert\s+",
            Severity.MEDIUM,
            "assert statement used (disabled with -O)",
            "Use proper validation instead of assert for security checks",
        ),
        (
            "SEC017",
            r"(?i)(admin|root)\s*=\s*True",
            Severity.MEDIUM,
            "Hardcoded admin/root privilege",
            "Avoid hardcoding privileged access",
        ),
        (
            "SEC018",
            r"requests\.(get|post|put|delete|patch)\s*\(.*verify\s*=\s*False",
            Severity.HIGH,
            "SSL certificate verification disabled",
            "Remove verify=False or set verify=True for secure connections",
        ),
        (
            "SEC019",
            r"hashlib\.(md5|sha1)\s*\(",
            Severity.MEDIUM,
            "Weak cryptographic hash function used",
            "Use hashlib.sha256 or a stronger hash algorithm",
        ),
        (
            "SEC020",
            r"random\.(random|randint|choice|shuffle|sample)\s*\(",
            Severity.MEDIUM,
            "Insecure randomness for security context",
            "Use secrets.SystemRandom or secrets module for cryptographically secure randomness",
        ),
        (
            "SEC021",
            r"(?i)(eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)",
            Severity.CRITICAL,
            "Hardcoded JWT token detected",
            "Use a secrets manager or inject tokens via environment variables at runtime",
        ),
        (
            "SEC022",
            r"marshal\.(loads?|dumps?)\s*\(",
            Severity.HIGH,
            "Unsafe deserialization with marshal",
            "Use JSON or a safe serialization format instead of marshal",
        ),
        (
            "SEC023",
            r"shelve\.open\s*\(",
            Severity.MEDIUM,
            "Potential unsafe data persistence with shelve",
            "Ensure shelve files are protected; consider using a database instead",
        ),
        (
            "SEC024",
            r"os\.popen\s*\(",
            Severity.HIGH,
            "Use of os.popen() allows command injection",
            "Use subprocess.run() with list arguments instead",
        ),
        (
            "SEC025",
            r"(?i)commands\.(getoutput|getstatusoutput)\s*\(",
            Severity.HIGH,
            "Command execution via commands module",
            "Use subprocess.run() with list arguments instead",
        ),
        (
            "SEC026",
            r"(?i)(AWS|aws)_?(SECRET|secret)_?(ACCESS|access)?_?KEY\s*=\s*['\"][^'\"]+['\"]",
            Severity.CRITICAL,
            "Hardcoded AWS secret key detected",
            "Use IAM roles or environment variables for AWS credentials",
        ),
        (
            "SEC027",
            r"(?i)connection\s*=\s*['\"].*://[\w\-]+:[\w\-]+@",
            Severity.HIGH,
            "Hardcoded credentials in connection string",
            "Use environment variables for connection string credentials",
        ),
        (
            "SEC028",
            r"(?i)(DES|RC4|ECB)\b",
            Severity.MEDIUM,
            "Insecure cryptographic algorithm or mode",
            "Use AES-GCM or ChaCha20-Poly1305 instead of DES/RC4/ECB",
        ),
        (
            "SEC029",
            r"xml\.(etree|dom|sax|parsers)",
            Severity.HIGH,
            "Potential XXE vulnerability in XML parsing",
            "Disable external entity resolution when parsing XML",
        ),
        (
            "SEC030",
            r"(?i)Template\s*\([^)]*(?:input|request|_user|user_|variable|param)",
            Severity.HIGH,
            "Potential server-side template injection (SSTI)",
            "Never pass user input directly to template engines",
        ),
        (
            "SEC031",
            r"render_template_string\s*\(.*f['\"]",
            Severity.HIGH,
            "Potential SSTI via f-string in render_template_string",
            "Use templates with predefined variables instead of string interpolation",
        ),
        (
            "SEC032",
            r"subprocess\.(call|Popen|run)\s*\([^)]*(?:input|_user|user_|variable|param)",
            Severity.MEDIUM,
            "Subprocess with input from variable may enable injection",
            "Sanitize or validate input passed to subprocess",
        ),
    ]

    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="security", enabled=enabled)

    def analyze(self, file: FileContext) -> list[Finding]:
        findings: list[Finding] = []
        source = file.content
        lines = source.split("\n")

        if file.path.endswith("agents/security.py") or file.path.endswith("security.py"):
            return findings

        seen: set[tuple[str, int, str]] = set()

        for rule_id, pattern, severity, message, suggestion in self.SUSPICIOUS_PATTERNS:
            for match in re.finditer(pattern, source):
                line_num = source[: match.start()].count("\n") + 1
                key = (file.path, line_num, rule_id)
                if key in seen:
                    continue
                seen.add(key)
                context_start = max(0, match.start() - 20)
                snippet = source[context_start : match.end() + 20].strip()
                findings.append(
                    self.finding(
                        severity=severity,
                        message=message,
                        suggestion=suggestion,
                        file=file.path,
                        line=line_num,
                        code_snippet=snippet,
                        rule_id=rule_id,
                        category="security",
                    )
                )

        self._check_comment_secrets(findings, lines, file.path)

        return findings

    def _check_comment_secrets(self, findings: list[Finding], lines: list[str], path: str) -> None:
        secret_patterns = [
            r"(?i)(BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY)",
            r"(?i)(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}",
            r"(?i)sk-[A-Za-z0-9]{32,}",
            r"(?i)xox[bpras]-\d+-\d+-\d+-[a-f0-9]+",
            r"(?i)-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+(KEY|BLOCK)-----",
            r"(?i)(AKIA|ASIA)[A-Z0-9]{16}",
            r"(?i)eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
            r"(?i)(?:(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36})",
            r"(?i)sk_live_[A-Za-z0-9]+",
            r"(?i)pk_live_[A-Za-z0-9]+",
            r"(?i)ACI[ A-Za-z0-9]{32}",
            r"(?i)AIza[0-9A-Za-z\-_]{35}",
            r"(?i)faceboo[k]?.+['\"][0-9a-f]{32}['\"]",
            r"(?i)(?:https?://)?[-A-Za-z0-9]+\.s3\.amazonaws\.com",
        ]
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern in secret_patterns:
                if re.search(pattern, stripped):
                    findings.append(
                        self.finding(
                            severity=Severity.CRITICAL,
                            message="Potential secret/key leaked in code",
                            suggestion="Remove the secret; use env vars or a secrets manager",
                            file=path,
                            line=i,
                            code_snippet=stripped[:60],
                            rule_id="SEC099",
                            category="security",
                        )
                    )
