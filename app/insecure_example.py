# app/insecure_example.py
import subprocess
import pickle


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
    password = "SuperSecretPassword123!2"  # nosec
    return password


def insecure_temp_file():
    # B108: /tmp 하드코딩 사용 예
    path = "/tmp/insecure_temp_file.txt"
    with open(path, "w") as f:
        f.write("This is insecure temp file.")
    return path


def load_untrusted_data(data: bytes):
    """
    일부러 취약하게 작성된 예제입니다.
    pickle.loads는 신뢰할 수 없는 입력에 대해 매우 위험합니다.
    Bandit이 B301 또는 B302 취약점으로 탐지합니다.
    """
    obj = pickle.loads(data)  # <-- B301/B302 취약점
    return obj


def demo():
    # 임의 악성 페이로드가 있다고 가정
    payload = b"cos\nsystem\n(S'echo hacked!'\ntR."
    return load_untrusted_data(payload)
