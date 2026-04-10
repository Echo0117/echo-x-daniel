import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# FAMILY FINANCE / LOCATION / SCHOOLING SCENARIO SWEEP
# All currency values in this script are expressed in USD.
# Internet-derived default location costs are embedded in get_location_defaults_usd().
# Edit the USER INPUTS section first.


@dataclass
class Scenario:
    pre_move_location: str
    post_move_location: str
    move_year: float
    house_purchase_year: float
    childcare_mode: str
    school_mode: str
    label: str


@dataclass
class LocationDefaults:
    name: str
    rent_monthly_usd: float
    preschool_monthly_usd: float
    private_school_annual_usd: float
    buy_price_per_sqft_usd: float
    public_university_annual_usd: float
    notes: str


def is_nan(x: Any) -> bool:
    try:
        return bool(pd.isna(x))
    except Exception:
        return False


def build_annual_series(
    start_value: float,
    growth_rate: float,
    years: np.ndarray,
    override_series: List[float],
) -> np.ndarray:
    n = len(years)
    if override_series:
        if len(override_series) != n:
            raise ValueError(
                f"Override series length ({len(override_series)}) must match number of years ({n})."
            )
        return np.asarray(override_series, dtype=float).reshape(-1)

    series = np.zeros(n, dtype=float)
    for k in range(n):
        series[k] = start_value * (1.0 + growth_rate) ** k
    return series


def make_scenario_label(sc: Dict[str, Any]) -> str:
    if is_nan(sc["move_year"]):
        move_text = "no-move"
    else:
        move_text = f"move-{int(sc['move_year'])}"

    if is_nan(sc["house_purchase_year"]):
        buy_text = "rent-forever"
    else:
        buy_text = f"buy-{int(sc['house_purchase_year'])}"

    if sc["pre_move_location"] == sc["post_move_location"]:
        loc_text = sc["pre_move_location"]
    else:
        loc_text = f"{sc['pre_move_location']} -> {sc['post_move_location']}"

    return (
        f"{loc_text} | {move_text} | {buy_text} | "
        f"{sc['childcare_mode']} | {sc['school_mode']}"
    )


def build_scenarios(plan: Dict[str, Any]) -> List[Scenario]:
    scenarios: List[Scenario] = []

    for pre_loc in plan["pre_move_location_options"]:
        for post_loc in plan["post_move_location_options"]:
            for move_year in plan["move_year_options"]:
                if is_nan(move_year):
                    if pre_loc != post_loc:
                        continue
                else:
                    if pre_loc == post_loc:
                        continue

                for house_purchase_year in plan["house_purchase_year_options"]:
                    for childcare_mode in plan["childcare_modes"]:
                        for school_mode in plan["school_modes"]:
                            sc_dict = {
                                "pre_move_location": pre_loc,
                                "post_move_location": post_loc,
                                "move_year": move_year,
                                "house_purchase_year": house_purchase_year,
                                "childcare_mode": childcare_mode,
                                "school_mode": school_mode,
                            }
                            scenarios.append(
                                Scenario(
                                    pre_move_location=pre_loc,
                                    post_move_location=post_loc,
                                    move_year=move_year,
                                    house_purchase_year=house_purchase_year,
                                    childcare_mode=childcare_mode,
                                    school_mode=school_mode,
                                    label=make_scenario_label(sc_dict),
                                )
                            )
    return scenarios


def get_location_by_name(locations: List[LocationDefaults], name: str) -> LocationDefaults:
    for loc in locations:
        if loc.name == name:
            return loc
    raise ValueError(f"Unknown location: {name}")


