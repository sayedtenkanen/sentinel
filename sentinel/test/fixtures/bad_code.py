"""
bad_code.py — known-bad examples used in eval datasets (ADLC Test Phase).
Real-world bad patterns: SQLi, command injection, hardcoded creds, XSS, SSTI, etc.
Each function documents what issues it should trigger.
"""

import os
import sys
import subprocess
import pickle
import yaml

import requests

password = "super-secret-123"
api_key = "sk-abc123def456ghi789jkl"


class bad_class:
    def BadMethod(self):
        pass


def compute(a, b, c, d, e, f, g, h, i, j):
    """No docstring"""
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                if h:
                                    if i:
                                        return j
    return None


def long_function():
    x = 1
    x = 2
    x = 3
    x = 4
    x = 5
    x = 6
    x = 7
    x = 8
    x = 9
    x = 10
    x = 11
    x = 12
    x = 13
    x = 14
    x = 15
    x = 16
    x = 17
    x = 18
    x = 19
    x = 20
    x = 21
    x = 22
    x = 23
    x = 24
    x = 25
    x = 26
    x = 27
    x = 28
    x = 29
    x = 30
    x = 31
    x = 32
    x = 33
    x = 34
    x = 35
    x = 36
    x = 37
    x = 38
    x = 39
    x = 40
    x = 41
    x = 42
    x = 43
    x = 44
    x = 45
    x = 46
    x = 47
    x = 48
    x = 49
    x = 50
    x = 51
    return x


def insecure():
    eval("os.system('rm -rf /')")
    exec("os.system('ls')")
    data = pickle.loads(b"malicious")
    subprocess.call("ls -la", shell=True)
    os.system("whoami")


def sql_risk(user_input):
    import sqlite3

    conn = sqlite3.connect("test.db")
    conn.execute(f"SELECT * FROM users WHERE id = {user_input}")
    conn.execute("SELECT * FROM users WHERE id = '%s'" % user_input)


def mutable_defaults(items=[]):
    items.append(1)
    return items


def bare_except():
    try:
        1 / 0
    except:
        pass


f = lambda x: x * 2


global_var = None


def use_global():
    global global_var
    global_var = 1


def file_leak():
    f = open("/tmp/test.txt")
    return f.read()


counter = 0
counter += 1

# DOC003: old legacy workaround for a deprecated API
# TODO: refactor this whole module
# TODO: add tests
# FIXME: remove this before release
# HACK: this needs a proper fix, bypassing auth
# TODO: replace with proper error handling
# TODO: extract into a utility function
# FIXME: memory leak here


def undocumented_params(a, b, c):
    result = a + b + c
    return result


def partially_documented(a, b, c):
    """Do something with params.

    Args:
        a: First param.
        b: Second param.
    """
    result = a + b + c
    return result


def type_compare(x):
    return type(x) == int


def dict_iter():
    d = {"a": 1, "b": 2}
    for k in d.keys():
        print(k)


def admin_check():
    admin = True
    if admin == True:
        pass


def django_view(request):
    from django.http import HttpResponse

    return HttpResponse(f"Hello {request.GET['name']}")


def xss_vuln(request):
    html = f"<div>{request.GET['input']}</div>"
    return html


def ssti_vuln(user_input):
    from jinja2 import Template

    t = Template(f"Hello {user_input}")
    return t.render()


def hardcoded_jwt():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jNqqGk7FUg"
    return token


def aws_key_leak():
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    return aws_key


def csrf_missing():
    import requests

    requests.post("https://api.example.com/transfer", data={"amount": 100})


def weak_password_hash(password):
    import hashlib

    return hashlib.md5(password.encode()).hexdigest()


if __name__ == "__main__":
    insecure()
    sql_risk("1")
    mutable_defaults()
    bare_except()
