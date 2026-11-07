# Sources

Every column's source and coverage is listed in [DATA_DICTIONARY.md](DATA_DICTIONARY.md). Raw downloads are in `data/raw/`.

## Income
- **Census Bureau, Table H-5**, "Median and Mean Household Income by Race and Hispanic Origin of Householder: 1967 to 2025" (CPS ASEC), All Races. Current-dollar and 2025-dollar columns. https://www2.census.gov/programs-surveys/cps/tables/time-series/historical-income-households/h05.xlsx
- **Census Bureau, Table F-7**, "Median and Mean Family Income of All Families by Type of Family: 1947 to 2025," Married-Couple Families. https://www2.census.gov/programs-surveys/cps/tables/time-series/historical-income-families/f07ar.xlsx
- **Census Bureau, American Community Survey 1-year estimates**: Table B25119 (median household income by tenure), Table B25071 (median gross rent as % of income), Table B25070 (gross rent as % of income, distribution). https://data.census.gov
- Cross-check for nominal median income: **FRED `MEHOINUSA646N`**. https://fred.stlouisfed.org/series/MEHOINUSA646N

## Federal income tax
- **Tax Foundation**, "Historical U.S. Federal Individual Income Tax Rates & Brackets." https://taxfoundation.org/data/all/federal/historical-income-tax-rates-brackets/
- **IRS**: Statistics of Income tax rate tables and annual inflation-adjustment releases (standard deductions, cross-checks).

## Housing
- **FRED `MSPUS` / `ASPUS`**: median and average sales price of new houses sold (Census/HUD). https://fred.stlouisfed.org/series/MSPUS
- **Freddie Mac Primary Mortgage Market Survey**, 30-year fixed rate. https://www.freddiemac.com/pmms
- **Census Bureau, Housing Vacancy Survey, Table 11A**: median asking rent. https://www.census.gov/housing/hvs/data/histtab11.xlsx

## Household spending
- **BLS Consumer Expenditure Survey**: all-consumer-unit multi-year tables, annual releases, and "Composition of consumer unit" tables (groceries, insurance, property tax, electricity, water, gasoline). https://www.bls.gov/cex/tables.htm
- **FRED `CXUPHONELB0101M`**: telephone services (BLS CE). https://fred.stlouisfed.org/series/CXUPHONELB0101M
- **FRED `GASREGW`**: regular gasoline price (EIA). https://fred.stlouisfed.org/series/GASREGW
- **Child Care Aware of America**, annual Price of Care reports. https://www.childcareaware.org/price-landscape24/

## Education, wages, savings, prices
- **NCES**, Digest of Education Statistics, Table 330.10 (tuition, 1990–2023). https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp
- **College Board**, Trends in College Pricing (tuition, 2024–2025).
- **U.S. Department of Labor**, history of federal minimum wage rates. https://www.dol.gov/agencies/whd/minimum-wage/history/chart
- **FRED `PSAVERT`**: personal saving rate (BEA). https://fred.stlouisfed.org/series/PSAVERT
- **FRED `CPIAUCNS`**: CPI-U, not seasonally adjusted (BLS). https://fred.stlouisfed.org/series/CPIAUCNS

## Context figures cited on the dashboard
- **HUD**: 30%-of-income cost-burden threshold. https://www.huduser.gov/portal/pdredge/pdr_edge_featd_article_092214.html
- **Harvard Joint Center for Housing Studies**, *America's Rental Housing 2024*.
- **National Association of Realtors**, *2024 Profile of Home Buyers and Sellers*.