def compute_education_and_care_costs(
    plan: Dict[str, Any],
    sc: Scenario,
    loc: LocationDefaults,
    year_now: int,
) -> (float, float):
    cost_usd = 0.0
    caregiver_salary_factor = 1.0
    ed_scale = (1.0 + plan["education_inflation"]) ** (year_now - plan["current_year"])

    if len(plan["child_birth_years"]) == 0:
        return cost_usd, caregiver_salary_factor

    child_ages = [year_now - birth_year for birth_year in plan["child_birth_years"]]

    for age in child_ages:
        if age < 0:
            continue
        if age < 3:
            if sc.childcare_mode == "daycare":
                cost_usd += loc.preschool_monthly_usd * 12.0 * ed_scale
            else:
                caregiver_salary_factor = min(
                    caregiver_salary_factor,
                    plan["parent_care_salary_fraction"],
                )
        elif age < 6:
            if sc.school_mode == "private":
                cost_usd += loc.preschool_monthly_usd * 12.0 * ed_scale
            elif sc.school_mode == "public":
                cost_usd += plan["public_school_annual_usd"] * ed_scale
            elif sc.school_mode == "homeschool":
                cost_usd += plan["homeschool_annual_usd"] * ed_scale
                caregiver_salary_factor = min(
                    caregiver_salary_factor,
                    plan["homeschool_salary_fraction"],
                )
            else:
                raise ValueError(f"Unknown school mode: {sc.school_mode}")
        elif age < 18:
            if sc.school_mode == "private":
                cost_usd += loc.private_school_annual_usd * ed_scale
            elif sc.school_mode == "public":
                cost_usd += plan["public_school_annual_usd"] * ed_scale
            elif sc.school_mode == "homeschool":
                cost_usd += plan["homeschool_annual_usd"] * ed_scale
                caregiver_salary_factor = min(
                    caregiver_salary_factor,
                    plan["homeschool_salary_fraction"],
                )
            else:
                raise ValueError(f"Unknown school mode: {sc.school_mode}")
        elif plan["include_university"] and age < 18 + plan["university_years"]:
            cost_usd += loc.public_university_annual_usd * ed_scale

    return cost_usd, caregiver_salary_factor


def simulate_scenario(
    plan: Dict[str, Any],
    sc: Scenario,
    locations: List[LocationDefaults],
    salary1: np.ndarray,
    salary2: np.ndarray,
    extra_investment_income: np.ndarray,
) -> Dict[str, Any]:
    n_years = len(plan["years"])
    liquid_usd = np.zeros(n_years, dtype=float)
    net_worth_usd = np.zeros(n_years, dtype=float)
    home_value_usd = np.zeros(n_years, dtype=float)
    annual_income_usd = np.zeros(n_years, dtype=float)
    annual_cost_usd = np.zeros(n_years, dtype=float)
    education_cost_usd = np.zeros(n_years, dtype=float)
    housing_cost_usd = np.zeros(n_years, dtype=float)

    effective_purchase_year = sc.house_purchase_year
    if (
        plan["buy_only_after_final_move"]
        and not is_nan(effective_purchase_year)
        and not is_nan(sc.move_year)
    ):
        effective_purchase_year = max(effective_purchase_year, sc.move_year)

    owned_home = False
    carried_home_value = 0.0

    for k, year_now in enumerate(plan["years"]):
        if k == 0:
            prev_liquid = plan["current_savings_usd"]
        else:
            prev_liquid = liquid_usd[k - 1]

        if prev_liquid >= 0:
            liquid_after_return = prev_liquid * (1.0 + plan["investment_return"])
        else:
            liquid_after_return = prev_liquid * (1.0 + plan["debt_interest_rate"])

        active_location_name = sc.pre_move_location
        if not is_nan(sc.move_year) and year_now >= sc.move_year:
            active_location_name = sc.post_move_location
        loc = get_location_by_name(locations, active_location_name)

        if owned_home:
            carried_home_value = carried_home_value * (1.0 + plan["home_appreciation"])

        if (not owned_home) and (not is_nan(effective_purchase_year)) and (year_now >= effective_purchase_year):
            purchase_base_value = loc.buy_price_per_sqft_usd * plan["home_size_sqft"]
            transaction_cost = purchase_base_value * plan["buying_transaction_cost_rate"]
            liquid_after_return = liquid_after_return - purchase_base_value - transaction_cost
            carried_home_value = purchase_base_value
            owned_home = True

        school_and_care_cost, caregiver_salary_factor = compute_education_and_care_costs(
            plan, sc, loc, int(year_now)
        )

        s1 = salary1[k]
        s2 = salary2[k]
        if plan["caregiver_parent_index"] == 1:
            s1 = s1 * caregiver_salary_factor
        elif plan["caregiver_parent_index"] == 2:
            s2 = s2 * caregiver_salary_factor
        else:
            raise ValueError("caregiver_parent_index must be 1 or 2.")

        annual_income_usd[k] = s1 + s2 + extra_investment_income[k]

        years_from_base = int(year_now - plan["current_year"])
        if owned_home:
            housing_cost_usd[k] = carried_home_value * plan["owner_carrying_cost_rate"]
        else:
            housing_cost_usd[k] = (
                loc.rent_monthly_usd * 12.0 * (1.0 + plan["rent_inflation"]) ** years_from_base
            )

        education_cost_usd[k] = school_and_care_cost
        other_cost = plan["other_annual_spending_usd"] * (1.0 + plan["general_inflation"]) ** years_from_base
        annual_cost_usd[k] = housing_cost_usd[k] + education_cost_usd[k] + other_cost

        liquid_usd[k] = liquid_after_return + annual_income_usd[k] - annual_cost_usd[k]
        home_value_usd[k] = carried_home_value
        net_worth_usd[k] = liquid_usd[k] + home_value_usd[k]

    return {
        "label": sc.label,
        "pre_move_location": sc.pre_move_location,
        "post_move_location": sc.post_move_location,
        "move_year": sc.move_year,
        "house_purchase_year": sc.house_purchase_year,
        "effective_purchase_year": effective_purchase_year,
        "childcare_mode": sc.childcare_mode,
        "school_mode": sc.school_mode,
        "years": plan["years"].copy(),
        "liquid_usd": liquid_usd,
        "net_worth_usd": net_worth_usd,
        "home_value_usd": home_value_usd,
        "annual_income_usd": annual_income_usd,
        "annual_cost_usd": annual_cost_usd,
        "education_cost_usd": education_cost_usd,
        "housing_cost_usd": housing_cost_usd,
        "final_liquid_usd": float(liquid_usd[-1]),
        "final_net_worth_usd": float(net_worth_usd[-1]),
        "min_liquid_usd": float(np.min(liquid_usd)),
        "min_net_worth_usd": float(np.min(net_worth_usd)),
        "ever_negative_liquid": bool(np.any(liquid_usd < 0)),
    }


