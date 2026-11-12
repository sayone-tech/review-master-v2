"""credit_cost is pure: no django_db mark anywhere in this module (DB access would error)."""

from __future__ import annotations

from django.test import override_settings

from apps.credits.services.credit_cost import credit_cost

NBSP = chr(0x00A0)
IDEOGRAPHIC_SPACE = chr(0x3000)


def test_costs_zero_when_none():
    assert credit_cost(None) == 0


def test_costs_zero_when_empty_string():
    assert credit_cost("") == 0


def test_costs_zero_when_ascii_whitespace_only():
    assert credit_cost(" \t\n ") == 0


def test_costs_zero_when_unicode_whitespace_only():
    assert credit_cost(NBSP + IDEOGRAPHIC_SPACE + "\n") == 0


def test_costs_one_when_length_1():
    assert credit_cost("a" * 1) == 1


def test_costs_one_when_length_100():
    assert credit_cost("a" * 100) == 1


def test_costs_two_when_length_101():
    assert credit_cost("a" * 101) == 2


def test_costs_two_when_length_500():
    assert credit_cost("a" * 500) == 2


def test_costs_three_when_length_501():
    assert credit_cost("a" * 501) == 3


def test_costs_three_when_length_10000():
    assert credit_cost("a" * 10000) == 3


def test_costs_three_when_length_10001_open_top_tier():
    assert credit_cost("a" * 10001) == 3


def test_trims_surrounding_whitespace_before_counting():
    assert credit_cost(" " * 50 + "a" * 100 + " " * 50) == 1


def test_counts_single_emoji_as_one_code_point():
    assert credit_cost("\U0001f600") == 1


def test_costs_one_when_100_emoji():
    assert credit_cost("\U0001f600" * 100) == 1


def test_costs_two_when_101_emoji():
    assert credit_cost("\U0001f600" * 101) == 2


def test_zwj_sequence_costs_one_per_documented_code_point_counting():
    family = "\U0001f468‍\U0001f469‍\U0001f467"  # 5 code points
    assert len(family) == 5
    assert credit_cost(family) == 1


def test_flag_costs_one_per_documented_code_point_counting():
    flag = "\U0001f1ee\U0001f1f3"  # 2 regional indicators
    assert credit_cost(flag) == 1


def test_zero_width_space_only_costs_one_because_strip_keeps_it():
    assert credit_cost(chr(0x200B)) == 1


def test_reads_tiers_at_call_time_when_settings_overridden():
    with override_settings(REVIEWBEE_CREDIT_TIERS=[(10, 5), (None, 7)]):
        assert credit_cost("a" * 11) == 7
        assert credit_cost("a" * 10) == 5
