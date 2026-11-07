"""
fix_dollar_basis.py -- puts every income column on the same dollar basis
as the cost columns, then recomputes the %-of-income columns.

THE PROBLEM THIS FIXES
----------------------
The cost columns (Median_Home_Price, Rent, Grocery, insurance, utilities,
Gas_Spend, Childcare, Property_Tax, ...) are NOMINAL: each year's actual
dollars. The income columns were stored in REAL, constant 2025 dollars.
Dividing a nominal cost by a real income understates every year before
2025 -- e.g. 1990 rent came out as 6.6% of median income when the true
nominal-to-nominal figure is 14.9%.

THE FIX
-------
Convert every income column to nominal (current) dollars, using the SAME
source and deflator each was originally built from:
  * Census Table H-5 (Median_Income, and the mean-income base behind some
    net-income ratios) and Table F-7 (Married_Couple_Median_Income):
    each table publishes a current-dollar column next to its 2025-dollar
    column, so the exact published current-dollar figure is used, matched
    to the same table row the merge used.
  * ACS-based incomes (Owner_Median_Income, Renter_Median_Income, and the
    net incomes built on them) were converted to 2025 dollars with CPI-U
    (CPI_Index) by merge_data.py, so that conversion is reversed exactly.
Tax rates are unchanged (they were already computed on nominal income),
so net incomes scale by the same factor as the income they come from.

Each %-of-income column is then rescaled by its own denominator's factor:
  corrected_pct = old_pct * (real_income / nominal_income)
and every rescaled value is checked against an independent recomputation
from the corrected columns.

After this step, ALL dollar columns are nominal. Use CPI_Index to convert
any of them to constant dollars:
  real_2025 = value * CPI_Index[2025] / CPI_Index[year]

Run:  python3 fix_dollar_basis.py
Reads/writes affordability_merged.xlsx and affordability_merged.csv in
this folder. Run it ONCE on the real-dollar file; it refuses to run twice.
"""
import re
import shutil
import datetime
import pandas as pd
from openpyxl import load_workbook

XLSX, CSV, SHEET = "affordability_merged.xlsx", "affordability_merged.csv", "Affordability Data"

df = pd.read_excel(XLSX, sheet_name=SHEET)
df = df.set_index("Year")

# Guard: 1990 real median income is ~$67k; nominal was ~$30k.
if df.at[1990, "Median_Income"] < 40000:
    raise SystemExit("Income columns already look nominal -- nothing to do.")


