"""
merge_data.py -- builds the U.S. Affordability dataset (1990-2025).

Merges federal sources into one row per year:
  * FRED: median/average home sale price (MSPUS, ASPUS), regular gas
    price (GASREGW), personal saving rate (PSAVERT), CPI-U (CPIAUCNS)
  * Census Table H-5: median and mean household income
  * Census Table F-7: married-couple family median income
  * Census ACS B25119 / B25071: income by tenure (owner/renter) and renter
    rent burden, 2010-2024
  * Census HVS Table 11A: median asking rent
  * Freddie Mac PMMS: 30-year fixed mortgage rate
  * BLS Consumer Expenditure Survey, NCES / College Board, Child Care
    Aware of America, DOL: household spending, tuition, childcare,
    federal minimum wage (entered from published tables -- see
    SOURCES.md for every figure's source)
  * Tax Foundation / IRS: historical federal brackets and standard
    deductions, used to estimate after-federal-tax ("net") income

HOW TO USE
----------
1. Put the raw files (data/raw in this repo) in the working directory.
2. Run:  python3 merge_data.py   ->  writes affordability_merged.csv
3. Run:  python3 fix_dollar_basis.py  (see note below)

NOTE ON DOLLAR BASIS
--------------------
This script loads Census incomes in constant 2025 dollars while cost
columns are each year's nominal dollars. fix_dollar_basis.py converts the
income columns to nominal dollars so every %-of-income ratio compares
like with like. The published dataset is this script's output plus the
household-type and renter-income adjustments noted in comments below,
followed by fix_dollar_basis.py.

All dollar columns are plain numbers (no $, %, or k); percent columns
are stored as e.g. 20.5 (not 0.205).
"""
import pandas as pd
import os

YEARS = list(range(1990, 2026))  # 1990-2025; 2026 dropped (too incomplete), 1989 dropped (, 2026-09-17 -- cleaner start point) -- see note below
df = pd.DataFrame({"Year": YEARS})

def load_fred_annual(filename, colname, agg="mean"):
    """FRED CSVs are two columns: observation_date/DATE, VALUE. Resamples to annual."""
    global df
    if not os.path.exists(filename):
        print(f"  [skip] {filename} not found -- download it first.")
        df[colname] = pd.NA
        return
    raw = pd.read_csv(filename)
    raw.columns = [c.strip() for c in raw.columns]
    date_col = "observation_date" if "observation_date" in raw.columns else raw.columns[0]
    value_col = raw.columns[1]
    raw[date_col] = pd.to_datetime(raw[date_col], errors="coerce")
    raw["Year"] = raw[date_col].dt.year
    raw[value_col] = pd.to_numeric(raw[value_col], errors="coerce")
    annual = raw.groupby("Year")[value_col].agg(agg).reset_index()
    annual.columns = ["Year", colname]
    df = df.merge(annual, on="Year", how="left")
    print(f"  [ok] merged {filename} -> {colname}")

print("Merging FRED series...")
load_fred_annual("MSPUS.csv", "Median_Home_Price", agg="mean")
load_fred_annual("ASPUS.csv", "Avg_Home_Price", agg="mean")
load_fred_annual("GASREGW.csv", "Gas_Price_Gal", agg="mean")
load_fred_annual("PSAVERT.csv", "Savings_Rate_Pct", agg="mean")

# BLS Consumer Price Index for All Urban Consumers: All Items in U.S.
# City Average (CPI-U), NOT seasonally adjusted -- the standard general
# inflation index (base period 1982-84 = 100). Annual value = mean of
# the 12 monthly index values, matching BLS's own published "annual
# average" convention. Added so Tableau can toggle nominal vs.
# inflation-adjusted ("real") views of any dollar column -- e.g.
# Real_Value = Nominal_Value * (CPI_Index[2025] / CPI_Index[that year]).
# FRED series CPIAUCNS: https://fred.stlouisfed.org/series/CPIAUCNS
load_fred_annual("CPIAUCNS.csv", "CPI_Index", agg="mean")


# Census Bureau Table H-5 ("Median and Mean Household Income by Race and
# Hispanic Origin of Householder"), "All Races" rows -- loaded directly
# from h05.xlsx, added to this folder (download link:
# https://www2.census.gov/programs-surveys/cps/tables/time-series/historical-income-households/h05.xlsx).
# Used for BOTH Median_Income and Mean_Income so the two are on an
# identical, consistent real-dollar basis (2025 C-CPI-U/R-CPI-U-RS
# dollars) for every year -- this REPLACED the prior median-income
# approach (FRED's MEHOINUSA672N, in 2024 dollars, plus a manually-
# entered 2025 dollars figure for 2025 alone), which had mixed two
# different real-dollar bases across the series. See SOURCES.md.
def load_census_income_annual(filename="h05.xlsx"):
    if not os.path.exists(filename):
        print(f"  [skip] {filename} not found -- download Table H-5 from "
              "census.gov (see comment above for the URL).")
        return {}, {}
    import re
    raw = pd.read_excel(filename, sheet_name="h05", header=None)
    median, mean = {}, {}
    started = False
    for _, r in raw.iterrows():
        yr_raw = r[0]
        m = None if pd.isna(yr_raw) else re.match(r"^(\d{4})", str(yr_raw))
        if not m:
            # A non-matching row after data has started means we've hit the
            # next race/ethnicity section header (e.g. "White Alone (31)") --
            # this file repeats the same year list once per subgroup, so we
            # stop here to keep only the "All Races" rows (the first block).
            if started:
                break
            continue
        started = True
        yr = int(m.group(1))
        if yr < 1989 or yr > 2025:
            continue
        try:
            median[yr] = float(r[3])  # "Median income, 2025 dollars"
            mean[yr] = float(r[5])    # "Mean income, 2025 dollars"
        except (ValueError, TypeError):
            continue
    print(f"  [ok] merged {filename} -> Median_Income, Mean_Income (All Races section only)")
    return median, mean

median_income_annual, mean_income_annual = load_census_income_annual()
df["Median_Income"] = df["Year"].map(median_income_annual)
df["Mean_Income"] = df["Year"].map(mean_income_annual)

# Married-couple household income (2026-10-26) --
# Net_Income_MFJ previously reused the general Median_Income (all U.S.
# households) with only the tax *filing status* switched to Married
# Filing Jointly -- it did not reflect that married-couple households
# actually earn more (more likely to be dual-earner). Net_Income_MFJ
# should reflect married-couple household income
# specifically, after comparing Census's own 2024 figures: all households
# $83,730 vs. married-couple households $128,700 (Table F-7).
# Source: Census Bureau Table F-7, "Median and Mean Family Income of All
# Families by Type of Family: 1947 to 2025" (CPS ASEC), Married-Couple
# Families section, "2025 dollars" (real/inflation-adjusted) column --
# same real-dollar basis as Median_Income/Mean_Income from Table H-5, so
# the existing CPI-based nominal-bracket conversion below still applies
# unchanged, no further changes needed there.
# CAVEAT: this does NOT isolate dual-earner couples specifically -- it is
# the median across all married-couple households regardless of how many
# spouses currently work (includes single-earner and retired/no-earner
# couples too). Considered Census's dual-earner-specific cross-tab
# (Table FINC-04) but chose Table F-7 for now as a cleaner, continuously-
# published series; Net_Income_MFJ (and everything derived from it, e.g.
# Home_Price_Pct_Net_Income_MFJ, Rent_Pct_Net_Income_MFJ, Married Homeowner
# Remaining % in Tableau) likely still runs a bit conservative for an
# actual dual-earner household. See SOURCES.md and the dashboard
# footnote for this caveat.
def load_married_couple_income_annual(filename="f07ar.xlsx"):
    if not os.path.exists(filename):
        print(f"  [skip] {filename} not found -- download Table F-7 from "
              "census.gov (see comment above for the URL).")
        return {}
    import re
    raw = pd.read_excel(filename, sheet_name="f07ar", header=None)
    income = {}
    in_section = False
    for _, r in raw.iterrows():
        label = r[0]
        if isinstance(label, str) and "Married-Couple Families" in label:
            in_section = True
            continue
        if isinstance(label, str) and "Householder" in label and in_section:
            # Hit the next family-type section (Male/Female Householder) --
            # stop, so we only read the Married-Couple Families block.
            break
        if not in_section:
            continue
        m = None if pd.isna(label) else re.match(r"^(\d{4})", str(label))
        if not m:
            continue
        yr = int(m.group(1))
        if yr < 1990 or yr > 2025:
            continue
        if yr in income:
            # This table lists some years twice (a CPS methodology-break
            # footnote pair, e.g. "2013 (39)" then "2013 (38)") -- keep the
            # first (top-most) occurrence, consistent with the newer
            # methodology used by the years immediately above it.
            continue
        try:
            income[yr] = float(r[3])  # "Median income, 2025 dollars"
        except (ValueError, TypeError):
            continue
    print(f"  [ok] merged {filename} -> Married_Couple_Median_Income (Married-Couple Families section only)")
    return income

married_couple_income_annual = load_married_couple_income_annual()
df["Married_Couple_Median_Income"] = df["Year"].map(married_couple_income_annual)

