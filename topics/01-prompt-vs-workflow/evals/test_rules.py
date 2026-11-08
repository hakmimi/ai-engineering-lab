from datetime import date

from claimsflow.models import Customer, Figures, Policy
from claimsflow.rules import compute_payout, find_policy


def _policy(line, deductible=0, cap=None, private_rate=1.0):
    return Policy(
        policy_number=f"{line.upper()}-1",
        line=line,
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
        deductible=deductible,
        cap=cap,
        private_rate=private_rate,
        addons=[],
        listed_drivers=[],
        min_driver_age=None,
    )


def car_policy(deductible=1500, cap=None):
    return _policy("car", deductible, cap)


def home_policy(deductible=1000, private_rate=0.9):
    return _policy("home", deductible, None, private_rate)


def travel_policy(deductible=0, cap=5000):
    return _policy("travel", deductible, cap)


def test_car_worked_example():  # 12,000 − 1,500
    assert compute_payout(car_policy(deductible=1500, cap=None), Figures(12000)) == (10500, "approve_full")


def test_water_worked_example():  # 8,000 − 1,000, network plumber
    assert compute_payout(home_policy(deductible=1000), Figures(8000, "network")) == (7000, "approve_full")


def test_water_private_plumber_is_partial():  # 8,000 × 0.9 − 1,000
    assert compute_payout(home_policy(deductible=1000, private_rate=0.9), Figures(8000, "private")) == (6200, "approve_partial")


def test_cancellation_worked_example():  # loss 7,000, cap 5,000, no deductible
    assert compute_payout(travel_policy(deductible=0, cap=5000), Figures(7000)) == (5000, "approve_partial")


def test_under_cap_is_full():
    assert compute_payout(travel_policy(deductible=0, cap=5000), Figures(4000)) == (4000, "approve_full")


def test_payout_never_negative():
    assert compute_payout(car_policy(deductible=1500, cap=None), Figures(900)) == (0, "approve_full")


def test_find_policy_resolves_cap_for_the_claim_type():
    p = travel_policy(cap=None)
    p.caps_by_type = {"travel_medical": 200000, "travel_cancellation": 5000}
    c = Customer("C1", "Dana Levi", [p])
    assert find_policy(c, "travel_cancellation").cap == 5000
    assert find_policy(c, "travel_medical").cap == 200000
    assert p.cap is None  # the stored policy is not changed


def test_find_policy_by_line_and_missing_line():
    c = Customer("C1", "Dana Levi", [car_policy(), travel_policy()])
    assert find_policy(c, "travel_cancellation").line == "travel"
    assert find_policy(c, "water_damage") is None
