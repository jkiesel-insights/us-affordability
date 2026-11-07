# Data Dictionary: `affordability_merged.csv` / `.xlsx`

36 rows (one per year, 1990–2025) × 62 columns.

## How to read this file

- **All dollar columns are nominal**: each year's actual dollars, so incomes and costs are on the same basis and every "% of income" column compares like with like. To express any dollar column in constant 2025 dollars: `value × CPI_Index[2025] ÷ CPI_Index[year]`.
- Values are plain numbers (no `$`, `%`, or `k`). Percent columns store the displayed number (`20.47` = 20.47%), not a 0–1 fraction.
- **Gross** columns use pre-tax income. **Net** columns (`_MFJ` = married filing jointly, `_Single` = single filer) use estimated income after **federal income tax only**: no state/local or payroll tax, and no exemptions or credits. Net figures are a simplification and likely understate true take-home pay slightly.
- **Derived** means calculated from other columns in this file.
- Blank cells mean no published data for that year (for example, BLS 2025 spending, or ACS 2020, when the 1-year survey wasn't released).

## Household income

| Column | Definition | Source | Coverage |
|---|---|---|---|
| `Year` | Calendar year | — | 1990–2025 |
| `Median_Income` | Median U.S. household income, pre-tax | Census Table H-5 (All Races), current-dollar column | 1990–2025 |
| `Married_Couple_Median_Income` | Median income of married-couple families, pre-tax | Census Table F-7 (Married-Couple Families), current-dollar column | 1990–2025 |
| `Owner_Median_Income` | Median income of owner-occupied households | Census ACS 1-year, Table B25119 | 2010–2024 (no 2020) |
| `Married_Homeowner_Base_Income` | Income base for the married-homeowner persona: `Owner_Median_Income` where available, otherwise `Married_Couple_Median_Income` | Derived | 1990–2025 |
| `Net_Income_MFJ` | `Married_Homeowner_Base_Income` after federal income tax at that year's married-filing-jointly brackets and standard deduction | Derived; brackets from Tax Foundation / IRS | 1990–2025 |
| `Effective_Tax_Rate_MFJ_Pct` | Federal tax ÷ gross income, MFJ | Derived | 1990–2025 |
| `Net_Income_Single` | `Median_Income` after federal income tax at single-filer brackets | Derived | 1990–2025 |
| `Effective_Tax_Rate_Single_Pct` | Federal tax ÷ gross income, single filer | Derived | 1990–2025 |
| `Renter_Median_Income` | Median income of renter-occupied households | Census ACS 1-year, Table B25119 | 2010–2024 (no 2020) |
| `Renter_Net_Income_Single` | `Renter_Median_Income` after federal income tax, single filer | Derived | 2010–2024 (no 2020) |
| `Min_Wage_Hourly` | Federal minimum wage in effect at year end | U.S. Department of Labor | 1990–2025 |
| `Savings_Rate_Pct` | Personal saving rate (national aggregate, % of disposable income) | FRED `PSAVERT` (BEA) | 1990–2025 |
| `CPI_Index` | CPI-U, annual average (1982–84 = 100) | FRED `CPIAUCNS` (BLS) | 1990–2025 |

## Housing

| Column | Definition | Source | Coverage |
|---|---|---|---|
| `Median_Home_Price` | Median sales price of **new** houses sold | FRED `MSPUS` (Census/HUD) | 1990–2025 |
| `Avg_Home_Price` | Average sales price of new houses sold | FRED `ASPUS` (Census/HUD) | 1990–2025 |
| `Home_Price_Pct_Median_Income` | `Median_Home_Price ÷ Median_Income × 100` (e.g. 475 = 4.75× income) | Derived | 1990–2025 |
| `Home_Price_Pct_Net_Income_MFJ` | `Median_Home_Price ÷ Net_Income_MFJ × 100` | Derived | 1990–2025 |
| `Home_Price_Pct_Net_Income_Single` | `Median_Home_Price ÷ Net_Income_Single × 100` | Derived | 1990–2025 |
| `Mortgage_Rate_30Yr` | Average 30-year fixed mortgage rate, % | Freddie Mac PMMS | 1990–2025 |
| `Est_Mortgage_Payment_Annual` | Annual payment on `Median_Home_Price` with 20% down, 30-year fixed at that year's rate | Derived (standard amortization) | 1990–2025 |
| `Lifetime_Interest` | Total interest over the same 30-year loan | Derived | 1990–2025 |
| `Rent` | Median **asking** rent for vacant units, annualized (monthly × 12) | Census Housing Vacancy Survey, Table 11A | 1990–2025 |
| `Rent_Pct_Median_Income` | `Rent ÷ Median_Income × 100` | Derived | 1990–2025 |
| `Rent_Pct_Net_Income_MFJ` | `Rent ÷ Net_Income_MFJ × 100` | Derived | 1990–2025 |
| `Rent_Pct_Net_Income_Single` | `Rent ÷ Renter_Net_Income_Single × 100` where available (2010–2024, no 2020); otherwise `Rent ÷ Net_Income_Single × 100` | Derived | 1990–2025 |
| `Renter_Rent_Burden_Pct` | Median gross rent as % of household income, renter households (published ratio) | Census ACS 1-year, Table B25071 | 2010–2024 (no 2020) |
| `Renter_Cost_Burdened_Pct` | Share of renter households paying 30%+ of income on rent | Derived from Census ACS Table B25070 | 2010–2024 (no 2020) |
| `Renter_Severely_Burdened_Pct` | Share of renter households paying 50%+ of income on rent | Derived from Census ACS Table B25070 | 2010–2024 (no 2020) |
| `Property_Tax` | Average annual household spending on property tax | BLS Consumer Expenditure Survey (CE), all consumer units | 1990–2024 |
| `Property_Tax_Pct_Net_Income_MFJ` | `Property_Tax` ÷ net mean household income (MFJ) × 100 | Derived | 1990–2024 |
| `Property_Tax_Pct_Net_Income_Single` | `Property_Tax ÷ Net_Income_Single × 100` | Derived | 1990–2024 |

## Household spending

| Column | Definition | Source | Coverage |
|---|---|---|---|
| `Grocery` | Average annual spending on food at home | BLS CE, all consumer units | 1990–2024 |
| `Home_Insurance` | Owned dwellings: maintenance, repairs, insurance, other | BLS CE, all consumer units | 1990–2024 |
| `Auto_Insurance` | Vehicle insurance | BLS CE, all consumer units | 1990–2024 |
| `Health_Insurance` | Health insurance | BLS CE, all consumer units | 1990–2024 |
| `Insurance_Pct_Net_Income_MFJ` | `(Home_Insurance + Auto_Insurance)` ÷ net mean household income (MFJ) × 100 | Derived | 1990–2024 |
| `Insurance_Pct_Net_Income_Single` | `(Home_Insurance + Auto_Insurance) ÷ Net_Income_Single × 100` | Derived | 1990–2024 |
| `Electricity` | Electricity | BLS CE, all consumer units | 1990–2024 |
| `Water` | Water and other public services | BLS CE, all consumer units | 1990–2024 |
| `Phone_Service` | Telephone services | FRED `CXUPHONELB0101M` (BLS CE) | 1990–2024 |
| `Gas_Price_Gal` | Average retail price, regular gasoline, $/gallon | FRED `GASREGW` (EIA) | 1990–2025 |
| `Gas_Spend` | Gasoline, other fuels, and motor oil | BLS CE, all consumer units | 1990–2024 |
| `Gas_Pct_Net_Income_MFJ` | `Gas_Spend` ÷ net mean household income (MFJ) × 100 | Derived | 1990–2024 |
| `Gas_Pct_Net_Income_Single` | `Gas_Spend ÷ Renter_Net_Income_Single × 100` where available; otherwise `÷ Net_Income_Single` | Derived | 1990–2024 |
| `Childcare` | National average annual price of child care (infant and 4-year-old) | Child Care Aware of America | 2022–2025 |
| `Childcare_Pct_Net_Income_MFJ` | `Childcare` ÷ net mean household income (MFJ) × 100 | Derived | 2022–2025 |
| `Childcare_Pct_Net_Income_Single` | `Childcare ÷ Renter_Net_Income_Single × 100` (2022–2024); `÷ Net_Income_Single` (2025) | Derived | 2022–2025 |
| `Public_Tuition_4Yr` | Published tuition and fees, public in-state 4-year college | NCES Digest Table 330.10 (1990–2023); College Board (2024–2025) | 1990–2025 |

## Household-type costs (2024 "What's Left?" sheets)

Taken from the BLS CE "Composition of consumer unit" table for **2022** (the latest year published as a readable table) and **held flat for 2022–2025**, so later years understate actual costs.

| Column | BLS household type | Coverage |
|---|---|---|
| `Grocery_Family`, `Home_Insurance_Family`, `Auto_Insurance_Family`, `Health_Insurance_Family`, `Utilities_Family` | Married couple with children | 2022–2025 |
| `Grocery_Single_Parent`, `Auto_Insurance_Single_Parent`, `Health_Insurance_Single_Parent`, `Utilities_Single_Parent` | One parent, at least one child under 18 | 2022–2025 |
| `Grocery_Pct_Net_Income_MFJ`, `Utilities_Pct_Net_Income_MFJ` | `Grocery_Family` / `Utilities_Family` ÷ `Net_Income_MFJ` × 100 | 2022–2025 |
| `Grocery_Pct_Net_Income_Single`, `Utilities_Pct_Net_Income_Single` | `Grocery_Single_Parent` / `Utilities_Single_Parent` ÷ `Renter_Net_Income_Single` × 100 | 2022–2024 |

## Known limitations

- `Median_Home_Price` covers **new** homes only, not existing-home sales.
- `Rent` is **asking** rent for vacant units, not rent paid by current tenants. `Renter_Rent_Burden_Pct` (ACS) measures rent actually paid.
- Net income is federal income tax only.
- The married-homeowner income base switches sources (ACS owner income for 2010–2024 excluding 2020; Census F-7 married-couple income otherwise), so the `_MFJ` series has visible breaks in 2010, 2020, and 2025. The same applies to renter-based `_Single` columns.
- Net mean household income, the denominator for some `_MFJ` ratios, is derived from Census H-5 mean income and isn't stored as its own column.
- Tuition switches source between 2023 and 2024, which inflates that year's jump.