# Federal income tax bracket calculation applied SPECIFICALLY to
# Median_Income each year (2026-09-17 -- replaces
# an earlier national-aggregate-rate approach with a true bracket-based
# estimate tied to the median household's own income). Two filing-status
# variants are provided side by side by design:
# Married Filing Jointly (MFJ) and Single. See SOURCES.md for full
# sourcing (Tax Foundation historical brackets, cross-checked against
# IRS.gov for multiple years) and for the important caveats:
#   - FEDERAL INCOME TAX ONLY. Does not include state/local income tax
#     (varies by state, several have none -- no single "national" state
#     rate exists) or payroll/FICA tax.
#   - Taxable income = Median_Income - that year's standard deduction
#     ONLY. No personal exemptions (1990-2017), itemizing, or credits
#     (child tax credit, EITC, etc.) are modeled -- so pre-2018 effective
#     rates here run a bit HIGH relative to what a filer claiming the
#     era's personal exemptions would have actually paid, and Net_Income
#     understates take-home pay for anyone eligible for credits.
#   - 1990 uses the real, non-monotonic "TRA86 bubble" bracket structure
#     (rates go 15%->28%->33%->back to 28%) -- historically accurate, not
#     a data error.
def _federal_tax(taxable_income, brackets):
    """brackets: list of (rate, bracket_start) tuples sorted ascending by
    bracket_start. Walks brackets in order regardless of whether rates
    are monotonically increasing (needed for 1990's bubble bracket)."""
    if taxable_income is None or pd.isna(taxable_income) or taxable_income <= 0:
        return 0.0
    tax = 0.0
    for i, (rate, start) in enumerate(brackets):
        if taxable_income <= start:
            break
        next_start = brackets[i + 1][1] if i + 1 < len(brackets) else float("inf")
        tax += (min(taxable_income, next_start) - start) * rate
    return tax

# year -> list of (rate_as_decimal, bracket_start_dollars) tuples, ascending.
# Source: Tax Foundation, "Historical Federal Income Tax Rates & Brackets,
# 1862-2025" (https://taxfoundation.org/data/all/federal/historical-income-tax-rates-brackets/),
# 1990 cross-checked against IRS SOI "Individual Income Tax Rates and Tax
# Shares, 1990"; 2020 independently re-verified against irs.gov's own
# "IRS provides tax inflation adjustments for tax year 2020" release.
MFJ_BRACKETS = {
    1990: [(0.15, 0), (0.28, 32450), (0.33, 67200), (0.28, 134930)],
    1991: [(0.15, 0), (0.28, 34000), (0.31, 82150)],
    1992: [(0.15, 0), (0.28, 35800), (0.31, 86500)],
    1993: [(0.15, 0), (0.28, 36900), (0.31, 89150), (0.36, 140000), (0.396, 250000)],
    1994: [(0.15, 0), (0.28, 38000), (0.31, 91850), (0.36, 140000), (0.396, 250000)],
    1995: [(0.15, 0), (0.28, 39000), (0.31, 94250), (0.36, 143600), (0.396, 256500)],
    1996: [(0.15, 0), (0.28, 40100), (0.31, 96900), (0.36, 147700), (0.396, 263750)],
    1997: [(0.15, 0), (0.28, 41200), (0.31, 99600), (0.36, 151750), (0.396, 271050)],
    1998: [(0.15, 0), (0.28, 42350), (0.31, 102300), (0.36, 155950), (0.396, 278450)],
    1999: [(0.15, 0), (0.28, 43050), (0.31, 104050), (0.36, 158550), (0.396, 283150)],
    2000: [(0.15, 0), (0.28, 43850), (0.31, 105950), (0.36, 161450), (0.396, 288350)],
    2001: [(0.15, 0), (0.275, 45200), (0.305, 109250), (0.355, 166500), (0.391, 297350)],
    2002: [(0.10, 0), (0.15, 12000), (0.27, 46700), (0.30, 112850), (0.35, 171950), (0.386, 307050)],
    2003: [(0.10, 0), (0.15, 14000), (0.25, 56800), (0.28, 114650), (0.33, 174700), (0.35, 311950)],
    2004: [(0.10, 0), (0.15, 14300), (0.25, 58100), (0.28, 117250), (0.33, 178650), (0.35, 319100)],
    2005: [(0.10, 0), (0.15, 14600), (0.25, 59400), (0.28, 119950), (0.33, 182800), (0.35, 326450)],
    2006: [(0.10, 0), (0.15, 15100), (0.25, 61300), (0.28, 123700), (0.33, 188450), (0.35, 336550)],
    2007: [(0.10, 0), (0.15, 15650), (0.25, 63700), (0.28, 128500), (0.33, 195850), (0.35, 349700)],
    2008: [(0.10, 0), (0.15, 16050), (0.25, 65100), (0.28, 131450), (0.33, 200300), (0.35, 357700)],
    2009: [(0.10, 0), (0.15, 16700), (0.25, 67900), (0.28, 137050), (0.33, 208850), (0.35, 372950)],
    2010: [(0.10, 0), (0.15, 16750), (0.25, 68000), (0.28, 137300), (0.33, 209250), (0.35, 373650)],
    2011: [(0.10, 0), (0.15, 17000), (0.25, 69000), (0.28, 139350), (0.33, 212300), (0.35, 379150)],
    2012: [(0.10, 0), (0.15, 17400), (0.25, 70700), (0.28, 142700), (0.33, 217450), (0.35, 388350)],
    2013: [(0.10, 0), (0.15, 17850), (0.25, 72500), (0.28, 146400), (0.33, 223050), (0.35, 398350), (0.396, 450000)],
    2014: [(0.10, 0), (0.15, 18150), (0.25, 73800), (0.28, 148850), (0.33, 226850), (0.35, 405100), (0.396, 457600)],
    2015: [(0.10, 0), (0.15, 18450), (0.25, 74900), (0.28, 151200), (0.33, 230450), (0.35, 411500), (0.396, 464850)],
    2016: [(0.10, 0), (0.15, 18550), (0.25, 75300), (0.28, 151900), (0.33, 231450), (0.35, 413350), (0.396, 466950)],
    2017: [(0.10, 0), (0.15, 18650), (0.25, 75900), (0.28, 153100), (0.33, 233350), (0.35, 416700), (0.396, 470700)],
    2018: [(0.10, 0), (0.12, 19050), (0.22, 77400), (0.24, 165000), (0.32, 315000), (0.35, 400000), (0.37, 600000)],
    2019: [(0.10, 0), (0.12, 19400), (0.22, 78950), (0.24, 168400), (0.32, 321450), (0.35, 408200), (0.37, 612350)],
    2020: [(0.10, 0), (0.12, 19750), (0.22, 80250), (0.24, 171050), (0.32, 326600), (0.35, 414700), (0.37, 622050)],
    2021: [(0.10, 0), (0.12, 19900), (0.22, 81050), (0.24, 172750), (0.32, 329850), (0.35, 418850), (0.37, 628300)],
    2022: [(0.10, 0), (0.12, 20550), (0.22, 83550), (0.24, 178150), (0.32, 340100), (0.35, 431900), (0.37, 647850)],
    2023: [(0.10, 0), (0.12, 22000), (0.22, 89450), (0.24, 190750), (0.32, 364200), (0.35, 462500), (0.37, 693750)],
    2024: [(0.10, 0), (0.12, 23200), (0.22, 94300), (0.24, 201050), (0.32, 383900), (0.35, 487450), (0.37, 731200)],
    2025: [(0.10, 0), (0.12, 23850), (0.22, 96950), (0.24, 206700), (0.32, 394600), (0.35, 501050), (0.37, 751600)],
}