def census_rows(path, sheet, section=None):
    """Return {year: [(current_dollars, real_2025_dollars), ...]} for the
    first block of the table (or the named section), in table order."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    out, started, in_section = {}, False, section is None
    for _, r in raw.iterrows():
        label = r[0]
        if section and isinstance(label, str) and section in label:
            in_section = True
            continue
        if not in_section:
            continue
        m = None if pd.isna(label) else re.match(r"^(\d{4})", str(label))
        if not m:
            if started:
                break
            continue
        started = True
        try:
            out.setdefault(int(m.group(1)), []).append((float(r[2]), float(r[3]), float(r[4]), float(r[5])))
        except (TypeError, ValueError):
            continue
    return out


def nominal_for(rows_by_year, year, real_value, real_col=1, cur_col=0):
    """Pick the published row whose real-dollar value matches ours, and
    return its current-dollar value (handles years listed twice)."""
    for row in rows_by_year.get(year, []):
        if abs(row[real_col] - real_value) <= 1:
            return row[cur_col]
    raise ValueError(f"No Census row for {year} matching {real_value}")


h5 = census_rows("h05.xlsx", "h05")                                   # All Races block
f7 = census_rows("f07ar.xlsx", "f07ar", section="Married-Couple Families")

years = df.index
cpi = df["CPI_Index"]
f_cpi = cpi / cpi[2025]                                              # ACS / CPI-U basis

# Census H-5 median factor (exact, row-matched) and mean factor.
med_nom = pd.Series({y: nominal_for(h5, y, df.at[y, "Median_Income"]) for y in years})
f_med = med_nom / df["Median_Income"]
f_mean = pd.Series({y: next(r[2] / r[3] for r in h5[y]
                            if abs(r[1] - df.at[y, "Median_Income"]) <= 1) for y in years})

# Census F-7 married-couple factor (exact, row-matched; first listing wins,
# as in merge_data.py).
mc_nom = pd.Series({y: nominal_for(f7, y, df.at[y, "Married_Couple_Median_Income"]) for y in years})
f_mc = mc_nom / df["Married_Couple_Median_Income"]

# Married homeowner base = ACS owner income where available, else F-7.
acs_owner_years = df["Owner_Median_Income"].notna()
f_mfj = f_mc.where(~acs_owner_years, f_cpi)

old = df.copy()

# ---- 1. Income columns -> nominal --------------------------------------
df["Median_Income"] = med_nom.round(0)
df["Married_Couple_Median_Income"] = mc_nom.round(0)
df["Owner_Median_Income"] = (old["Owner_Median_Income"] * f_cpi).round(0)
df["Married_Homeowner_Base_Income"] = (old["Married_Homeowner_Base_Income"] * f_mfj).round(0)
df["Net_Income_MFJ"] = (old["Net_Income_MFJ"] * f_mfj).round(0)
df["Net_Income_Single"] = (old["Net_Income_Single"] * f_med).round(0)
df["Renter_Median_Income"] = (old["Renter_Median_Income"] * f_cpi).round(0)
df["Renter_Net_Income_Single"] = (old["Renter_Net_Income_Single"] * f_cpi).round(0)

# ---- 2. %-of-income columns -> rescale by their denominator's factor ---
# Which income each column divides by was established by back-solving
# every value in the file (numerator / pct) against the income columns.
renter_years = old["Renter_Net_Income_Single"].notna()
rules = {
    # column: (factor series, independent check: (numerator, new denominator) or None)
    "Home_Price_Pct_Median_Income": (f_med, ("Median_Home_Price", "Median_Income")),
    "Rent_Pct_Median_Income":       (f_med, ("Rent", "Median_Income")),
    "Home_Price_Pct_Net_Income_MFJ": (f_mfj, ("Median_Home_Price", "Net_Income_MFJ")),
    "Rent_Pct_Net_Income_MFJ":       (f_mfj, ("Rent", "Net_Income_MFJ")),
    "Grocery_Pct_Net_Income_MFJ":    (f_mfj, ("Grocery_Family", "Net_Income_MFJ")),
    "Utilities_Pct_Net_Income_MFJ":  (f_mfj, ("Utilities_Family", "Net_Income_MFJ")),
    # these four divide by net MEAN household income (Census H-5 basis)
    "Gas_Pct_Net_Income_MFJ":        (f_mean, None),
    "Insurance_Pct_Net_Income_MFJ":  (f_mean, None),
    "Property_Tax_Pct_Net_Income_MFJ": (f_mean, None),
    "Childcare_Pct_Net_Income_MFJ":  (f_mean, None),
    "Home_Price_Pct_Net_Income_Single": (f_med, ("Median_Home_Price", "Net_Income_Single")),
    "Insurance_Pct_Net_Income_Single":  (f_med, None),
    "Property_Tax_Pct_Net_Income_Single": (f_med, ("Property_Tax", "Net_Income_Single")),
    # renter-based where the renter net income exists, otherwise all-household single
    "Rent_Pct_Net_Income_Single":     (f_cpi.where(renter_years, f_med), None),
    "Gas_Pct_Net_Income_Single":      (f_cpi.where(renter_years, f_med), None),
    "Grocery_Pct_Net_Income_Single":  (f_cpi.where(renter_years, f_med), ("Grocery_Single_Parent", "Renter_Net_Income_Single")),
    "Utilities_Pct_Net_Income_Single": (f_cpi.where(renter_years, f_med), ("Utilities_Single_Parent", "Renter_Net_Income_Single")),
    "Childcare_Pct_Net_Income_Single": (f_cpi.where(renter_years, f_med), None),
}
for col, (factor, _) in rules.items():
    df[col] = (old[col] / factor).round(2)

# ---- 3. Verify ---------------------------------------------------------
problems = []
for col, (_, check) in rules.items():
    if not check:
        continue
    num, den = check
    recomputed = df[num] / df[den] * 100
    mask = df[col].notna() & recomputed.notna()
    # only rows where the original value used this exact formula
    orig_formula = (old[num] / old[den] * 100 - old[col]).abs() < 0.05
    bad = (recomputed[mask & orig_formula] - df[col][mask & orig_formula]).abs() > 0.1
    if bad.any():
        problems.append((col, list(bad[bad].index)))
# Rent/Gas single: check against whichever income the original used
for col, num in [("Rent_Pct_Net_Income_Single", "Rent"), ("Gas_Pct_Net_Income_Single", "Gas_Spend")]:
    den = pd.Series(["Renter_Net_Income_Single" if r else "Net_Income_Single" for r in renter_years], index=years)
    rec = pd.Series({y: df.at[y, num] / df.at[y, den[y]] * 100 for y in years})
    mask = df[col].notna() & rec.notna()
    bad = (rec[mask] - df[col][mask]).abs() > 0.1
    if bad.any():
        problems.append((col, list(bad[bad].index)))
if problems:
    raise SystemExit(f"Verification failed: {problems}")
print("Verification passed: rescaled ratios match independent recomputation.")

# ---- 4. Save (backups first) -------------------------------------------
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
for f in (XLSX, CSV):
    shutil.copy(f, f"{f}.real_dollars_backup_{stamp}")

out = df.reset_index()
int_cols = ["Median_Income", "Married_Couple_Median_Income", "Owner_Median_Income",
            "Married_Homeowner_Base_Income", "Net_Income_MFJ", "Net_Income_Single",
            "Renter_Median_Income", "Renter_Net_Income_Single"]
for c in int_cols:
    out[c] = out[c].astype("Int64")
out.to_csv(CSV, index=False)

# Write values into the existing workbook so its formatting is kept.
wb = load_workbook(XLSX)
ws = wb[SHEET]
header = [c.value for c in ws[1]]
changed = int_cols + list(rules)
for col in changed:
    j = header.index(col) + 1
    for i, v in enumerate(out[col], start=2):
        ws.cell(row=i, column=j).value = None if pd.isna(v) else (int(v) if col in int_cols else float(v))
wb.save(XLSX)
print(f"Saved {XLSX} and {CSV} (backups: *.real_dollars_backup_{stamp})")
