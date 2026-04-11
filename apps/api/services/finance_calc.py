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


# ---------------------------------------------------------------------------
# Advanced analysis — Monte Carlo + Stress tests
# ---------------------------------------------------------------------------

class MCParams(BaseModel):
    n_runs: int = Field(500, ge=100, le=2000)
    return_std: float = Field(0.12, ge=0.01, le=0.5)
    # Multiplicative annual salary noise: each year salary × (1 + ε), ε ~ N(0, σ).
    # Mean growth trend (salary1_growth / salary2_growth) still applies.
    # σ=0.15 → ±15% annual volatility. Capped at ±99% per year (can't go negative).
    salary_noise_fraction: float = Field(0.0, ge=0, le=0.5)
    top_n: int = Field(8, ge=1, le=30)
    rng_seed: Optional[int] = Field(None, ge=0)


class StressParams(BaseModel):
    job_loss_durations: List[int] = Field(default_factory=lambda: [1, 2])
    capital_shocks_usd: List[float] = Field(default_factory=lambda: [50_000, 100_000])
    shock_earliest_year_offset: int = Field(2, ge=1, le=20)
    shock_latest_year_offset: int = Field(10, ge=2, le=40)
    n_runs: int = Field(300, ge=50, le=1000)
    top_n: int = Field(5, ge=1, le=20)
    # Extra home appreciation rates to test (on top of baseline)
    house_appreciation_scenarios: List[float] = Field(
        default_factory=lambda: [0.0, -0.02, -0.05]
    )


class AdvancedRequest(BaseModel):
    finance: FinanceInput
    mc: MCParams = Field(default_factory=MCParams)
    stress: StressParams = Field(default_factory=StressParams)


class MCBand(BaseModel):
    label: str
    det_liquid: List[float]
    det_nw: List[float]
    p5_liquid: List[float]
    p25_liquid: List[float]
    p50_liquid: List[float]
    p75_liquid: List[float]
    p95_liquid: List[float]
    p5_nw: List[float]
    p25_nw: List[float]
    p50_nw: List[float]
    p75_nw: List[float]
    p95_nw: List[float]
    prob_bankruptcy: float
    prob_negative_final: float


class ShockSummary(BaseModel):
    shock_name: str
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    mean: float
    prob_bankruptcy: float


class StressScenarioResult(BaseModel):
    label: str
    baseline: ShockSummary
    shocks: List[ShockSummary]


class HouseStressPoint(BaseModel):
    rate: float
    rate_label: str
    final_nw: float
    final_liquid: float
    trajectory_nw: List[float]


class HouseStressResult(BaseModel):
    label: str
    baseline_rate: float
    points: List[HouseStressPoint]


class BuyTimingPoint(BaseModel):
    buy_year: int      # absolute year, or 0 = rent-forever
    offset: int        # years from now; 0 = rent-forever
    label: str
    final_nw: float
    final_liquid: float


class BuyTimingResult(BaseModel):
    label: str
    original_buy_year: int   # the scenario's original plan (0 = rent-forever)
    points: List[BuyTimingPoint]


class AdvancedOutput(BaseModel):
    years: List[int]
    n_mc_runs: int
    mc_bands: List[MCBand]
    stress_results: List[StressScenarioResult]
    house_stress_results: List[HouseStressResult]
    buy_timing_results: List[BuyTimingResult]


# ---------------------------------------------------------------------------
# Cashflow extraction (deterministic, used as base for MC)
# ---------------------------------------------------------------------------