SINGLE_BRACKETS = {
    1990: [(0.15, 0), (0.28, 19450), (0.33, 39200), (0.28, 123570)],
    1991: [(0.15, 0), (0.28, 20350), (0.31, 49300)],
    1992: [(0.15, 0), (0.28, 21450), (0.31, 51900)],
    1993: [(0.15, 0), (0.28, 22100), (0.31, 53500), (0.36, 115000), (0.396, 250000)],
    1994: [(0.15, 0), (0.28, 22750), (0.31, 55100), (0.36, 115000), (0.396, 250000)],
    1995: [(0.15, 0), (0.28, 23350), (0.31, 56550), (0.36, 117950), (0.396, 256500)],
    1996: [(0.15, 0), (0.28, 24000), (0.31, 58150), (0.36, 121300), (0.396, 263750)],
    1997: [(0.15, 0), (0.28, 24650), (0.31, 59750), (0.36, 124650), (0.396, 271050)],
    1998: [(0.15, 0), (0.28, 25350), (0.31, 61400), (0.36, 128100), (0.396, 278450)],
    1999: [(0.15, 0), (0.28, 25750), (0.31, 62450), (0.36, 130250), (0.396, 283150)],
    2000: [(0.15, 0), (0.28, 26250), (0.31, 63550), (0.36, 132600), (0.396, 288350)],
    2001: [(0.15, 0), (0.275, 27050), (0.305, 65550), (0.355, 136750), (0.391, 297350)],
    2002: [(0.10, 0), (0.15, 6000), (0.27, 27950), (0.30, 67700), (0.35, 141250), (0.386, 307050)],
    2003: [(0.10, 0), (0.15, 7000), (0.25, 28400), (0.28, 68800), (0.33, 143500), (0.35, 311950)],
    2004: [(0.10, 0), (0.15, 7150), (0.25, 29050), (0.28, 70350), (0.33, 146750), (0.35, 319100)],
    2005: [(0.10, 0), (0.15, 7300), (0.25, 29700), (0.28, 71950), (0.33, 150150), (0.35, 326450)],
    2006: [(0.10, 0), (0.15, 7550), (0.25, 30650), (0.28, 74200), (0.33, 154800), (0.35, 336550)],
    2007: [(0.10, 0), (0.15, 7825), (0.25, 31850), (0.28, 77100), (0.33, 160850), (0.35, 349700)],
    2008: [(0.10, 0), (0.15, 8025), (0.25, 32550), (0.28, 78850), (0.33, 164550), (0.35, 357700)],
    2009: [(0.10, 0), (0.15, 8350), (0.25, 33950), (0.28, 82250), (0.33, 171550), (0.35, 372950)],
    2010: [(0.10, 0), (0.15, 8375), (0.25, 34000), (0.28, 82400), (0.33, 171850), (0.35, 373650)],
    2011: [(0.10, 0), (0.15, 8500), (0.25, 34500), (0.28, 83600), (0.33, 174400), (0.35, 379150)],
    2012: [(0.10, 0), (0.15, 8700), (0.25, 35350), (0.28, 85650), (0.33, 178650), (0.35, 388350)],
    2013: [(0.10, 0), (0.15, 8925), (0.25, 36250), (0.28, 87850), (0.33, 183250), (0.35, 398350), (0.396, 400000)],
    2014: [(0.10, 0), (0.15, 9075), (0.25, 36900), (0.28, 89350), (0.33, 186350), (0.35, 405100), (0.396, 406750)],
    2015: [(0.10, 0), (0.15, 9225), (0.25, 37450), (0.28, 90750), (0.33, 189300), (0.35, 411500), (0.396, 413200)],
    2016: [(0.10, 0), (0.15, 9275), (0.25, 37650), (0.28, 91150), (0.33, 190150), (0.35, 413350), (0.396, 415050)],
    2017: [(0.10, 0), (0.15, 9325), (0.25, 37950), (0.28, 91900), (0.33, 191650), (0.35, 416700), (0.396, 418400)],
    2018: [(0.10, 0), (0.12, 9525), (0.22, 38700), (0.24, 82500), (0.32, 157500), (0.35, 200000), (0.37, 500000)],
    2019: [(0.10, 0), (0.12, 9700), (0.22, 39475), (0.24, 84200), (0.32, 160725), (0.35, 204100), (0.37, 510300)],
    2020: [(0.10, 0), (0.12, 9875), (0.22, 40125), (0.24, 85525), (0.32, 163300), (0.35, 207350), (0.37, 518400)],
    2021: [(0.10, 0), (0.12, 9950), (0.22, 40525), (0.24, 86375), (0.32, 164925), (0.35, 209425), (0.37, 523600)],
    2022: [(0.10, 0), (0.12, 10275), (0.22, 41775), (0.24, 89075), (0.32, 170050), (0.35, 215950), (0.37, 539900)],
    2023: [(0.10, 0), (0.12, 11000), (0.22, 44725), (0.24, 95375), (0.32, 182000), (0.35, 231250), (0.37, 578125)],
    2024: [(0.10, 0), (0.12, 11600), (0.22, 47150), (0.24, 100525), (0.32, 191950), (0.35, 243725), (0.37, 609350)],
    2025: [(0.10, 0), (0.12, 11925), (0.22, 48475), (0.24, 103350), (0.32, 197300), (0.35, 250525), (0.37, 626350)],
}

MFJ_STANDARD_DEDUCTION = {
    1990: 5450, 1991: 5700, 1992: 6000, 1993: 6200, 1994: 6350, 1995: 6550,
    1996: 6700, 1997: 6900, 1998: 7100, 1999: 7200, 2000: 7350, 2001: 7600,
    2002: 7850, 2003: 9500, 2004: 9700, 2005: 10000, 2006: 10300, 2007: 10700,
    2008: 10900, 2009: 11400, 2010: 11400, 2011: 11600, 2012: 11900, 2013: 12200,
    2014: 12400, 2015: 12600, 2016: 12600, 2017: 12700, 2018: 24000, 2019: 24400,
    2020: 24800, 2021: 25100, 2022: 25900, 2023: 27700, 2024: 29200, 2025: 31500,
}

SINGLE_STANDARD_DEDUCTION = {
    1990: 3250, 1991: 3400, 1992: 3600, 1993: 3700, 1994: 3800, 1995: 3900,
    1996: 4000, 1997: 4150, 1998: 4250, 1999: 4300, 2000: 4400, 2001: 4550,
    2002: 4700, 2003: 4750, 2004: 4850, 2005: 5000, 2006: 5150, 2007: 5350,
    2008: 5450, 2009: 5700, 2010: 5700, 2011: 5800, 2012: 5950, 2013: 6100,
    2014: 6200, 2015: 6300, 2016: 6300, 2017: 6350, 2018: 12000, 2019: 12200,
    2020: 12400, 2021: 12550, 2022: 12950, 2023: 13850, 2024: 14600, 2025: 15750,
}

# IMPORTANT: Median_Income is sourced from Census Table H-5's "2025
# dollars" (inflation-adjusted / REAL) column, not that year's actual
# nominal dollar figure -- but IRS tax brackets and standard deductions
# are inherently NOMINAL (each year's own current-dollar thresholds).
# Applying nominal brackets directly to a real, 2025-dollar income figure
# would push older years into brackets they never actually reached (e.g.
# 1990's real $67,050-equivalent income is NOT what a household actually
# had in hand in 1990 -- nominal 1990 income was much lower, and that's
# what 1990's brackets are denominated in). So each row is converted to
# that year's NOMINAL dollars using CPI_Index before the bracket lookup,
# then the resulting rate is applied back to the REAL Median_Income to
# get Net_Income -- keeping Net_Income on the same real/2025-dollar basis
# as Median_Income (consistent with the rest of the dataset), while still
# taxing the household at the bracket it would have actually been in.
cpi_2025 = df.loc[df["Year"] == 2025, "CPI_Index"]
cpi_2025 = float(cpi_2025.iloc[0]) if len(cpi_2025) and pd.notna(cpi_2025.iloc[0]) else None

def _bracket_tax_rate_for_row(year, real_income, brackets_by_year, std_ded_by_year, cpi_by_year, cpi_ref):
    if pd.isna(real_income) or year not in brackets_by_year or cpi_ref is None:
        return pd.NA
    cpi_year = cpi_by_year.get(year)
    if cpi_year is None or pd.isna(cpi_year):
        return pd.NA
    nominal_income = real_income * (cpi_year / cpi_ref)
    nominal_taxable = max(0.0, nominal_income - std_ded_by_year[year])
    nominal_tax = _federal_tax(nominal_taxable, brackets_by_year[year])
    if nominal_income <= 0:
        return pd.NA
    return nominal_tax / nominal_income  # scale-invariant -- same ratio in real or nominal terms

cpi_by_year = dict(zip(df["Year"], df["CPI_Index"]))

df["_Rate_MFJ"] = df.apply(
    lambda r: _bracket_tax_rate_for_row(r["Year"], r["Married_Couple_Median_Income"], MFJ_BRACKETS, MFJ_STANDARD_DEDUCTION, cpi_by_year, cpi_2025), axis=1)
df["_Rate_Single"] = df.apply(
    lambda r: _bracket_tax_rate_for_row(r["Year"], r["Median_Income"], SINGLE_BRACKETS, SINGLE_STANDARD_DEDUCTION, cpi_by_year, cpi_2025), axis=1)
df["_Rate_MFJ"] = pd.to_numeric(df["_Rate_MFJ"], errors="coerce")
df["_Rate_Single"] = pd.to_numeric(df["_Rate_Single"], errors="coerce")

df["Effective_Tax_Rate_MFJ_Pct"] = (df["_Rate_MFJ"] * 100).round(2)
df["Net_Income_MFJ"] = (df["Married_Couple_Median_Income"] * (1 - df["_Rate_MFJ"])).round(0)
df["Effective_Tax_Rate_Single_Pct"] = (df["_Rate_Single"] * 100).round(2)
df["Net_Income_Single"] = (df["Median_Income"] * (1 - df["_Rate_Single"])).round(0)
df.drop(columns=["_Rate_MFJ", "_Rate_Single"], inplace=True)

# Same bracket method, applied to Mean_Income instead of Median_Income, so
# the Mean_Income-based %-of-income ratios (grocery, insurance, utilities,
# gas, childcare, property tax) can also have net-income variants
# (2026-09-17). Not exposed as its own visible
# "effective rate" column pair -- the Median_Income-based rate columns
# above already tell that story; these are intermediate only.
df["_RateMean_MFJ"] = df.apply(
    lambda r: _bracket_tax_rate_for_row(r["Year"], r["Mean_Income"], MFJ_BRACKETS, MFJ_STANDARD_DEDUCTION, cpi_by_year, cpi_2025), axis=1)
df["_RateMean_Single"] = df.apply(
    lambda r: _bracket_tax_rate_for_row(r["Year"], r["Mean_Income"], SINGLE_BRACKETS, SINGLE_STANDARD_DEDUCTION, cpi_by_year, cpi_2025), axis=1)
df["_RateMean_MFJ"] = pd.to_numeric(df["_RateMean_MFJ"], errors="coerce")
df["_RateMean_Single"] = pd.to_numeric(df["_RateMean_Single"], errors="coerce")
df["Net_Mean_Income_MFJ"] = (df["Mean_Income"] * (1 - df["_RateMean_MFJ"])).round(0)
df["Net_Mean_Income_Single"] = (df["Mean_Income"] * (1 - df["_RateMean_Single"])).round(0)
df.drop(columns=["_RateMean_MFJ", "_RateMean_Single"], inplace=True)

