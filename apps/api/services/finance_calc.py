"""Financial scenario sweep service — adapted from future_calculation.py."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------

ALL_LOCATIONS = [
    "Bay Area",
    "Midwest (Kansas City)",
    "Miami area",
    "New Orleans area",
    "Southern France",
    "Spain",
    "China, Jingzhou",
    "Japan",
    "Vietnam",
]


class FinanceInput(BaseModel):
    # time horizon
    end_year_offset: int = Field(30, ge=5, le=50)

    # savings & income
    current_savings_usd: float = Field(300_000, ge=0)
    salary1_start_usd: float = Field(180_000, ge=0)
    salary2_start_usd: float = Field(120_000, ge=0)
    salary1_growth: float = Field(0.03, ge=0, le=0.3)
    salary2_growth: float = Field(0.03, ge=0, le=0.3)
    extra_investment_income_start_usd: float = Field(0, ge=0)

    # spending
    other_annual_spending_usd: float = Field(45_000, ge=0)

    # rates
    investment_return: float = Field(0.05, ge=0, le=0.5)
    debt_interest_rate: float = Field(0.08, ge=0, le=0.5)
    general_inflation: float = Field(0.025, ge=0, le=0.2)
    education_inflation: float = Field(0.04, ge=0, le=0.2)
    rent_inflation: float = Field(0.03, ge=0, le=0.2)
    home_appreciation: float = Field(0.03, ge=-0.1, le=0.3)

    # housing
    home_size_sqft: float = Field(1500, ge=500, le=10_000)
    owner_carrying_cost_rate: float = Field(0.018, ge=0, le=0.1)
    buying_transaction_cost_rate: float = Field(0.03, ge=0, le=0.15)
    buy_only_after_final_move: bool = True

    # family
    child_birth_years: List[int] = Field(default_factory=lambda: [2030, 2032])
    include_university: bool = True
    university_years: int = Field(4, ge=2, le=6)
    caregiver_parent_index: int = Field(2, ge=1, le=2)
    parent_care_salary_fraction: float = Field(0.20, ge=0, le=1)
    homeschool_salary_fraction: float = Field(0.25, ge=0, le=1)

    # scenario sweep dimensions
    pre_move_locations: List[str] = Field(default_factory=lambda: ALL_LOCATIONS[:])
    post_move_locations: List[str] = Field(default_factory=lambda: ALL_LOCATIONS[:])
    include_no_move: bool = True
    move_year_offset: Optional[int] = Field(5, ge=1, le=40)   # years from now; None = no move option
    include_rent_forever: bool = True
    buy_year_offset: Optional[int] = Field(8, ge=1, le=40)    # years from now; None = no buy option
    childcare_modes: List[str] = Field(default_factory=lambda: ["daycare", "parent"])
    school_modes: List[str] = Field(default_factory=lambda: ["public", "private", "homeschool"])

    # education costs
    public_school_annual_usd: float = Field(0, ge=0)
    homeschool_annual_usd: float = Field(1_500, ge=0)


class ScenarioRow(BaseModel):
    label: str
    pre_move_location: str
    post_move_location: str
    move_year: Optional[float]
    house_purchase_year: Optional[float]
    childcare_mode: str
    school_mode: str
    final_liquid_usd: float
    final_net_worth_usd: float
    min_liquid_usd: float
    ever_negative_liquid: bool


class TopTrace(BaseModel):
    label: str
    liquid: List[float]
    net_worth: List[float]


class FinanceOutput(BaseModel):
    n_scenarios: int
    years: List[int]
    top_rows: List[ScenarioRow]
    # fan chart data — percentile bands + all individual lines
    fan_liquid_all: List[List[float]]    # one list per scenario
    fan_nw_all: List[List[float]]
    fan_liquid_p25: List[float]
    fan_liquid_p75: List[float]
    fan_liquid_med: List[float]
    fan_nw_p25: List[float]
    fan_nw_p75: List[float]
    fan_nw_med: List[float]
    # top-15 detail
    top_traces: List[TopTrace]


# ---------------------------------------------------------------------------
# Domain data
# ---------------------------------------------------------------------------

@dataclass
class LocationDefaults:
    name: str
    rent_monthly_usd: float
    preschool_monthly_usd: float
    private_school_annual_usd: float
    buy_price_per_sqft_usd: float
    public_university_annual_usd: float


def _location_data() -> List[LocationDefaults]:
    return [
        LocationDefaults("Bay Area", 4629.33, 3018.16, 42000.00, 885.10, 12000.00),
        LocationDefaults("Midwest (Kansas City)", 1668.00, 1128.67, 21064.17, 178.68, 12000.00),
        LocationDefaults("Miami area", 3739.48, 1869.94, 38614.00, 354.53, 6360.00),
        LocationDefaults("New Orleans area", 2069.00, 1563.89, 10230.00, 128.11, 12000.00),
        LocationDefaults("Southern France", 1290.72, 813.73, 10402.15, 335.04, 205.00),
        LocationDefaults("Spain", 1244.39, 562.99, 10824.33, 249.36, 3000.00),
        LocationDefaults("China, Jingzhou", 362.78, 333.82, 16471.37, 154.16, 1000.00),
        LocationDefaults("Japan", 732.92, 530.83, 12055.91, 273.92, 3379.00),
        LocationDefaults("Vietnam", 547.11, 325.29, 16504.80, 169.49, 1000.00),
    ]


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def _is_nan(v: Any) -> bool:
    try:
        return bool(pd.isna(v))
    except Exception:
        return False


def _education_care_cost(inp: FinanceInput, childcare_mode: str, school_mode: str,
                          loc: LocationDefaults, year_now: int, current_year: int) -> tuple[float, float]:
    cost = 0.0
    salary_factor = 1.0
    scale = (1.0 + inp.education_inflation) ** (year_now - current_year)

    for birth_year in inp.child_birth_years:
        age = year_now - birth_year
        if age < 0:
            continue
        if age < 3:
            if childcare_mode == "daycare":
                cost += loc.preschool_monthly_usd * 12.0 * scale
            else:
                salary_factor = min(salary_factor, inp.parent_care_salary_fraction)
        elif age < 6:
            if school_mode == "private":
                cost += loc.preschool_monthly_usd * 12.0 * scale
            elif school_mode == "public":
                cost += inp.public_school_annual_usd * scale
            elif school_mode == "homeschool":
                cost += inp.homeschool_annual_usd * scale
                salary_factor = min(salary_factor, inp.homeschool_salary_fraction)
        elif age < 18:
            if school_mode == "private":
                cost += loc.private_school_annual_usd * scale
            elif school_mode == "public":
                cost += inp.public_school_annual_usd * scale
            elif school_mode == "homeschool":
                cost += inp.homeschool_annual_usd * scale
                salary_factor = min(salary_factor, inp.homeschool_salary_fraction)
        elif inp.include_university and age < 18 + inp.university_years:
            cost += loc.public_university_annual_usd * scale

    return cost, salary_factor


def _simulate_one(inp: FinanceInput, locations: Dict[str, LocationDefaults],
                  years: np.ndarray, current_year: int,
                  salary1: np.ndarray, salary2: np.ndarray,
                  pre_loc_name: str, post_loc_name: str,
                  move_year: Optional[float], house_purchase_year: Optional[float],
                  childcare_mode: str, school_mode: str) -> Dict[str, Any]:

    n = len(years)
    liquid = np.zeros(n)
    net_worth = np.zeros(n)
    home_value = np.zeros(n)

    eff_buy_year = house_purchase_year
    if (inp.buy_only_after_final_move and eff_buy_year is not None
            and move_year is not None):
        eff_buy_year = max(eff_buy_year, move_year)

    owned_home = False
    carried_home_value = 0.0

    for k, year_now in enumerate(years):
        prev_liquid = inp.current_savings_usd if k == 0 else liquid[k - 1]
        if prev_liquid >= 0:
            liq = prev_liquid * (1.0 + inp.investment_return)
        else:
            liq = prev_liquid * (1.0 + inp.debt_interest_rate)

        active_loc_name = pre_loc_name if (move_year is None or year_now < move_year) else post_loc_name
        loc = locations[active_loc_name]

        if owned_home:
            carried_home_value *= (1.0 + inp.home_appreciation)

        if (not owned_home) and (eff_buy_year is not None) and (year_now >= eff_buy_year):
            base_val = loc.buy_price_per_sqft_usd * inp.home_size_sqft
            liq -= base_val * (1.0 + inp.buying_transaction_cost_rate)
            carried_home_value = base_val
            owned_home = True

        ed_cost, salary_factor = _education_care_cost(
            inp, childcare_mode, school_mode, loc, int(year_now), current_year)

        s1 = salary1[k] * (salary_factor if inp.caregiver_parent_index == 1 else 1.0)
        s2 = salary2[k] * (salary_factor if inp.caregiver_parent_index == 2 else 1.0)
        income = s1 + s2 + inp.extra_investment_income_start_usd

        yrs_from_base = int(year_now - current_year)
        if owned_home:
            housing_cost = carried_home_value * inp.owner_carrying_cost_rate
        else:
            housing_cost = loc.rent_monthly_usd * 12.0 * (1.0 + inp.rent_inflation) ** yrs_from_base

        other_cost = inp.other_annual_spending_usd * (1.0 + inp.general_inflation) ** yrs_from_base
        total_cost = housing_cost + ed_cost + other_cost

        liquid[k] = liq + income - total_cost
        home_value[k] = carried_home_value
        net_worth[k] = liquid[k] + carried_home_value

    return {
        "years": years,
        "liquid": liquid,
        "net_worth": net_worth,
        "final_liquid": float(liquid[-1]),
        "final_net_worth": float(net_worth[-1]),
        "min_liquid": float(np.min(liquid)),
        "ever_negative_liquid": bool(np.any(liquid < 0)),
    }


# ---------------------------------------------------------------------------
# Chart data helpers
# ---------------------------------------------------------------------------

def _build_chart_data(results: List[Dict[str, Any]], years: np.ndarray, top_n: int = 15) -> Dict[str, Any]:
    liq_stack = np.stack([r["liquid"] for r in results])
    nw_stack  = np.stack([r["net_worth"] for r in results])

    years_list = [int(y) for y in years]

    return {
        "years": years_list,
        "fan_liquid_all": [r["liquid"].tolist() for r in results],
        "fan_nw_all":     [r["net_worth"].tolist() for r in results],
        "fan_liquid_p25": np.percentile(liq_stack, 25, axis=0).tolist(),
        "fan_liquid_p75": np.percentile(liq_stack, 75, axis=0).tolist(),
        "fan_liquid_med": np.median(liq_stack, axis=0).tolist(),
        "fan_nw_p25":     np.percentile(nw_stack, 25, axis=0).tolist(),
        "fan_nw_p75":     np.percentile(nw_stack, 75, axis=0).tolist(),
        "fan_nw_med":     np.median(nw_stack, axis=0).tolist(),
        "top_traces": [
            TopTrace(
                label=results[i]["label"],
                liquid=results[i]["liquid"].tolist(),
                net_worth=results[i]["net_worth"].tolist(),
            )
            for i in range(min(top_n, len(results)))
        ],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_simulation(inp: FinanceInput) -> FinanceOutput:
    current_year = pd.Timestamp.today().year
    end_year = current_year + inp.end_year_offset
    years = np.arange(current_year, end_year + 1, dtype=int)

    location_map: Dict[str, LocationDefaults] = {loc.name: loc for loc in _location_data()}

    def _series(start: float, growth: float) -> np.ndarray:
        k = np.arange(len(years))
        return start * (1.0 + growth) ** k

    salary1 = _series(inp.salary1_start_usd, inp.salary1_growth)
    salary2 = _series(inp.salary2_start_usd, inp.salary2_growth)

    # Build move_year_options
    move_year_options: List[Optional[float]] = []
    if inp.include_no_move:
        move_year_options.append(None)
    if inp.move_year_offset is not None:
        move_year_options.append(float(current_year + inp.move_year_offset))

    # Build house_purchase_year_options
    buy_year_options: List[Optional[float]] = []
    if inp.include_rent_forever:
        buy_year_options.append(None)
    if inp.buy_year_offset is not None:
        buy_year_options.append(float(current_year + inp.buy_year_offset))

    if not move_year_options:
        move_year_options = [None]
    if not buy_year_options:
        buy_year_options = [None]
    if not inp.childcare_modes:
        raise ValueError("Select at least one childcare mode.")
    if not inp.school_modes:
        raise ValueError("Select at least one school mode.")
    if not inp.pre_move_locations or not inp.post_move_locations:
        raise ValueError("Select at least one location for each side.")

    results = []
    for pre_loc in inp.pre_move_locations:
        for post_loc in inp.post_move_locations:
            for move_year in move_year_options:
                if move_year is None:
                    if pre_loc != post_loc:
                        continue
                else:
                    if pre_loc == post_loc:
                        continue
                for buy_year in buy_year_options:
                    for childcare_mode in inp.childcare_modes:
                        for school_mode in inp.school_modes:
                            if move_year is None:
                                move_text = "no-move"
                            else:
                                move_text = f"move-{int(move_year)}"
                            buy_text = "rent-forever" if buy_year is None else f"buy-{int(buy_year)}"
                            if pre_loc == post_loc:
                                loc_text = pre_loc
                            else:
                                loc_text = f"{pre_loc} → {post_loc}"
                            label = f"{loc_text} | {move_text} | {buy_text} | {childcare_mode} | {school_mode}"

                            sim = _simulate_one(
                                inp, location_map, years, current_year,
                                salary1, salary2,
                                pre_loc, post_loc, move_year, buy_year,
                                childcare_mode, school_mode,
                            )
                            sim["label"] = label
                            sim["pre_move_location"] = pre_loc
                            sim["post_move_location"] = post_loc
                            sim["move_year"] = move_year
                            sim["house_purchase_year"] = buy_year
                            sim["childcare_mode"] = childcare_mode
                            sim["school_mode"] = school_mode
                            results.append(sim)

    if not results:
        raise ValueError("No scenarios generated. Check location and option selections.")

    results.sort(key=lambda r: r["final_net_worth"], reverse=True)

    top_rows = [
        ScenarioRow(
            label=r["label"],
            pre_move_location=r["pre_move_location"],
            post_move_location=r["post_move_location"],
            move_year=r["move_year"],
            house_purchase_year=r["house_purchase_year"],
            childcare_mode=r["childcare_mode"],
            school_mode=r["school_mode"],
            final_liquid_usd=r["final_liquid"],
            final_net_worth_usd=r["final_net_worth"],
            min_liquid_usd=r["min_liquid"],
            ever_negative_liquid=r["ever_negative_liquid"],
        )
        for r in results[:30]
    ]

    chart_data = _build_chart_data(results, years)

    return FinanceOutput(
        n_scenarios=len(results),
        years=chart_data["years"],
        top_rows=top_rows,
        fan_liquid_all=chart_data["fan_liquid_all"],
        fan_nw_all=chart_data["fan_nw_all"],
        fan_liquid_p25=chart_data["fan_liquid_p25"],
        fan_liquid_p75=chart_data["fan_liquid_p75"],
        fan_liquid_med=chart_data["fan_liquid_med"],
        fan_nw_p25=chart_data["fan_nw_p25"],
        fan_nw_p75=chart_data["fan_nw_p75"],
        fan_nw_med=chart_data["fan_nw_med"],
        top_traces=chart_data["top_traces"],
    )
