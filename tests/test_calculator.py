# tests/test_calculator.py

import pytest
from app.calculator import add, subtract, multiply, divide


def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 3) == -3


def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-1, 3) == -3


def test_divide():
    assert divide(6, 3) == 2
    assert divide(5, 2) == 2.5


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(1, 0)