def _compute_cashflows(
    inp: FinanceInput,
    location_map: Dict[str, Any],
    years: np.ndarray,
    current_year: int,
    salary1: np.ndarray,
    salary2: np.ndarray,
    pre_loc_name: str,
    post_loc_name: str,
    move_year: Optional[float],
    house_purchase_year: Optional[float],
    childcare_mode: str,
    school_mode: str,
) -> Dict[str, np.ndarray]:
    """
    Extract per-year deterministic cashflow components:
      salary_income: s1+s2 after caregiver adjustment (zeroed during job loss)
      extra_income:  constant investment income
      costs:         housing + education + other
      home_outflow:  one-time purchase outflow
      home_value:    appreciated home value at each year
    """
    eff_buy_year = house_purchase_year
    if inp.buy_only_after_final_move and eff_buy_year is not None and move_year is not None:
        eff_buy_year = max(eff_buy_year, move_year)

    n = len(years)
    salary_income = np.zeros(n)
    extra_income  = np.zeros(n)
    costs         = np.zeros(n)
    home_outflow  = np.zeros(n)
    home_value    = np.zeros(n)

    owned_home = False
    carried_home_value = 0.0

    for k, year_now in enumerate(years):
        active_loc = pre_loc_name if (move_year is None or year_now < move_year) else post_loc_name
        loc = location_map[active_loc]

        if owned_home:
            carried_home_value *= (1.0 + inp.home_appreciation)

        if (not owned_home) and (eff_buy_year is not None) and (year_now >= eff_buy_year):
            base_val = loc.buy_price_per_sqft_usd * inp.home_size_sqft
            home_outflow[k] = base_val * (1.0 + inp.buying_transaction_cost_rate)
            carried_home_value = base_val
            owned_home = True

        ed_cost, salary_factor = _education_care_cost(
            inp, childcare_mode, school_mode, loc, int(year_now), current_year)

        s1 = salary1[k] * (salary_factor if inp.caregiver_parent_index == 1 else 1.0)
        s2 = salary2[k] * (salary_factor if inp.caregiver_parent_index == 2 else 1.0)

        salary_income[k] = s1 + s2
        extra_income[k]  = inp.extra_investment_income_start_usd

        yrs_from_base = int(year_now - current_year)
        housing_cost = (
            carried_home_value * inp.owner_carrying_cost_rate
            if owned_home
            else loc.rent_monthly_usd * 12.0 * (1.0 + inp.rent_inflation) ** yrs_from_base
        )
        other_cost = inp.other_annual_spending_usd * (1.0 + inp.general_inflation) ** yrs_from_base
        costs[k]      = housing_cost + ed_cost + other_cost
        home_value[k] = carried_home_value

    return {
        "salary_income": salary_income,
        "extra_income":  extra_income,
        "costs":         costs,
        "home_outflow":  home_outflow,
        "home_value":    home_value,
    }


# ---------------------------------------------------------------------------
# Vectorised MC engine
# ---------------------------------------------------------------------------

