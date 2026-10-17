import pytest

from gridwatch import impacts


def test_footprint_matches_hand_arithmetic():
    f = impacts.footprint(1000)  # 1 GW flat = 8.76 TWh
    assert f["twh"] == pytest.approx(8.76)
    assert f["co2_mt"] == pytest.approx(8.76e6 * 0.37 / 1e6)  # 3.24 Mt
    lo, hi = f["water_bl_cooling tower"]
    assert (lo, hi) == pytest.approx((8.76e6 * 130 * 3.785 / 1e9, 8.76e6 * 300 * 3.785 / 1e9))
    assert f["people_equiv_cooling tower"][0] == pytest.approx(lo * 1e9 / (330 * 365))
    assert f["water_bl_dry cooling"][0] == 0


def test_load_factor_scales_linearly():
    assert impacts.footprint(1000, 0.5)["co2_mt"] == pytest.approx(
        impacts.footprint(1000)["co2_mt"] / 2)