# Median home price as a % of MEDIAN household income -- e.g. 400% means the
# median home costs 4x the median household's annual income that year.
df["Home_Price_Pct_Median_Income"] = (
    df["Median_Home_Price"] / df["Median_Income"] * 100
).round(2)

# --- Manual sources: real figures pulled from BLS Consumer Expenditure ----
# Survey tables, NCES, College Board, Child Care Aware of America, Freddie
# Mac, and other named sources below. See SOURCES.md for full sourcing
# detail and which years are still gaps.

# BLS Consumer Expenditure Survey, "All Consumer Units" -- the true national
# average across every household type (not single-person/married-with-kids
# averaged together). Pulled from BLS's own "multi-year mean expenditure"
# tables, which cover 1984-2022 in five PDF files with no gaps in that
# range for these line items. Annual dollar figures. 2023-2024 grocery/
# car-insurance come from the 2024 "Consumer Expenditures" news release
# (cesan.pdf), Table A; BLS consolidated its published category detail
# starting with 2023 data (121 categories down to 42), and the more-
# detailed table that would have house-insurance/property-tax/electricity/
# water for 2023-2024 is only published as .xlsx, which couldn't be parsed
# in this pass -- see SOURCES.md. 2025 CE data isn't published yet as of
# 2026-09-16.
grocery_annual = {
    1989: 2390, 1990: 2485, 1991: 2651, 1992: 2643, 1993: 2735, 1994: 2712,
    1995: 2803, 1996: 2876, 1997: 2880, 1998: 2780, 1999: 2915, 2000: 3021,
    2001: 3086, 2002: 3099, 2003: 3129, 2004: 3347, 2005: 3297, 2006: 3417,
    2007: 3465, 2008: 3744, 2009: 3753, 2010: 3624, 2011: 3838, 2012: 3921,
    2013: 3977, 2014: 3971, 2015: 4015, 2016: 4049, 2017: 4363, 2018: 4464,
    2019: 4643, 2020: 4942, 2021: 5259, 2022: 5703, 2023: 6053, 2024: 6224,
}
car_insurance_annual = {
    1989: 575, 1990: 563, 1991: 614, 1992: 629, 1993: 678, 1994: 690,
    1995: 712, 1996: 698, 1997: 755, 1998: 739, 1999: 756, 2000: 778,
    2001: 819, 2002: 894, 2003: 905, 2004: 964, 2005: 913, 2006: 886,
    2007: 1071, 2008: 1113, 2009: 1075, 2010: 1010, 2011: 983, 2012: 1018,
    2013: 1013, 2014: 1112, 2015: 1079, 2016: 1149, 2017: 967, 2018: 976,
    2019: 1545, 2020: 1575, 2021: 1528, 2022: 1592, 2023: 1775, 2024: 1993,
}
house_insurance_annual = {  # "owned dwellings: maintenance, repairs, insurance, other expenses"
    1989: 533, 1990: 540, 1991: 559, 1992: 560, 1993: 628, 1994: 651,
    1995: 715, 1996: 729, 1997: 738, 1998: 775, 1999: 854, 2000: 825,
    2001: 884, 2002: 960, 2003: 965, 2004: 997, 2005: 1101, 2006: 1115,
    2007: 1131, 2008: 1176, 2009: 1138, 2010: 1112, 2011: 1120, 2012: 1153,
    2013: 1182, 2014: 1293, 2015: 1438, 2016: 1437, 2017: 1616, 2018: 1703,
    2019: 1879, 2020: 2158, 2021: 2335, 2022: 2559, 2023: 2599, 2024: 2926,
}
property_tax_annual = {
    1989: 575, 1990: 597, 1991: 789, 1992: 782, 1993: 825, 1994: 922,
    1995: 930, 1996: 939, 1997: 971, 1998: 1015, 1999: 1123, 2000: 1139,
    2001: 1233, 2002: 1242, 2003: 1344, 2004: 1391, 2005: 1541, 2006: 1649,
    2007: 1709, 2008: 1758, 2009: 1811, 2010: 1814, 2011: 1845, 2012: 1836,
    2013: 1848, 2014: 1903, 2015: 1913, 2016: 1969, 2017: 2065, 2018: 2200,
    2019: 2159, 2020: 2353, 2021: 2475, 2022: 2570, 2023: 2666, 2024: 2738,
}
electricity_annual = {
    1989: 738, 1990: 758, 1991: 803, 1992: 787, 1993: 836, 1994: 861,
    1995: 869, 1996: 907, 1997: 909, 1998: 921, 1999: 899, 2000: 911,
    2001: 1009, 2002: 981, 2003: 1028, 2004: 1064, 2005: 1155, 2006: 1266,
    2007: 1303, 2008: 1353, 2009: 1377, 2010: 1413, 2011: 1423, 2012: 1388,
    2013: 1422, 2014: 1484, 2015: 1460, 2016: 1444, 2017: 1420, 2018: 1496,
    2019: 1472, 2020: 1516, 2021: 1551, 2022: 1683, 2023: 1763, 2024: 1833,
}
water_annual = {
    1989: 182, 1990: 193, 1991: 217, 1992: 230, 1993: 241, 1994: 257,
    1995: 259, 1996: 268, 1997: 286, 1998: 285, 1999: 285, 2000: 296,
    2001: 321, 2002: 328, 2003: 326, 2004: 327, 2005: 366, 2006: 397,
    2007: 434, 2008: 446, 2009: 481, 2010: 489, 2011: 501, 2012: 525,
    2013: 509, 2014: 530, 2015: 540, 2016: 569, 2017: 583, 2018: 614,
    2019: 645, 2020: 682, 2021: 695, 2022: 739, 2023: 780, 2024: 826,
}
# "Gasoline and motor oil" (BLS's name for this line through ~2012; renamed
# "Gasoline, other fuels, and motor oil" from 2013 on -- same underlying
# category, continuous series). This is total household spending on gas,
# distinct from Gas_Price_Gal (price per gallon) -- it reflects both price
# AND how much driving/fuel a household actually does. Same BLS multi-year
# tables as the other expense columns, plus cesan.pdf Table A for
# 2023-2024. Complete 1989-2024, no gaps.
gas_expenditure_annual = {
    1989: 985, 1990: 1047, 1991: 995, 1992: 973, 1993: 977, 1994: 986,
    1995: 1006, 1996: 1082, 1997: 1098, 1998: 1017, 1999: 1055, 2000: 1291,
    2001: 1279, 2002: 1235, 2003: 1333, 2004: 1598, 2005: 2013, 2006: 2227,
    2007: 2384, 2008: 2715, 2009: 1986, 2010: 2132, 2011: 2655, 2012: 2756,
    2013: 2611, 2014: 2468, 2015: 2090, 2016: 1909, 2017: 1968, 2018: 2109,
    2019: 2094, 2020: 1568, 2021: 2148, 2022: 3120, 2023: 2449, 2024: 2411,
}

# Published/sticker-price annual tuition & fees for a PUBLIC, IN-STATE,
# 4-YEAR institution -- ("average cost for a 4 year
# degree for that year"), confirmed via clarifying question: annual (not
# a 4-year total), tuition & fees only (not room/board), public in-state.
# 1989-2023 are from NCES Digest of Education Statistics, Table 330.10,
# "Tuition and fees" column, CURRENT dollars; academic years (e.g.
# "2022-23") are mapped to their starting calendar year (2022).
# 2024-2025 are from College Board's "Trends in College Pricing 2025"
# report (published tuition & fees, public four-year in-state, current
# dollars) -- NCES has not published 2024-25/2025-26 yet as of
# 2026-09-16. IMPORTANT CAVEAT, added
# these two years anyway: College Board uses an ENROLLMENT-WEIGHTED
# national average, which runs meaningfully higher than NCES's simple
# institutional average for the same year (e.g. NCES's last point, 2023,
# is $9,872; College Board's 2024 figure is $11,610) -- so the jump from
# 2023 to 2024 in this column is partly a real one-year increase and
# partly a methodology switch, not purely the former. See SOURCES.md.
tuition_public_4yr_annual = {
    1989: 1780, 1990: 1888, 1991: 2117, 1992: 2349, 1993: 2537, 1994: 2681,
    1995: 2848, 1996: 2987, 1997: 3110, 1998: 3229, 1999: 3349, 2000: 3501,
    2001: 3735, 2002: 4046, 2003: 4587, 2004: 5027, 2005: 5351, 2006: 5666,
    2007: 5943, 2008: 6312, 2009: 6717, 2010: 7132, 2011: 7713, 2012: 8070,
    2013: 8312, 2014: 8543, 2015: 8778, 2016: 8804, 2017: 9036, 2018: 9212,
    2019: 9349, 2020: 9374, 2021: 9596, 2022: 9750, 2023: 9872,
    2024: 11610, 2025: 11950,
}