def scalar_or_nan(v: Any) -> float:
    if v is None:
        return float("nan")
    if isinstance(v, (list, tuple, np.ndarray, pd.Series)):
        if len(v) == 0:
            return float("nan")
        return scalar_or_nan(v[0])
    return float("nan") if is_nan(v) else float(v)


def scalar_or_false(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (list, tuple, np.ndarray, pd.Series)):
        if len(v) == 0:
            return False
        return scalar_or_false(v[0])
    return False if is_nan(v) else bool(v)


def results_to_table(results: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for r in results:
        rows.append(
            {
                "Label": r["label"],
                "PreMoveLocation": r["pre_move_location"],
                "PostMoveLocation": r["post_move_location"],
                "MoveYear": scalar_or_nan(r["move_year"]),
                "HousePurchaseYear": scalar_or_nan(r["house_purchase_year"]),
                "EffectivePurchaseYear": scalar_or_nan(r["effective_purchase_year"]),
                "ChildcareMode": r["childcare_mode"],
                "SchoolMode": r["school_mode"],
                "FinalLiquidUSD": scalar_or_nan(r["final_liquid_usd"]),
                "FinalNetWorthUSD": scalar_or_nan(r["final_net_worth_usd"]),
                "MinLiquidUSD": scalar_or_nan(r["min_liquid_usd"]),
                "MinNetWorthUSD": scalar_or_nan(r["min_net_worth_usd"]),
                "EverNegativeLiquid": scalar_or_false(r["ever_negative_liquid"]),
            }
        )
    return pd.DataFrame(rows)


def _usd_formatter(x: float, _: Any) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:.0f}K"
    return f"${x:.0f}"


def _apply_axis_style(ax: Any, years: np.ndarray, title: str, ylabel: str = "USD") -> None:
    import matplotlib.ticker as mticker
    ax.axhline(0.0, color="black", linestyle="--", linewidth=1.0, alpha=0.4)
    ax.grid(True, which="major", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_xlim(years[0], years[-1])
    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_usd_formatter))
    ax.tick_params(axis="both", labelsize=10)