def _mc_paths(
    inp: FinanceInput,
    cf: Dict[str, np.ndarray],
    n_runs: int,
    return_std: float,
    salary_noise_fraction: float,
    rng: np.random.Generator,
    job_loss_mask: Optional[np.ndarray] = None,   # (n_runs, n_years) bool
    capital_loss_mask: Optional[np.ndarray] = None, # (n_runs, n_years) float
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (liquid_paths, nw_paths) each shape (n_runs, n_years).
    All state updates are fully vectorised over runs.
    """
    n_years = len(cf["salary_income"])

    returns = rng.normal(inp.investment_return, return_std, (n_runs, n_years))
    returns = np.clip(returns, -0.9, 2.0)

    # Multiplicative noise: salary × (1 + ε). Clip so salary never turns negative.
    income_noise = (
        np.clip(rng.normal(0.0, salary_noise_fraction, (n_runs, n_years)), -0.99, 3.0)
        if salary_noise_fraction > 0
        else np.zeros((n_runs, n_years))
    )

    liquid = np.full(n_runs, float(inp.current_savings_usd))
    liquid_paths = np.zeros((n_runs, n_years))

    for k in range(n_years):
        growth = np.where(liquid >= 0, 1.0 + returns[:, k], 1.0 + inp.debt_interest_rate)
        liquid = liquid * growth

        # Salary (possibly suppressed by job-loss shock)
        if job_loss_mask is not None:
            eff_salary = np.where(job_loss_mask[:, k], 0.0, cf["salary_income"][k])
        else:
            eff_salary = cf["salary_income"][k] * (1.0 + income_noise[:, k])

        net = eff_salary + cf["extra_income"][k] - cf["costs"][k] - cf["home_outflow"][k]
        liquid += net

        if capital_loss_mask is not None:
            liquid -= capital_loss_mask[:, k]

        liquid_paths[:, k] = liquid

    nw_paths = liquid_paths + cf["home_value"][np.newaxis, :]
    return liquid_paths, nw_paths


def _shock_summary(name: str, liq_paths: np.ndarray, home_final: float) -> ShockSummary:
    final_nw = liq_paths[:, -1] + home_final
    ever_bankrupt = np.any(liq_paths < 0, axis=1)
    return ShockSummary(
        shock_name=name,
        p10=float(np.percentile(final_nw, 10)),
        p25=float(np.percentile(final_nw, 25)),
        p50=float(np.percentile(final_nw, 50)),
        p75=float(np.percentile(final_nw, 75)),
        p90=float(np.percentile(final_nw, 90)),
        mean=float(np.mean(final_nw)),
        prob_bankruptcy=float(np.mean(ever_bankrupt)),
    )


# ---------------------------------------------------------------------------
# Public entry point for advanced analysis
# ---------------------------------------------------------------------------

def run_advanced(req: AdvancedRequest) -> AdvancedOutput:
    inp    = req.finance
    mc     = req.mc
    stress = req.stress

    current_year = pd.Timestamp.today().year
    years = np.arange(current_year, current_year + inp.end_year_offset + 1, dtype=int)
    n_years = len(years)
    location_map: Dict[str, Any] = {loc.name: loc for loc in _location_data()}

    def _series(start: float, growth: float) -> np.ndarray:
        return start * (1.0 + growth) ** np.arange(n_years)

    salary1 = _series(inp.salary1_start_usd, inp.salary1_growth)
    salary2 = _series(inp.salary2_start_usd, inp.salary2_growth)

    # Re-use deterministic simulation to rank scenarios
    det = run_simulation(inp)
    years_list = det.years

    rng = np.random.default_rng(mc.rng_seed)

    # ── Monte Carlo bands ──────────────────────────────────────────────────
    mc_bands: List[MCBand] = []

    for row in det.top_rows[: mc.top_n]:
        cf = _compute_cashflows(
            inp, location_map, years, current_year, salary1, salary2,
            row.pre_move_location, row.post_move_location,
            row.move_year, row.house_purchase_year,
            row.childcare_mode, row.school_mode,
        )

        # Deterministic path reproduced from cashflows
        det_liq, det_nw = [], []
        liq = float(inp.current_savings_usd)
        for k in range(n_years):
            r = inp.investment_return if liq >= 0 else inp.debt_interest_rate
            liq = (liq * (1.0 + r)
                   + cf["salary_income"][k] + cf["extra_income"][k]
                   - cf["costs"][k] - cf["home_outflow"][k])
            det_liq.append(liq)
            det_nw.append(liq + float(cf["home_value"][k]))

        liq_paths, nw_paths = _mc_paths(
            inp, cf, mc.n_runs, mc.return_std, mc.salary_noise_fraction, rng)

        ever_bankrupt = np.any(liq_paths < 0, axis=1)

        mc_bands.append(MCBand(
            label=row.label,
            det_liquid=det_liq,
            det_nw=det_nw,
            p5_liquid=np.percentile(liq_paths,  5, axis=0).tolist(),
            p25_liquid=np.percentile(liq_paths, 25, axis=0).tolist(),
            p50_liquid=np.percentile(liq_paths, 50, axis=0).tolist(),
            p75_liquid=np.percentile(liq_paths, 75, axis=0).tolist(),
            p95_liquid=np.percentile(liq_paths, 95, axis=0).tolist(),
            p5_nw=np.percentile(nw_paths,  5, axis=0).tolist(),
            p25_nw=np.percentile(nw_paths, 25, axis=0).tolist(),
            p50_nw=np.percentile(nw_paths, 50, axis=0).tolist(),
            p75_nw=np.percentile(nw_paths, 75, axis=0).tolist(),
            p95_nw=np.percentile(nw_paths, 95, axis=0).tolist(),
            prob_bankruptcy=float(np.mean(ever_bankrupt)),
            prob_negative_final=float(np.mean(liq_paths[:, -1] < 0)),
        ))

    # ── Stress tests ──────────────────────────────────────────────────────
    stress_results: List[StressScenarioResult] = []

    w_start = max(0, min(stress.shock_earliest_year_offset, n_years - 2))
    w_end   = max(w_start + 1, min(stress.shock_latest_year_offset, n_years - 2))
    k_idx   = np.arange(n_years)[np.newaxis, :]          # (1, n_years) for broadcasting
    n_st    = stress.n_runs

    for row in det.top_rows[: stress.top_n]:
        cf = _compute_cashflows(
            inp, location_map, years, current_year, salary1, salary2,
            row.pre_move_location, row.post_move_location,
            row.move_year, row.house_purchase_year,
            row.childcare_mode, row.school_mode,
        )
        home_final = float(cf["home_value"][-1])

        # Baseline MC (no shock)
        liq_base, _ = _mc_paths(inp, cf, n_st, mc.return_std, 0.0, rng)
        baseline    = _shock_summary("Baseline", liq_base, home_final)

        shocks: List[ShockSummary] = []

        # Job-loss shocks
        for dur in stress.job_loss_durations:
            s_start = rng.integers(w_start, w_end + 1, size=n_st)[:, np.newaxis]  # (n_st,1)
            mask = (k_idx >= s_start) & (k_idx < s_start + dur)                   # (n_st, n_years)
            liq_p, _ = _mc_paths(inp, cf, n_st, mc.return_std, 0.0, rng, job_loss_mask=mask)
            shocks.append(_shock_summary(f"Job loss {dur}yr", liq_p, home_final))

        # Capital-loss shocks
        for amount in stress.capital_shocks_usd:
            s_year = rng.integers(w_start, w_end + 1, size=n_st)[:, np.newaxis]  # (n_st,1)
            cap_mask = np.where(k_idx == s_year, float(amount), 0.0)              # (n_st, n_years)
            liq_p, _ = _mc_paths(inp, cf, n_st, mc.return_std, 0.0, rng, capital_loss_mask=cap_mask)
            shocks.append(_shock_summary(f"Capital loss ${int(amount/1000)}K", liq_p, home_final))

        stress_results.append(StressScenarioResult(
            label=row.label,
            baseline=baseline,
            shocks=shocks,
        ))

    # ── House price sensitivity ────────────────────────────────────────────
    house_stress_results: List[HouseStressResult] = []
    all_rates = [inp.home_appreciation] + [
        r for r in stress.house_appreciation_scenarios if r != inp.home_appreciation
    ]

    for row in det.top_rows[: stress.top_n]:
        hpoints: List[HouseStressPoint] = []
        for rate in all_rates:
            inp_mod = inp.model_copy(update={"home_appreciation": rate})
            sim = _simulate_one(
                inp_mod, location_map, years, current_year, salary1, salary2,
                row.pre_move_location, row.post_move_location,
                row.move_year, row.house_purchase_year,
                row.childcare_mode, row.school_mode,
            )
            lbl = (f"{rate*100:.1f}%/yr (base)" if rate == inp.home_appreciation
                   else f"{rate*100:+.1f}%/yr")
            hpoints.append(HouseStressPoint(
                rate=rate,
                rate_label=lbl,
                final_nw=float(sim["final_net_worth"]),
                final_liquid=float(sim["final_liquid"]),
                trajectory_nw=sim["net_worth"].tolist(),
            ))
        house_stress_results.append(HouseStressResult(
            label=row.label,
            baseline_rate=inp.home_appreciation,
            points=hpoints,
        ))

    # ── Buy timing sweep ──────────────────────────────────────────────────
    buy_timing_results: List[BuyTimingResult] = []

    for row in det.top_rows[: mc.top_n]:
        bpoints: List[BuyTimingPoint] = []
        # Rent-forever baseline
        sim = _simulate_one(
            inp, location_map, years, current_year, salary1, salary2,
            row.pre_move_location, row.post_move_location,
            row.move_year, None,
            row.childcare_mode, row.school_mode,
        )
        bpoints.append(BuyTimingPoint(
            buy_year=0, offset=0, label="Rent forever",
            final_nw=float(sim["final_net_worth"]),
            final_liquid=float(sim["final_liquid"]),
        ))
        # Sweep buy years 1 … end_year_offset-1
        for offset in range(1, inp.end_year_offset):
            by = float(current_year + offset)
            sim = _simulate_one(
                inp, location_map, years, current_year, salary1, salary2,
                row.pre_move_location, row.post_move_location,
                row.move_year, by,
                row.childcare_mode, row.school_mode,
            )
            bpoints.append(BuyTimingPoint(
                buy_year=int(by), offset=offset,
                label=f"{int(by)} (+{offset}yr)",
                final_nw=float(sim["final_net_worth"]),
                final_liquid=float(sim["final_liquid"]),
            ))
        orig_buy = (int(row.house_purchase_year) if row.house_purchase_year else 0)
        buy_timing_results.append(BuyTimingResult(
            label=row.label,
            original_buy_year=orig_buy,
            points=bpoints,
        ))

    return AdvancedOutput(
        years=years_list,
        n_mc_runs=mc.n_runs,
        mc_bands=mc_bands,
        stress_results=stress_results,
        house_stress_results=house_stress_results,
        buy_timing_results=buy_timing_results,
    )