# Child Care Aware of America, annual "Price of Care" / price-and-supply
# reports -- NATIONAL average annual price of child care (methodology
# blends multiple state-level estimation approaches; CCAoA's own reports
# caution that a single national figure understates what many families
# actually pay locally). Decision: no clean,
# consistent national annual series exists back to 1989 (BLS's detailed
# "day care centers, nursery schools" line item only appears in per-year
# .xlsx tables, not the aggregated multi-year PDFs used above; the federal
# DOL/Women's Bureau county-level database explicitly advises against a
# single national figure), so this column is filled with real, well-
# sourced recent years only -- 2022-2025 -- and left blank before that,
# same approach used earlier for the (now-removed) state gas-price-range
# column. See SOURCES.md for the year-by-year source list.
childcare_annual = {
    2022: 10853, 2023: 11582, 2024: 13128, 2025: 13184,
}


# Federal minimum hourly wage -- U.S. Department of Labor, "History of
# Federal Minimum Wage Rates Under the Fair Labor Standards Act"
# (https://www.dol.gov/agencies/whd/minimum-wage/history/chart). Fully
# documented, zero-ambiguity federal statute; no survey/estimation
# involved. Each year below is the rate IN EFFECT AS OF DECEMBER 31 of
# that year (a deliberate, simple convention since the rate only changes
# on a handful of specific mid-year effective dates -- see the comment
# after the dict for exactly when each change took effect). The rate has
# been $7.25 since July 24, 2009, unchanged through 2025.
min_wage_hourly = {
    1990: 3.80, 1991: 4.25, 1992: 4.25, 1993: 4.25, 1994: 4.25, 1995: 4.25,
    1996: 4.75, 1997: 5.15, 1998: 5.15, 1999: 5.15, 2000: 5.15, 2001: 5.15,
    2002: 5.15, 2003: 5.15, 2004: 5.15, 2005: 5.15, 2006: 5.15, 2007: 5.85,
    2008: 6.55, 2009: 7.25, 2010: 7.25, 2011: 7.25, 2012: 7.25, 2013: 7.25,
    2014: 7.25, 2015: 7.25, 2016: 7.25, 2017: 7.25, 2018: 7.25, 2019: 7.25,
    2020: 7.25, 2021: 7.25, 2022: 7.25, 2023: 7.25, 2024: 7.25, 2025: 7.25,
}
# Effective dates behind the changes above (DOL, same source):
# Apr 1 1990: $3.80 | Apr 1 1991: $4.25 | Oct 1 1996: $4.75 |
# Sep 1 1997: $5.15 | Jul 24 2007: $5.85 | Jul 24 2008: $6.55 |
# Jul 24 2009: $7.25 (unchanged since).


# Freddie Mac Primary Mortgage Market Survey (PMMS) -- national annual
# average 30-year fixed-rate mortgage rate, loaded directly from the
# primary-source "historicalweeklydata.xlsx" file (Freddie Mac's own
# "Download Rates Since 1971" export, added to this folder).
def load_mortgage_rate_annual(filename="historicalweeklydata.xlsx"):
    if not os.path.exists(filename):
        print(f"  [skip] {filename} not found -- download Freddie Mac's "
              "'Rates Since 1971' file from freddiemac.com/pmms.")
        return {}
    raw = pd.read_excel(filename, sheet_name="Full History", header=5)
    raw = raw.rename(columns={raw.columns[0]: "Week", raw.columns[1]: "Rate30yr"})
    raw["Week"] = pd.to_datetime(raw["Week"], errors="coerce")
    raw = raw.dropna(subset=["Week"])
    raw["Rate30yr"] = pd.to_numeric(raw["Rate30yr"], errors="coerce")
    raw["Year"] = raw["Week"].dt.year
    raw = raw[raw["Year"] <= 2025]
    annual = raw.groupby("Year")["Rate30yr"].mean().round(2)
    print(f"  [ok] merged {filename} -> Mortgage_Rate_30Yr")
    return annual.to_dict()

mortgage_rate_pct = load_mortgage_rate_annual()

# Census Bureau, Housing Vacancy Survey (HVS/CPS), Table 11A -- "Median
# Asking Rent for the U.S. and Regions: 1988 to Present" (current
# dollars), from the primary-source "histtab11.xlsx" file (added to this folder). This is the only long-run, consistent, annual
# national rent series available -- it measures ASKING rent for vacant-
# for-rent units, not gross rent paid by occupied renters, which is a
# well-established long-run proxy but worth noting as a definitional
# difference from, e.g., ACS "median gross rent" (which only starts in
# 2005 and isn't consistent back to 1990). The file's own "Annual" row
# for each year (Census's own aggregate, not a re-derived average) is
# used directly and multiplied by 12 to annualize (the source reports
# median MONTHLY asking rent). 2025's figure carries a Census footnote:
# due to the Oct 2025 government shutdown, HVS did not collect data for
# October 2025, so 2025 Q4 is based on Nov+Dec only and the 2025 annual
# figure excludes October -- still Census's own official published
# number, just based on 11 months instead of 12.
def load_rent_annual(filename="histtab11.xlsx"):
    if not os.path.exists(filename):
        print(f"  [skip] {filename} not found -- download Census's Table "
              "11A/B (Quarterly Median Asking Rent) from "
              "census.gov/housing/hvs/data/histtabs.html.")
        return {}
    raw = pd.read_excel(filename, sheet_name="Sheet1", header=None)
    current_year = None
    monthly = {}
    for i in range(len(raw)):
        v = raw.iloc[i, 0]
        if pd.isna(v):
            continue
        if isinstance(v, (int, float)) and 1980 <= v <= 2030:
            current_year = int(v)
        elif isinstance(v, str) and v.strip().lower().startswith("annual"):
            us_val = raw.iloc[i, 1]
            if not pd.isna(us_val):
                monthly[current_year] = us_val
        elif isinstance(v, str) and "Table 11B" in v:
            break  # stop before the median SALES PRICE table further down
    print(f"  [ok] merged {filename} -> Rent (Census HVS Table 11A, US median asking rent)")
    return {y: val * 12 for y, val in monthly.items()}

rent_annual = load_rent_annual()