def plot_scenario_results(results: List[Dict[str, Any]], plan: Dict[str, Any]) -> None:
    valid_results: List[Dict[str, Any]] = []
    for r in results:
        years = r.get("years")
        liquid = r.get("liquid_usd")
        net_worth = r.get("net_worth_usd")
        label = r.get("label")
        if label is None or label == "":
            continue
        if years is None or liquid is None or net_worth is None:
            continue
        if len(years) == 0 or len(liquid) == 0 or len(net_worth) == 0:
            continue
        if len(years) != len(liquid) or len(years) != len(net_worth):
            continue
        valid_results.append(r)

    if not valid_results:
        print("Warning: No valid scenarios available for plotting.")
        return

    n = len(valid_results)
    years = np.asarray(valid_results[0]["years"], dtype=float)

    # --- Figure 1: all scenarios fan ---
    color_map = plt.cm.tab20(np.linspace(0.0, 1.0, max(7, min(n, 20))))
    fig1, axes1 = plt.subplots(2, 1, figsize=(14, 11), constrained_layout=True)
    try:
        fig1.canvas.manager.set_window_title("Scenario Sweep: Liquid vs Net Worth")
    except Exception:
        pass

    for i, r in enumerate(valid_results):
        c = color_map[i % len(color_map)]
        axes1[0].plot(np.asarray(r["years"], dtype=float), np.asarray(r["liquid_usd"], dtype=float),
                      linewidth=0.7, color=c, alpha=0.6)
    _apply_axis_style(axes1[0], years, f"Liquid financial wealth — {n} scenarios")

    for i, r in enumerate(valid_results):
        c = color_map[i % len(color_map)]
        axes1[1].plot(np.asarray(r["years"], dtype=float), np.asarray(r["net_worth_usd"], dtype=float),
                      linewidth=0.7, color=c, alpha=0.6)
    _apply_axis_style(axes1[1], years, "Net worth (liquid + home value)")

    if n <= 20:
        labels = [r["label"] for r in valid_results]
        axes1[1].legend(labels, loc="upper left", fontsize=8, framealpha=0.85,
                        ncol=1, borderpad=0.8)

    # --- Figure 2: top-N detail ---
    order = np.argsort([r["final_net_worth_usd"] for r in valid_results])[::-1]
    top_n = min(15, n)

    distinct_colors = [
        "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
        "#dcbeff", "#9a6324", "#fffac8", "#800000", "#aaffc3",
    ]
    line_styles = ["-", "--", "-.", ":"]

    fig2, axes2 = plt.subplots(2, 1, figsize=(16, 13), constrained_layout=True)
    try:
        fig2.canvas.manager.set_window_title("Top Scenario Paths by Final Net Worth")
    except Exception:
        pass

    legend_text: List[str] = []
    for j in range(top_n):
        idx = int(order[j])
        col = distinct_colors[j % len(distinct_colors)]
        ls = line_styles[j // len(distinct_colors) % len(line_styles)]
        lw = 2.2 if j < 5 else 1.6
        final_val = valid_results[idx]["final_net_worth_usd"]
        short_label = f"#{j+1} — {valid_results[idx]['label']}  (${final_val/1e6:.2f}M)"
        legend_text.append(short_label)

        axes2[0].plot(
            np.asarray(valid_results[idx]["years"], dtype=float),
            np.asarray(valid_results[idx]["liquid_usd"], dtype=float),
            linewidth=lw, color=col, linestyle=ls,
        )
        axes2[1].plot(
            np.asarray(valid_results[idx]["years"], dtype=float),
            np.asarray(valid_results[idx]["net_worth_usd"], dtype=float),
            linewidth=lw, color=col, linestyle=ls,
            label=short_label,
        )

    _apply_axis_style(axes2[0], years, f"Top {top_n} scenarios — liquid wealth")
    _apply_axis_style(axes2[1], years, f"Top {top_n} scenarios — net worth")

    axes2[1].legend(
        loc="upper left",
        fontsize=8.5,
        framealpha=0.9,
        borderpad=0.9,
        labelspacing=0.6,
        ncol=1,
    )

    plt.show()


def print_assumption_notes(locations: List[LocationDefaults]) -> None:
    print("\nLocation default notes:")
    for loc in locations:
        print(f"  - {loc.name}: {loc.notes}")
    print(
        "\nInterpretation notes:\n"
        "  - Private preschool / kindergarten cost is used for both daycare (age 0-2) and private kindergarten (age 3-5).\n"
        "  - International primary school tuition is used as a proxy for private K-12 annual tuition.\n"
        "  - Public school is set to $0 by default. Edit plan['public_school_annual_usd'] if you want fees, supplies, or transport embedded.\n"
        "  - Homeschooling adds a direct annual cost and reduces one salary during active homeschooling years.\n"
        "  - Full-cash home purchase reduces liquid wealth, but home value is added back into net worth.\n"
        "  - If plan['buy_only_after_final_move'] is True, a purchase before a move is deferred until the move year."
    )


def get_location_defaults_usd() -> List[LocationDefaults]:
    return [
        LocationDefaults(
            name="Bay Area",
            rent_monthly_usd=4629.33,
            preschool_monthly_usd=3018.16,
            private_school_annual_usd=42000.00,
            buy_price_per_sqft_usd=885.10,
            public_university_annual_usd=12000.00,
            notes="San Francisco proxy for Bay Area; uses 3BR outside-centre rent and outside-centre purchase price.",
        ),
        LocationDefaults(
            name="Midwest (Kansas City)",
            rent_monthly_usd=1668.00,
            preschool_monthly_usd=1128.67,
            private_school_annual_usd=21064.17,
            buy_price_per_sqft_usd=178.68,
            public_university_annual_usd=12000.00,
            notes="Kansas City, MO proxy.",
        ),
        LocationDefaults(
            name="Miami area",
            rent_monthly_usd=3739.48,
            preschool_monthly_usd=1869.94,
            private_school_annual_usd=38614.00,
            buy_price_per_sqft_usd=354.53,
            public_university_annual_usd=6360.00,
            notes="Miami city proxy. Public university default is seeded lower because Florida public tuition is low relative to the U.S. average.",
        ),
        LocationDefaults(
            name="New Orleans area",
            rent_monthly_usd=2069.00,
            preschool_monthly_usd=1563.89,
            private_school_annual_usd=10230.00,
            buy_price_per_sqft_usd=128.11,
            public_university_annual_usd=12000.00,
            notes="New Orleans city proxy.",
        ),
        LocationDefaults(
            name="Southern France",
            rent_monthly_usd=1290.72,
            preschool_monthly_usd=813.73,
            private_school_annual_usd=10402.15,
            buy_price_per_sqft_usd=335.04,
            public_university_annual_usd=205.00,
            notes="Marseille proxy for Southern France.",
        ),
        LocationDefaults(
            name="Spain",
            rent_monthly_usd=1244.39,
            preschool_monthly_usd=562.99,
            private_school_annual_usd=10824.33,
            buy_price_per_sqft_usd=249.36,
            public_university_annual_usd=3000.00,
            notes="Country-wide Spain averages from Numbeo; university default is a rough editable seed.",
        ),
        LocationDefaults(
            name="China, Jingzhou",
            rent_monthly_usd=362.78,
            preschool_monthly_usd=333.82,
            private_school_annual_usd=16471.37,
            buy_price_per_sqft_usd=154.16,
            public_university_annual_usd=1000.00,
            notes="Jingzhou childcare/private-school values use Jingzhou page; housing uses nearby Wuhan proxy because direct Jingzhou rent/purchase entries were missing.",
        ),
        LocationDefaults(
            name="Japan",
            rent_monthly_usd=732.92,
            preschool_monthly_usd=530.83,
            private_school_annual_usd=12055.91,
            buy_price_per_sqft_usd=273.92,
            public_university_annual_usd=3379.00,
            notes="Country-wide Japan averages from Numbeo; public university seed follows the standard national university tuition level.",
        ),
        LocationDefaults(
            name="Vietnam",
            rent_monthly_usd=547.11,
            preschool_monthly_usd=325.29,
            private_school_annual_usd=16504.80,
            buy_price_per_sqft_usd=169.49,
            public_university_annual_usd=1000.00,
            notes="Country-wide Vietnam averages from Numbeo; university default is a rough editable seed.",
        ),
    ]


def main() -> None:
    plan: Dict[str, Any] = {}
    plan["current_year"] = pd.Timestamp.today().year
    plan["end_year"] = plan["current_year"] + 30
    plan["years"] = np.arange(plan["current_year"], plan["end_year"] + 1, dtype=int)

    plan["current_savings_usd"] = 300000
    plan["investment_return"] = 0.05
    plan["debt_interest_rate"] = 0.08
    plan["extra_investment_income_start_usd"] = 0
    plan["extra_investment_income_growth"] = 0.00

    plan["salary1_start_usd"] = 180000
    plan["salary2_start_usd"] = 120000
    plan["salary1_growth"] = 0.03
    plan["salary2_growth"] = 0.03
    plan["salary1_by_year_usd"] = []
    plan["salary2_by_year_usd"] = []

    plan["other_annual_spending_usd"] = 45000
    plan["general_inflation"] = 0.025
    plan["education_inflation"] = 0.040
    plan["rent_inflation"] = 0.030
    plan["home_appreciation"] = 0.030

    plan["home_size_sqft"] = 1500
    plan["owner_carrying_cost_rate"] = 0.018
    plan["buying_transaction_cost_rate"] = 0.03
    plan["buy_only_after_final_move"] = True

    plan["child_birth_years"] = [2030, 2032]
    plan["include_university"] = True
    plan["university_years"] = 4

    plan["childcare_modes"] = ["daycare", "parent"]
    plan["school_modes"] = ["public", "private", "homeschool"]
    plan["public_school_annual_usd"] = 0
    plan["homeschool_annual_usd"] = 1500

    plan["caregiver_parent_index"] = 2
    plan["parent_care_salary_fraction"] = 0.20
    plan["homeschool_salary_fraction"] = 0.25

    location_names = [
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

    plan["pre_move_location_options"] = location_names
    plan["post_move_location_options"] = location_names
    plan["move_year_options"] = [float("nan"), plan["current_year"] + 5]
    plan["house_purchase_year_options"] = [float("nan"), plan["current_year"] + 8]

    locations = get_location_defaults_usd()
    salary1 = build_annual_series(
        plan["salary1_start_usd"],
        plan["salary1_growth"],
        plan["years"],
        plan["salary1_by_year_usd"],
    )
    salary2 = build_annual_series(
        plan["salary2_start_usd"],
        plan["salary2_growth"],
        plan["years"],
        plan["salary2_by_year_usd"],
    )
    extra_investment_income = build_annual_series(
        plan["extra_investment_income_start_usd"],
        plan["extra_investment_income_growth"],
        plan["years"],
        [],
    )
    scenarios = build_scenarios(plan)

    if not scenarios:
        raise ValueError("No scenarios were generated. Check the location / move / purchase option lists.")

    print(f"Simulating {len(scenarios)} scenarios over {len(plan['years'])} years...")
    if len(scenarios) > 300:
        print("Large scenario grid detected. Plots will be crowded; reduce option lists if needed.")

    first_result = simulate_scenario(plan, scenarios[0], locations, salary1, salary2, extra_investment_income)
    results: List[Dict[str, Any]] = [first_result]
    for i in range(1, len(scenarios)):
        results.append(
            simulate_scenario(plan, scenarios[i], locations, salary1, salary2, extra_investment_income)
        )

    summary_table = results_to_table(results)
    summary_table = summary_table.sort_values("FinalNetWorthUSD", ascending=False, kind="mergesort")

    print(summary_table.head(min(30, len(summary_table))).to_string(index=False))
    summary_table.to_csv("family_finance_scenario_summary.csv", index=False)
    plot_scenario_results(results, plan)
    print_assumption_notes(locations)

    print("\nWrote scenario summary to: family_finance_scenario_summary.csv")


if __name__ == "__main__":
    main()
