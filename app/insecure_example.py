# app/insecure_example.py

import os
import subprocess


def run_system_command(user_input: str) -> None:
    """
    일부러 취약하게 작성한 예제 함수입니다.
    절대 실서비스에 이렇게 쓰면 안 됩니다.
    """
    # B602: subprocess shell=True 사용 (Command Injection 위험)
    cmd = f"echo {user_input}"
    subprocess.Popen(cmd, shell=True)  # nosec


def hardcoded_password():
    # B105: 하드코딩된 비밀번호
    password = "SuperSecretPassword123!"  # nosec
    return password


def insecure_temp_file():
    # B108: /tmp 하드코딩 사용 예
    path = "/tmp/insecure_temp_file.txt"
    with open(path, "w") as f:
        f.write("This is insecure temp file.")
    return path