# U.S. Census Bureau, American Community Survey (ACS) 1-Year Estimates,
# Table B25119 ("Median Household Income by Tenure") and Table B25071
# ("Median Gross Rent as a Percentage of Household Income"), U.S. total,
# downloaded from data.census.gov and added to this folder as
# ACS_B25119_Renter_Income/ and ACS_B25071_Renter_Burden/ (one *-Data.csv
# per year, Census's own multi-year comparison export). Added
# (2026-09-24) to show what renters specifically earn
# and pay, after the existing Rent/Rent_Pct_Median_Income columns (Census
# HVS asking-rent series) turned out to understate real-world renter rent
# burden -- HVS asking rent is for VACANT units, compared against the
# general Median_Income, not what actual renter households earn and pay.
# ACS 1-year estimates only exist from 2005 on and were not collected in
# 2020 (COVID); the download covers 2010-2024 (2005-2009 not
# included in this pass; 2025 not yet released as of this update -- see
# SOURCES.md and data_through.csv).
#
# B25119_003E ("Renter occupied") is reported in that survey year's own
# current/nominal dollars. To keep it on the same basis as the rest of
# this dataset's income columns (Median_Income/Mean_Income are REAL,
# constant 2025 dollars), each year's nominal renter income is converted
# to real 2025 dollars using this file's own CPI_Index column -- the same
# CPI-based real/nominal conversion already used for Net_Income_MFJ/
# Single above. Note this mixes deflator vintages (Table H-5's real-
# dollar figures use the C-CPI-U-R-S index, while this reuses the file's
# standard CPI-U/CPIAUCNS series) -- close enough for a consistent real-
# dollar view but not an exact same-index match; documented in
# SOURCES.md.
#
# B25071_001E ("Median gross rent as a percentage of household income")
# is already a ratio, so no real/nominal adjustment applies -- used as
# published.
def load_acs_renter_data(folder, var_code):
    """Reads Census's multi-year data.census.gov export (one
    ACSDT1Y{year}.{table}-Data.csv per year) from `folder` and returns
    {year: value} for the given variable code."""
    import glob, re, csv
    if not os.path.isdir(folder):
        print(f"  [skip] {folder}/ not found -- download the table from "
              "data.census.gov and drop the export's *-Data.csv files "
              "into a folder with this name.")
        return {}
    files = glob.glob(os.path.join(folder, "ACSDT1Y*-Data.csv"))
    out = {}
    for f in files:
        m = re.search(r"ACSDT1Y(\d{4})", os.path.basename(f))
        if not m:
            continue
        year = int(m.group(1))
        with open(f, encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        header = rows[0]
        if var_code not in header:
            continue
        idx = header.index(var_code)
        try:
            out[year] = float(rows[2][idx])
        except (IndexError, ValueError):
            continue
    return out

renter_income_nominal = load_acs_renter_data("ACS_B25119_Renter_Income", "B25119_003E")
renter_burden_pct = load_acs_renter_data("ACS_B25071_Renter_Burden", "B25071_001E")

def _to_real_2025(year, nominal):
    cpi_year = df.loc[df["Year"] == year, "CPI_Index"]
    cpi_2025 = df.loc[df["Year"] == 2025, "CPI_Index"]
    if cpi_year.empty or cpi_2025.empty or pd.isna(cpi_year.values[0]) or pd.isna(cpi_2025.values[0]):
        return pd.NA
    return round(nominal * cpi_2025.values[0] / cpi_year.values[0])

renter_income_real = {y: _to_real_2025(y, v) for y, v in renter_income_nominal.items()}
if renter_income_real:
    print(f"  [ok] merged ACS B25119/B25071 -> Renter_Median_Income, "
          f"Renter_Rent_Burden_Pct ({len(renter_income_real)} years)")

# Owner-occupied household income, for Net_Income_MFJ (2026-10-26,
# continued) -- priority for the
# Married Homeowner persona: "the home ownership filter is the most
# important one followed by married median income." Same ACS Table
# B25119 ("Median Household Income by Tenure"), same file set, same year
# range (2010-2024, no 2020 -- ACS wasn't collected that year) and same
# nominal -> real-2025-dollar conversion already used for
# Renter_Median_Income above, just the OTHER tenure column
# (B25119_002E, "Owner occupied") instead of B25119_003E ("Renter
# occupied").
#
# Used as the PRIMARY income base for Net_Income_MFJ wherever ACS covers
# that year; Married_Couple_Median_Income (Table F-7, full 1990-2025
# coverage, added earlier above) is the FALLBACK for years ACS doesn't
# reach (1990-2009, 2020) -- per the stated priority order
# (homeownership match first, marital-status match second). This mixes
# two different Census surveys/methodologies across time (ACS 2010-2024
# excl. 2020, Table F-7 CPS ASEC elsewhere) -- worth a dashboard footnote,
# documented in SOURCES.md.
owner_income_nominal = load_acs_renter_data("ACS_B25119_Renter_Income", "B25119_002E")
owner_income_real = {y: _to_real_2025(y, v) for y, v in owner_income_nominal.items()}
if owner_income_real:
    print(f"  [ok] merged ACS B25119 (Owner occupied) -> Owner_Median_Income ({len(owner_income_real)} years)")

df["Owner_Median_Income"] = df["Year"].map(owner_income_real)

df["Married_Homeowner_Base_Income"] = df["Owner_Median_Income"].where(
    df["Owner_Median_Income"].notna(), df["Married_Couple_Median_Income"])

# Re-run the MFJ bracket-tax calculation on this combined (ACS-owner-
# primary, Table-F-7-fallback) base -- supersedes the
# Married_Couple_Median_Income-only Net_Income_MFJ/Effective_Tax_Rate_MFJ_Pct
# computed earlier above.
df["_Rate_MFJ"] = df.apply(
    lambda r: _bracket_tax_rate_for_row(r["Year"], r["Married_Homeowner_Base_Income"], MFJ_BRACKETS, MFJ_STANDARD_DEDUCTION, cpi_by_year, cpi_2025), axis=1)
df["_Rate_MFJ"] = pd.to_numeric(df["_Rate_MFJ"], errors="coerce")
df["Effective_Tax_Rate_MFJ_Pct"] = (df["_Rate_MFJ"] * 100).round(2)
df["Net_Income_MFJ"] = (df["Married_Homeowner_Base_Income"] * (1 - df["_Rate_MFJ"])).round(0)
df.drop(columns=["_Rate_MFJ"], inplace=True)

for colname, d in [
    ("Grocery", grocery_annual),
    ("Home_Insurance", house_insurance_annual),
    ("Auto_Insurance", car_insurance_annual),
    ("Mortgage_Rate_30Yr", mortgage_rate_pct),
    ("Property_Tax", property_tax_annual),
    ("Electricity", electricity_annual),
    ("Water", water_annual),
    ("Gas_Spend", gas_expenditure_annual),
    ("Public_Tuition_4Yr", tuition_public_4yr_annual),
    ("Childcare", childcare_annual),
    ("Min_Wage_Hourly", min_wage_hourly),
    ("Rent", rent_annual),
    ("Renter_Median_Income", renter_income_real),
    ("Renter_Rent_Burden_Pct", renter_burden_pct),
]:
    df[colname] = df["Year"].map(d)

# Family-specific (married couple with children) cost figures, for the
# Married Homeowner sheet specifically (2026-10-27)
# -- the Married Homeowner and Single Renter treemaps had been
# reusing the SAME blended national-average dollar figures for Groceries,
# Home Insurance, and Auto Insurance, only dividing by different income;
# these columns use figures that actually represent a married-with-
# children household's costs instead.
#
# Source: BLS Consumer Expenditure Survey, "Composition of consumer
# unit" table (the same source family already used for the blended
# Grocery/Home_Insurance/Auto_Insurance columns, before they were
# blended per the 2026-09-16 restructuring note), "Married couple with
# children: Total" column -- https://www.bls.gov/cex/tables/calendar-year/
# mean-item-share-average-standard-error/cu-composition-2022.pdf (the
# most recent year published as a readable PDF; 2023 and 2024 exist only
# as an unparseable .xlsx as of this writing -- see SOURCES.md).
#
# Confirmed: recent-years-only is fine, used only on the Married
# Homeowner sheet. Held FLAT from the 2022 figure for 2022-2025 (rather
# than left blank) so the Married Homeowner sheet's Year=2024 view has a
# value -- a known approximation, not actual 2024 spending. These are
# NEW columns alongside the existing blended Grocery/Home_Insurance/
# Auto_Insurance columns, which are UNCHANGED -- every other sheet
# (Single Renter, the 1990-vs-2024 comparison) keeps using the blended
# figures exactly as before.
family_grocery = {y: 8309 for y in range(2022, 2026)}
family_home_insurance = {y: 3106 for y in range(2022, 2026)}
family_auto_insurance = {y: 2113 for y in range(2022, 2026)}
family_health_insurance = {y: 4714 for y in range(2022, 2026)}
family_utilities = {y: 5957 for y in range(2022, 2026)}

for colname, d in [
    ("Grocery_Family", family_grocery),
    ("Home_Insurance_Family", family_home_insurance),
    ("Auto_Insurance_Family", family_auto_insurance),
    ("Health_Insurance_Family", family_health_insurance),
    ("Utilities_Family", family_utilities),
]:
    df[colname] = df["Year"].map(d)
print("  [ok] added Grocery_Family, Home_Insurance_Family, Auto_Insurance_Family, "
      "Health_Insurance_Family, Utilities_Family "
      "(BLS CE composition table, married couple w/ children, 2022 figure held flat 2022-2025)")

# 2026-10-27 (same request, same source table): single-person-specific
# figures, same table's "Single person and other consumer units" column,
# to replace the blended national average on the Single Renter sheet the
# same way the _Family columns do for the Married Homeowner sheet. Held
# flat 2022-2025 for the same reason. NEW columns -- the existing blended
# Grocery/Home_Insurance/Auto_Insurance/Health_Insurance/Utilities-related
# columns are UNCHANGED.
# UPDATED 2026-10-27 (same day, later revision): Correction: this
# sheet is "Single Renter w/CHILD" -- since Childcare is already modeled,
# the persona is a single PARENT, not a childless single person. BLS's
# same composition table has a dedicated "One parent, at least one child
# under 18" column, which is the correct match -- swapped in below,
# superseding the "single person and other consumer units" figures used
# in the same-day earlier revision (kept as a comment for history).
#   previously (single person and other consumer units): grocery=4081,
#   auto_insurance=1239, health_insurance=2649, utilities=3473
# Column names keep the "_Single_Person" suffix even though the values
# now represent a single PARENT -- renaming would break the Tableau
# calculated fields already wired to these exact column names
# (Auto Insurance % Net Income Single, Health Insurance % Net Income
# Single). See SOURCES.md for the full explanation.
single_grocery = {y: 5453 for y in range(2022, 2026)}
single_auto_insurance = {y: 1421 for y in range(2022, 2026)}
single_health_insurance = {y: 2102 for y in range(2022, 2026)}
single_utilities = {y: 4206 for y in range(2022, 2026)}

for colname, d in [
    ("Grocery_Single_Parent", single_grocery),
    ("Auto_Insurance_Single_Parent", single_auto_insurance),
    ("Health_Insurance_Single_Parent", single_health_insurance),
    ("Utilities_Single_Parent", single_utilities),
]:
    df[colname] = df["Year"].map(d)
print("  [ok] added Grocery_Single_Parent, Auto_Insurance_Single_Parent, "
      "Health_Insurance_Single_Parent, Utilities_Single_Parent "
      "(BLS CE composition table, ONE PARENT AT LEAST ONE CHILD UNDER 18, "
      "2022 figure held flat 2022-2025 -- column names kept for Tableau "
      "compatibility, see SOURCES.md)")

# Whole-dollar already (source dicts are plain ints), but keep the round()
# for safety/consistency.
for c in ["Grocery", "Home_Insurance", "Auto_Insurance", "Property_Tax",
          "Electricity", "Water", "Gas_Spend", "Rent"]:
    df[c] = df[c].round(0)

df["Gas_Price_Gal"] = df["Gas_Price_Gal"].round(2)
df["Savings_Rate_Pct"] = df["Savings_Rate_Pct"].round(2)
df["Min_Wage_Hourly"] = df["Min_Wage_Hourly"].round(2)

# --- Estimated lifetime mortgage interest (2026-09-16) ---
# Purely derived, no new external source: assumes a 20% down payment (loan
# amount = 80% of Median_Home_Price, a standard conventional-loan
# assumption that avoids PMI) financed over the full 30-year term at that
# year's Mortgage_Rate_30Yr, using the standard fixed-rate amortization
# formula. This is the total interest paid over the full life of the loan
# if the rate never changed and every payment was made on schedule -- a
# simplified, illustrative figure, not an actual loan product. Blank
# wherever home price or mortgage rate is blank.
def lifetime_interest(row):
    price = row["Median_Home_Price"]
    rate_pct = row["Mortgage_Rate_30Yr"]
    if pd.isna(price) or pd.isna(rate_pct):
        return pd.NA
    principal = price * 0.80
    n_payments = 360  # 30 years x 12
    r = rate_pct / 100 / 12
    if r == 0:
        monthly_payment = principal / n_payments
    else:
        monthly_payment = principal * r * (1 + r) ** n_payments / ((1 + r) ** n_payments - 1)
    return monthly_payment * n_payments - principal

df["Lifetime_Interest"] = df.apply(lifetime_interest, axis=1).astype(float).round(2)

# --- Derived %-of-income columns (2026-09-16) ---
# All computed from the already-rounded (whole-dollar) ANNUAL figures
# above and divided by Mean_Income (not median) -- these are expense-based
# ratios against BLS "All Consumer Units" MEAN spending figures, so the
# denominator is switched to mean income too for an apples-to-apples
# comparison (mean-to-mean, not mean-to-median). Home_Price_Pct_Median_
# Income (above) stays on median/median, since both home price and that
# ratio are genuinely median-based. Both income columns are raw numbers at
# this point in the script (string formatting happens further down).
# Blank wherever an input is blank.
df["Insurance_Pct_Mean_Income"] = (
    (df["Home_Insurance"] + df["Auto_Insurance"]) / df["Mean_Income"] * 100
).round(2)

df["Utilities_Pct_Mean_Income"] = (
    (df["Water"] + df["Electricity"]) / df["Mean_Income"] * 100
).round(2)

df["Grocery_Pct_Mean_Income"] = (
    df["Grocery"] / df["Mean_Income"] * 100
).round(2)

df["Property_Tax_Pct_Mean_Income"] = (
    df["Property_Tax"] / df["Mean_Income"] * 100
).round(2)

df["Childcare_Pct_Mean_Income"] = (
    df["Childcare"] / df["Mean_Income"] * 100
).round(2)

df["Gas_Pct_Mean_Income"] = (
    df["Gas_Spend"] / df["Mean_Income"] * 100
).round(2)

# Rent uses MEDIAN income (not mean), since Census HVS asking rent is
# itself a median statistic -- median/median, same logic as
# Home_Price_Pct_Median_Income.
df["Rent_Pct_Median_Income"] = (
    df["Rent"] / df["Median_Income"] * 100
).round(2)

# ---- Net-income-based companion ratios (2026-09-17)
# ----
# Question considered: whether the %-of-income columns should be based on take-
# home (net) pay instead of gross, since it would be more realistic and
# more compelling for storytelling/affordability measurement. Decision:
# ADD these alongside the existing gross-based ratios rather than replace
# them -- the gross-based ratios stay comparable to standard published
# affordability benchmarks (HUD's 30%-of-gross-income cost-burden
# definition, the classic "30% rule", front-end DTI), while these new
# net-based ratios show the more visceral real-world burden. The GAP
# between a metric's gross and net ratio is itself a compelling dashboard
# story ("looks like 28% by the textbook definition, but it's really 34%
# of what a family actually takes home"). Both MFJ and Single filing-
# status variants are provided, by design, mirroring
# Net_Income_MFJ/Net_Income_Single. Two columns whose gross version used
# Median_Income (Home_Price, Rent) are divided by Net_Income_MFJ/Single;
# the six whose gross version used Mean_Income are divided by
# Net_Mean_Income_MFJ/Single (see above) for a like-for-like mean-to-mean
# comparison, same logic as the gross versions.
df["Home_Price_Pct_Net_Income_MFJ"] = (
    df["Median_Home_Price"] / df["Net_Income_MFJ"] * 100
).round(2)
df["Home_Price_Pct_Net_Income_Single"] = (
    df["Median_Home_Price"] / df["Net_Income_Single"] * 100
).round(2)

df["Rent_Pct_Net_Income_MFJ"] = (
    df["Rent"] / df["Net_Income_MFJ"] * 100
).round(2)
df["Rent_Pct_Net_Income_Single"] = (
    df["Rent"] / df["Net_Income_Single"] * 100
).round(2)

df["Grocery_Pct_Net_Income_MFJ"] = (
    df["Grocery"] / df["Net_Mean_Income_MFJ"] * 100
).round(2)
# NOTE (2026-10-27): SUPERSEDED for the Married Homeowner sheet -- the
# shipped affordability_merged.csv overrides this column's 2022-2025
# values with Grocery_Family / Net_Income_MFJ instead (BLS married-couple-
# with-children figure over the owner-occupied-primary married income),
# matching how Auto/Home/Health Insurance are already handled on that
# sheet. Applied as a one-off post-processing step; see SOURCES.md.
# Kept here so a fresh run of this script doesn't crash.
df["Grocery_Pct_Net_Income_Single"] = (
    df["Grocery"] / df["Net_Mean_Income_Single"] * 100
).round(2)
# NOTE (2026-10-27): Grocery_Pct_Net_Income_Single as computed above is
# SUPERSEDED for the Single Renter sheet -- the shipped affordability_merged.csv
# overrides this column's 2010-2024 values with Grocery_Single_Parent /
# Renter_Net_Income_Single instead (BLS single-person figure over the
# tenure-correct renter income, matching how Auto_Insurance/Health_Insurance
# are already handled on this sheet). The override can't live in this script
# because Renter_Net_Income_Single is a patch-only column this pipeline does
# not reproduce (see "Known inconsistency to watch" notes) -- it's applied as
# a one-off post-processing step and documented in SOURCES.md. Kept here so
# a fresh run of this script doesn't crash; do not rely on this line's output
# for the Single Renter sheet without reapplying that override afterward.

df["Insurance_Pct_Net_Income_MFJ"] = (
    (df["Home_Insurance"] + df["Auto_Insurance"]) / df["Net_Mean_Income_MFJ"] * 100
).round(2)
df["Insurance_Pct_Net_Income_Single"] = (
    (df["Home_Insurance"] + df["Auto_Insurance"]) / df["Net_Mean_Income_Single"] * 100
).round(2)

df["Utilities_Pct_Net_Income_MFJ"] = (
    (df["Water"] + df["Electricity"]) / df["Net_Mean_Income_MFJ"] * 100
).round(2)
# NOTE (2026-10-27): same situation as Grocery_Pct_Net_Income_MFJ above --
# SUPERSEDED for the Married Homeowner sheet by Utilities_Family /
# Net_Income_MFJ. See SOURCES.md.
df["Utilities_Pct_Net_Income_Single"] = (
    (df["Water"] + df["Electricity"]) / df["Net_Mean_Income_Single"] * 100
).round(2)
# NOTE (2026-10-27): same situation as Grocery_Pct_Net_Income_Single above --
# SUPERSEDED for the Single Renter sheet by a post-processing override using
# Utilities_Single_Parent / Renter_Net_Income_Single. See that note and
# SOURCES.md for detail.

df["Childcare_Pct_Net_Income_MFJ"] = (
    df["Childcare"] / df["Net_Mean_Income_MFJ"] * 100
).round(2)
df["Childcare_Pct_Net_Income_Single"] = (
    df["Childcare"] / df["Net_Mean_Income_Single"] * 100
).round(2)

df["Gas_Pct_Net_Income_MFJ"] = (
    df["Gas_Spend"] / df["Net_Mean_Income_MFJ"] * 100
).round(2)
df["Gas_Pct_Net_Income_Single"] = (
    df["Gas_Spend"] / df["Net_Mean_Income_Single"] * 100
).round(2)

df["Property_Tax_Pct_Net_Income_MFJ"] = (
    df["Property_Tax"] / df["Net_Mean_Income_MFJ"] * 100
).round(2)
df["Property_Tax_Pct_Net_Income_Single"] = (
    df["Property_Tax"] / df["Net_Mean_Income_Single"] * 100
).round(2)

# Put the %-of-income columns right after their related columns.
# Median_Income and Mean_Income go right after Year, as the first two
# data columns (2026-09-16).
cols = list(df.columns)
for c in ["Median_Income", "Married_Couple_Median_Income", "Owner_Median_Income", "Married_Homeowner_Base_Income", "Grocery_Family", "Home_Insurance_Family", "Auto_Insurance_Family", "Health_Insurance_Family", "Utilities_Family", "Grocery_Single_Parent", "Auto_Insurance_Single_Parent", "Health_Insurance_Single_Parent", "Utilities_Single_Parent", "Mean_Income", "Net_Income_MFJ", "Effective_Tax_Rate_MFJ_Pct",
          "Net_Income_Single", "Effective_Tax_Rate_Single_Pct",
          "Net_Mean_Income_MFJ", "Net_Mean_Income_Single",
          "Home_Price_Pct_Median_Income", "Home_Price_Pct_Net_Income_MFJ", "Home_Price_Pct_Net_Income_Single",
          "Mortgage_Rate_30Yr", "Lifetime_Interest", "Public_Tuition_4Yr",
          "Min_Wage_Hourly", "Gas_Spend",
          "Insurance_Pct_Mean_Income", "Insurance_Pct_Net_Income_MFJ", "Insurance_Pct_Net_Income_Single",
          "Utilities_Pct_Mean_Income", "Utilities_Pct_Net_Income_MFJ", "Utilities_Pct_Net_Income_Single",
          "Grocery_Pct_Mean_Income", "Grocery_Pct_Net_Income_MFJ", "Grocery_Pct_Net_Income_Single",
          "Childcare_Pct_Mean_Income", "Childcare_Pct_Net_Income_MFJ", "Childcare_Pct_Net_Income_Single",
          "Gas_Pct_Mean_Income", "Gas_Pct_Net_Income_MFJ", "Gas_Pct_Net_Income_Single",
          "Rent", "Rent_Pct_Median_Income", "Rent_Pct_Net_Income_MFJ", "Rent_Pct_Net_Income_Single",
          "Property_Tax_Pct_Mean_Income", "Property_Tax_Pct_Net_Income_MFJ", "Property_Tax_Pct_Net_Income_Single"]:
    cols.remove(c)
cols.insert(cols.index("Year") + 1, "Median_Income")
cols.insert(cols.index("Year") + 2, "Married_Couple_Median_Income")
cols.insert(cols.index("Year") + 3, "Owner_Median_Income")
cols.insert(cols.index("Year") + 4, "Married_Homeowner_Base_Income")
cols.insert(cols.index("Year") + 5, "Net_Income_MFJ")
cols.insert(cols.index("Year") + 6, "Effective_Tax_Rate_MFJ_Pct")
cols.insert(cols.index("Year") + 7, "Net_Income_Single")
cols.insert(cols.index("Year") + 8, "Effective_Tax_Rate_Single_Pct")
cols.insert(cols.index("Year") + 9, "Mean_Income")
cols.insert(cols.index("Mean_Income") + 1, "Grocery_Family")
cols.insert(cols.index("Grocery_Family") + 1, "Home_Insurance_Family")
cols.insert(cols.index("Home_Insurance_Family") + 1, "Auto_Insurance_Family")
cols.insert(cols.index("Auto_Insurance_Family") + 1, "Health_Insurance_Family")
cols.insert(cols.index("Health_Insurance_Family") + 1, "Utilities_Family")
cols.insert(cols.index("Utilities_Family") + 1, "Grocery_Single_Parent")
cols.insert(cols.index("Grocery_Single_Parent") + 1, "Auto_Insurance_Single_Parent")
cols.insert(cols.index("Auto_Insurance_Single_Parent") + 1, "Health_Insurance_Single_Parent")
cols.insert(cols.index("Health_Insurance_Single_Parent") + 1, "Utilities_Single_Parent")
cols.insert(cols.index("Mean_Income") + 1, "Net_Mean_Income_MFJ")
cols.insert(cols.index("Net_Mean_Income_MFJ") + 1, "Net_Mean_Income_Single")
insert_at = cols.index("Median_Home_Price") + 1
cols.insert(insert_at, "Home_Price_Pct_Median_Income")
cols.insert(insert_at + 1, "Home_Price_Pct_Net_Income_MFJ")
cols.insert(insert_at + 2, "Home_Price_Pct_Net_Income_Single")
cols.insert(insert_at + 3, "Mortgage_Rate_30Yr")
cols.insert(insert_at + 4, "Lifetime_Interest")
cols.insert(insert_at + 5, "Public_Tuition_4Yr")
cols.insert(insert_at + 6, "Min_Wage_Hourly")
cols.insert(cols.index("Avg_Home_Price") + 1, "Rent")
cols.insert(cols.index("Rent") + 1, "Rent_Pct_Median_Income")
cols.insert(cols.index("Rent_Pct_Median_Income") + 1, "Rent_Pct_Net_Income_MFJ")
cols.insert(cols.index("Rent_Pct_Net_Income_MFJ") + 1, "Rent_Pct_Net_Income_Single")
cols.insert(cols.index("Rent_Pct_Net_Income_Single") + 1, "Renter_Median_Income")
cols.insert(cols.index("Renter_Median_Income") + 1, "Renter_Rent_Burden_Pct")
cols.insert(cols.index("Grocery") + 1, "Grocery_Pct_Mean_Income")
cols.insert(cols.index("Grocery_Pct_Mean_Income") + 1, "Grocery_Pct_Net_Income_MFJ")
cols.insert(cols.index("Grocery_Pct_Net_Income_MFJ") + 1, "Grocery_Pct_Net_Income_Single")
cols.insert(cols.index("Auto_Insurance") + 1, "Insurance_Pct_Mean_Income")
cols.insert(cols.index("Insurance_Pct_Mean_Income") + 1, "Insurance_Pct_Net_Income_MFJ")
cols.insert(cols.index("Insurance_Pct_Net_Income_MFJ") + 1, "Insurance_Pct_Net_Income_Single")
cols.insert(cols.index("Property_Tax") + 1, "Property_Tax_Pct_Mean_Income")
cols.insert(cols.index("Property_Tax_Pct_Mean_Income") + 1, "Property_Tax_Pct_Net_Income_MFJ")
cols.insert(cols.index("Property_Tax_Pct_Net_Income_MFJ") + 1, "Property_Tax_Pct_Net_Income_Single")
cols.insert(cols.index("Water") + 1, "Utilities_Pct_Mean_Income")
cols.insert(cols.index("Utilities_Pct_Mean_Income") + 1, "Utilities_Pct_Net_Income_MFJ")
cols.insert(cols.index("Utilities_Pct_Net_Income_MFJ") + 1, "Utilities_Pct_Net_Income_Single")
cols.insert(cols.index("Childcare") + 1, "Childcare_Pct_Mean_Income")
cols.insert(cols.index("Childcare_Pct_Mean_Income") + 1, "Childcare_Pct_Net_Income_MFJ")
cols.insert(cols.index("Childcare_Pct_Net_Income_MFJ") + 1, "Childcare_Pct_Net_Income_Single")
cols.insert(cols.index("Gas_Price_Gal") + 1, "Gas_Spend")
cols.insert(cols.index("Gas_Spend") + 1, "Gas_Pct_Mean_Income")
cols.insert(cols.index("Gas_Pct_Mean_Income") + 1, "Gas_Pct_Net_Income_MFJ")
cols.insert(cols.index("Gas_Pct_Net_Income_MFJ") + 1, "Gas_Pct_Net_Income_Single")
df = df[cols]

# ---- Final numeric rounding (2026-09-17: symbols/formatting REMOVED
# -- every column is now a plain number, no $, %, or k
# suffix, so Tableau reads them as measures instead of dimensions. Scale
# choice: dollar columns store the TRUE raw dollar amount (e.g. Median_
# Income = 87500, not 87.5) rather than a pre-divided "in thousands"
# value -- mixing some columns pre-scaled to thousands and others not
# would make any cross-column arithmetic in Tableau (e.g. Rent as a share
# of Median_Income) silently wrong unless every formula remembered which
# columns were scaled. Percent columns keep the same XX.X number they
# always displayed (e.g. 20.5, not 0.205) -- NOTE: that means Tableau's
# built-in Percentage number format will multiply by 100 and show
# "2050.0%"; format these as Number with a custom "0.0'%'" format instead,
# or divide by 100 first if a true fraction is wanted.) ----
dollar_whole_cols = ["Median_Income", "Mean_Income", "Net_Income_MFJ", "Net_Income_Single",
                      "Net_Mean_Income_MFJ", "Net_Mean_Income_Single", "Median_Home_Price",
                      "Avg_Home_Price", "Lifetime_Interest", "Public_Tuition_4Yr",
                      "Childcare", "Rent", "Grocery", "Home_Insurance",
                      "Auto_Insurance", "Property_Tax", "Electricity", "Water",
                      "Gas_Spend", "Renter_Median_Income"]
for c in dollar_whole_cols:
    df[c] = df[c].round(0).astype("Int64")  # nullable int -- drops trailing .0, keeps blanks blank

dollar_2dp_cols = ["Gas_Price_Gal", "Min_Wage_Hourly"]
for c in dollar_2dp_cols:
    df[c] = df[c].round(2)

pct_cols = ["Home_Price_Pct_Median_Income", "Mortgage_Rate_30Yr", "Savings_Rate_Pct",
            "Insurance_Pct_Mean_Income", "Utilities_Pct_Mean_Income",
            "Grocery_Pct_Mean_Income", "Childcare_Pct_Mean_Income",
            "Gas_Pct_Mean_Income", "Rent_Pct_Median_Income",
            "Property_Tax_Pct_Mean_Income", "Effective_Tax_Rate_MFJ_Pct", "Effective_Tax_Rate_Single_Pct",
            "Home_Price_Pct_Net_Income_MFJ", "Home_Price_Pct_Net_Income_Single",
            "Rent_Pct_Net_Income_MFJ", "Rent_Pct_Net_Income_Single",
            "Grocery_Pct_Net_Income_MFJ", "Grocery_Pct_Net_Income_Single",
            "Insurance_Pct_Net_Income_MFJ", "Insurance_Pct_Net_Income_Single",
            "Utilities_Pct_Net_Income_MFJ", "Utilities_Pct_Net_Income_Single",
            "Childcare_Pct_Net_Income_MFJ", "Childcare_Pct_Net_Income_Single",
            "Gas_Pct_Net_Income_MFJ", "Gas_Pct_Net_Income_Single",
            "Property_Tax_Pct_Net_Income_MFJ", "Property_Tax_Pct_Net_Income_Single",
            "Renter_Rent_Burden_Pct"]
for c in pct_cols:
    df[c] = df[c].round(2)

df["CPI_Index"] = pd.to_numeric(df["CPI_Index"], errors="coerce").round(1)

out = "affordability_merged.csv"
df.to_csv(out, index=False)
print(f"\nWrote {out} -- {df.shape[0]} rows x {df.shape[1]} columns.")
