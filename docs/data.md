# Free historical and bulk data sources

Checked on 2026-07-28

This is a systematic best-effort catalog, not a literal inventory of the internet

It covers credible free sources for offline research and model training

It favors original publishers, regulators, exchanges, and maintained research archives

It excludes products whose useful history is only a live or request-by-request API

Free means that a useful dataset can be obtained without payment

Free access does not imply an open license or a right to redistribute

## Shape-compliant options

### Recommended foundation

Start with these sources before adding less durable community data

- SEC EDGAR for US filings, fundamentals, holdings, and disclosure text
- GLEIF for legal-entity identity and ownership links
- FRED and ALFRED for macro series and point-in-time vintages
- Government bulk portals for statistics, trade, energy, and weather
- CFTC, FINRA, and SEC market-structure files for positioning and stress signals
- Binance and Kraken public archives for exchange-specific crypto research
- Kenneth French and AQR datasets for factor validation

### Market prices, returns, positioning, and microstructure

#### Stooq historical database

- URL: [Stooq download](https://stooq.com/db/h/)
- Coverage: Global equities, indices, ETFs, futures, FX, rates, and commodities
- Access: ZIP archives and CSV files grouped by market and interval
- History: Daily and some intraday series, with depth varying by instrument
- Free terms: Free download, but site terms do not grant broad redistribution rights
- Status: **Active**, with opaque adjustment and survivorship methodology
- Best use: Broad exploratory panels and cross-checks, not a security master

#### Nasdaq Data Link free datasets

- URL: [Nasdaq Data Link](https://data.nasdaq.com/search?filters=%5B%22Free%22%5D)
- Coverage: Market, commodity, rates, economic, and publisher-specific datasets
- Access: CSV, JSON, API, and full-dataset downloads where the publisher permits
- History: Dataset-specific, from archival series to daily updates
- Free terms: Account and limits vary, with a separate license for every dataset
- Status: **Active**, but free catalogs and dataset codes can change
- Best use: Discovering documented niche series and reproducible snapshots

#### Binance public market-data archive

- URL: [Binance Public Data](https://data.binance.vision/)
- Coverage: Binance spot, margin, and derivatives symbols
- Access: Daily and monthly ZIP files with checksums
- History: Trades, aggregate trades, klines, and related files by product
- Free terms: No key or fee, but Binance terms govern use and redistribution
- Status: **Active**, with schema notes in the linked GitHub repository
- Best use: High-volume crypto pretraining and exchange-specific backtests

#### Kraken downloadable OHLCVT

- URL: [Kraken OHLCVT downloads](https://support.kraken.com/articles/360047124832)
- Coverage: Kraken currency pairs
- Access: One complete CSV ZIP plus quarterly incremental ZIP files
- History: Market inception onward at 1 to 1,440 minute intervals
- Free terms: Free download, with Kraken terms and market-data rights still applicable
- Status: **Active**, with quarterly archive updates
- Best use: Clean candle baselines and independent crypto validation

#### Dukascopy historical data feed

- URL: [Dukascopy Historical Data](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- Coverage: SWFX FX pairs plus selected commodities, indices, and CFDs
- Access: Browser download in tick or candle formats, commonly CSV and binary
- History: Instrument-specific tick and bar history, often from the early 2000s
- Free terms: Free access, with no clear open redistribution license
- Status: **Active**, but automation uses an undocumented file layout in many clients
- Best use: FX tick research and broker-feed robustness checks

#### HistData

- URL: [HistData downloads](https://www.histdata.com/download-free-forex-data/)
- Coverage: Major and minor FX pairs plus selected metal and index symbols
- Access: Monthly or yearly ZIP files in CSV and platform formats
- History: Tick and one-minute data, with start dates varying by symbol
- Free terms: Free download, with no explicit open-data redistribution grant
- Status: **Caution**, due to limited provenance and quality documentation
- Best use: Low-cost FX prototypes after timestamp and gap validation

#### Cboe historical index data

- URL: [Cboe VIX historical data](https://www.cboe.com/tradable_products/vix/vix_historical_data/)
- Coverage: VIX index, related volatility indices, and selected futures summaries
- Access: CSV and spreadsheet downloads from product pages
- History: Daily VIX values from 1990, with product-specific frequencies elsewhere
- Free terms: Free files, but Cboe website and data-use terms restrict some reuse
- Status: **Active**, with methodology changes documented by Cboe
- Best use: Volatility regimes, stress labels, and benchmark validation

#### CFTC Commitments of Traders

- URL: [CFTC historical compressed files](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)
- Coverage: US futures and options-on-futures positioning by trader category
- Access: Annual compressed text, CSV-compatible, and Excel files
- History: Legacy futures-only reports from 1986, mostly weekly after 1992
- Free terms: US government data, with attribution and source caveats advisable
- Status: **Active**, with weekly releases and historical revisions
- Best use: Crowding, hedger positioning, and medium-horizon regime features

#### FINRA daily short-sale volume

- URL: [FINRA daily short-sale files](https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files)
- Coverage: US exchange-listed and OTC securities reported to FINRA facilities
- Access: Pipe-delimited daily text files by facility and consolidated NMS
- History: Facility-specific, with consolidated NMS files from 2018
- Free terms: Free public files, subject to FINRA terms and interpretation notes
- Status: **Active**, normally posted by 18:00 US Eastern on the trade date
- Best use: Short-activity features, never a proxy for short interest

#### SEC fails-to-deliver

- URL: [SEC fails-to-deliver data](https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data)
- Coverage: Aggregate settlement fails for US equity securities
- Access: Twice-monthly ZIP files containing pipe-delimited text
- History: February 2004 onward, with a coverage rule change in September 2008
- Free terms: Free SEC data, but included CUSIP values have separate rights
- Status: **Active**, published about two weeks after each half-month
- Best use: Settlement stress, crowding, and market-friction features

#### US Treasury interest-rate statistics

- URL: [Treasury interest rate data](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics)
- Coverage: US par yields, real yields, bills, and long-term average rates
- Access: CSV, XML, and queryable table downloads
- History: Daily series, commonly from 1990 or 2003 depending on curve
- Free terms: US government data, with site notices and third-party exceptions
- Status: **Active**, updated on business days
- Best use: Discount curves, duration factors, and risk-free features

#### New York Fed markets data

- URL: [New York Fed markets data](https://www.newyorkfed.org/markets/data-hub)
- Coverage: Reference rates, repo, securities lending, FX, and market operations
- Access: CSV, spreadsheets, and downloadable historical tables
- History: Product-specific daily or operation-level history
- Free terms: Free access, with New York Fed terms and source attribution
- Status: **Active**, maintained alongside official market operations
- Best use: Funding conditions, SOFR history, liquidity, and policy operations

#### Kenneth French Data Library

- URL: [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- Coverage: Equity factors, sorted portfolios, industries, and regional returns
- Access: ZIP-compressed CSV and text files
- History: Monthly, weekly, and daily series, many extending to 1926
- Free terms: Free research downloads, with no blanket redistribution license
- Status: **Active**, with methodology and historical archives
- Best use: Factor targets, sanity checks, and asset-pricing benchmarks

#### AQR Data Library

- URL: [AQR datasets](https://www.aqr.com/Insights/Datasets)
- Coverage: Value, momentum, carry, defensive, trend, and alternative premia
- Access: Excel and browser-selected series downloads
- History: Dataset-specific monthly or daily histories, some near a century
- Free terms: Free research access under AQR site terms and required citations
- Status: **Active**, with recent updates visible on dataset pages
- Best use: Multi-asset factor replication and out-of-sample validation

### Filings, fundamentals, ownership, and regulated institutions

#### SEC EDGAR archives and bulk APIs

- URL: [SEC EDGAR API and bulk files](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- Coverage: US issuer filings, filing histories, and XBRL company facts
- Access: Filing archives plus nightly `submissions.zip` and `companyfacts.zip`
- History: Filing archives span decades, with structured XBRL mainly from 2009
- Free terms: Free access with a declared user agent and SEC fair-access policy
- Status: **Active**, with bulk ZIP files rebuilt nightly
- Best use: Point-in-time disclosures, text models, and as-filed fundamentals

#### SEC Financial Statement Data Sets

- URL: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets)
- Coverage: Numeric facts from primary statements in XBRL filings
- Access: Quarterly ZIP files with tab-delimited submission, tag, fact, and layout tables
- History: Quarterly files from 2009 onward
- Free terms: Free as-filed data, with filer errors and CUSIP rights caveats
- Status: **Active**, refreshed quarterly under the post-2024 extraction method
- Best use: Compact cross-sectional fundamentals with filing-date controls

#### SEC Financial Statement and Notes Data Sets

- URL: [SEC statement and notes data](https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets)
- Coverage: Primary statements and detailed tagged footnote disclosures
- Access: Large monthly and quarterly ZIP files with normalized text and facts
- History: 2009 onward
- Free terms: Free as-filed data, without a guarantee of filer accuracy
- Status: **Active**, with monthly files for recent periods
- Best use: Rich fundamentals, footnote signals, and accounting-language models

#### SEC Form 13F data sets

- URL: [SEC Form 13F data](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)
- Coverage: Quarterly institutional investment-manager holdings
- Access: Quarterly ZIP files with tab-delimited cover and information tables
- History: Structured quarterly datasets from 2013 onward
- Free terms: Free filing-derived data, with CUSIP redistribution caveats
- Status: **Active**, normally updated quarterly
- Best use: Institutional ownership changes, crowding, and manager features

#### SEC Form N-PORT data sets

- URL: [SEC Form N-PORT data](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)
- Coverage: Registered fund portfolios, risk metrics, and monthly holdings
- Access: Quarterly ZIP files with tab-delimited relational tables
- History: Public structured filings from 2019 onward
- Free terms: Free filing-derived data, with delayed public disclosure
- Status: **Active**, with amended and duplicate filings requiring handling
- Best use: Fund exposures, liquidity, derivatives, and flow-related research

#### Companies House basic company data

- URL: [Companies House free company data](https://download.companieshouse.gov.uk/en_output.html)
- Coverage: Live UK companies, status, address, filing dates, and SIC
- Access: One full or several split monthly CSV ZIP files
- History: Current monthly snapshots rather than a full event history
- Free terms: Free and generally under the UK Crown and OGL framework
- Status: **Active**, updated within five working days of month end
- Best use: UK entity reference data and filing-universe construction

#### Companies House accounts data

- URL: [Companies House accounts bulk data](https://download.companieshouse.gov.uk/en_accountsdata.html)
- Coverage: Electronically filed UK company accounts
- Access: Daily and historical monthly ZIP files containing iXBRL, XBRL, and HTML
- History: Bulk archives from 2013, with recent daily files retained for 60 days
- Free terms: Free and unsupported, with Crown and third-party rights caveats
- Status: **Active**, new files normally Tuesday through Saturday
- Best use: UK as-filed fundamentals and document-model training

#### XBRL International filings index

- URL: [filings.xbrl.org](https://filings.xbrl.org/)
- Coverage: ESEF and other public Inline XBRL reports across many jurisdictions
- Access: Filing packages, JSON index, and generated xBRL-CSV
- History: Primarily European annual reports from the ESEF era
- Free terms: Index software is open, while each filing retains source rights
- Status: **Active**, but jurisdiction discovery remains incomplete
- Best use: Cross-country IFRS facts and multilingual filing models

#### FDIC BankFind bulk data

- URL: [FDIC data downloads](https://www.fdic.gov/bank-data-guide/data-downloads)
- Coverage: US banks, financials, branches, failures, and deposit shares
- Access: CSV, spreadsheet, ZIP, and bulk-generator downloads
- History: Financials from 1992, aggregates from 1984, and structures earlier
- Free terms: US government data, with field-level and site caveats
- Status: **Active**, on weekly, quarterly, and annual schedules
- Best use: Bank fundamentals, distress labels, and regional deposit competition

#### FFIEC Call Reports

- URL: [FFIEC bulk download](https://cdr.ffiec.gov/public/pws/downloadbulkdata.aspx)
- Coverage: US commercial-bank balance sheets, income, assets, and capital
- Access: Quarterly tab-delimited and XBRL bulk files
- History: Broad public bulk coverage from 2001
- Free terms: Free US regulatory data, with a small set of confidential fields absent
- Status: **Active**, initial bulk files arrive about 45 days after quarter end
- Best use: Detailed bank credit, liquidity, asset-quality, and solvency features

#### NCUA quarterly data

- URL: [NCUA quarterly data](https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data)
- Coverage: Federally insured US credit unions and call-report accounts
- Access: Quarterly ZIP and CSV files with account descriptions
- History: Quarterly history from 1994, with schema changes over time
- Free terms: US government data, subject to agency notices
- Status: **Active**, released each quarter
- Best use: Household-credit conditions and community-finance panels

#### Sharadar free sample tier

- URL: [Sharadar data](https://www.sharadar.com/)
- Coverage: US company prices, fundamentals, funds, insiders, and institutions
- Access: Download templates and account-based extracts
- History: Free coverage is narrow, while the paid core exceeds 20 years
- Free terms: The useful free tier is limited to the Dow 30 and sample series
- Status: **Active**, but not a free broad-market foundation
- Best use: Evaluating normalized commercial schemas before buying

### Macroeconomic, trade, fiscal, and energy data

#### FRED and ALFRED

- URL: [FRED API documentation](https://fred.stlouisfed.org/docs/api/fred/)
- Coverage: US and international macro, rates, credit, markets, and commodities
- Access: CSV and Excel downloads plus bulk release retrieval in API version 2
- History: Series-specific frequencies and depth, with ALFRED vintage dates
- Free terms: Free account and key, but every upstream series keeps its own rights
- Status: **Active**, with current observations and historical revisions
- Best use: Macro features, release calendars, and vintage-safe backtests

#### Federal Reserve Data Download Program

- URL: [Federal Reserve data downloads](https://www.federalreserve.gov/data.htm)
- Coverage: US money, credit, industrial production, banks, rates, and balance sheet
- Access: CSV, XML, and release-specific packages
- History: Daily to annual series, often with long historical depth
- Free terms: Free access, with source notes and Federal Reserve terms
- Status: **Active**, tied to official statistical releases
- Best use: Direct canonical series when FRED provenance is ambiguous

#### FRED-MD and FRED-QD

- URL: [FRED-MD and FRED-QD](https://www.stlouisfed.org/research/economists/mccracken/fred-databases)
- Coverage: Curated monthly and quarterly US macro panels
- Access: Current CSV files and compressed historical vintages
- History: Long panels plus monthly vintages for reproducible forecasting
- Free terms: Public research data, with underlying FRED source rights
- Status: **Active**, updated from FRED
- Best use: Ready-made macro pretraining, nowcasting, and benchmark factors

#### US Bureau of Labor Statistics

- URL: [BLS public data](https://www.bls.gov/data/)
- Coverage: Employment, prices, wages, productivity, occupations, and spending
- Access: Bulk flat files, text, spreadsheets, and series downloads
- History: Dataset-specific monthly, quarterly, and annual histories
- Free terms: US government data, with source attribution requested
- Status: **Active**, following official release calendars
- Best use: Labor, inflation, wage, and recession features

#### US Bureau of Economic Analysis

- URL: [BEA data](https://www.bea.gov/data)
- Coverage: GDP, income, industry, trade, investment, and regional accounts
- Access: CSV, Excel, ZIP, interactive tables, and dataset APIs
- History: Monthly to annual series, with revisions and historical tables
- Free terms: US government data, with BEA citation guidance
- Status: **Active**, tied to official release and revision schedules
- Best use: Growth, profits, input-output, and regional economic features

#### US Census Bureau

- URL: [Census datasets](https://www.census.gov/data/datasets.html)
- Coverage: Population, business, construction, retail, trade, and surveys
- Access: Bulk ZIP, CSV, fixed-width files, and dataset-specific downloads
- History: Survey-specific monthly to decennial histories
- Free terms: US government statistics, with disclosure and geography caveats
- Status: **Active**, across many independently maintained programs
- Best use: Demand, demographics, housing, trade, and regional features

#### US Treasury Fiscal Data

- URL: [Fiscal Data datasets](https://fiscaldata.treasury.gov/datasets/)
- Coverage: Debt, spending, revenue, securities, exchange rates, and auctions
- Access: CSV, JSON, and full-dataset download
- History: Dataset-specific daily, monthly, or annual history
- Free terms: US government data, with documented dataset metadata
- Status: **Active**, with update dates on every dataset
- Best use: Fiscal impulse, issuance, debt structure, and liquidity features

#### US Energy Information Administration

- URL: [EIA data](https://www.eia.gov/opendata/)
- Coverage: Oil, gas, coal, electricity, renewables, prices, and inventories
- Access: CSV, XLSX, ZIP, and API-backed bulk routes by product
- History: Hourly to annual series, with depth varying by survey
- Free terms: US government data, except identified third-party material
- Status: **Active**, with explicit release calendars
- Best use: Energy prices, supply, storage, demand, and weather sensitivity

#### World Bank DataBank and indicators

- URL: [World Bank bulk downloads](https://databank.worldbank.org/)
- Coverage: Development, macro, population, debt, trade, and climate by country
- Access: Full CSV ZIP packages, Excel, and DataBank extracts
- History: Mostly annual series from 1960, with dataset-specific exceptions
- Free terms: Many core datasets use CC BY 4.0, but each dataset must be checked
- Status: **Active**, with source and update metadata
- Best use: Global cross-country panels and structural regime features

#### IMF Data

- URL: [IMF Data](https://data.imf.org/)
- Coverage: Balance of payments, finance, trade, reserves, debt, and forecasts
- Access: Portal downloads, CSV, Excel, and SDMX services
- History: Dataset-specific monthly, quarterly, and annual country histories
- Free terms: Free access, with IMF terms limiting some commercial redistribution
- Status: **Active**, amid migration to the current IMF Data platform
- Best use: International macro, external vulnerability, and sovereign features

#### OECD Data Explorer

- URL: [OECD Data Explorer](https://data-explorer.oecd.org/)
- Coverage: Member and partner country economics, policy, labor, tax, and trade
- Access: CSV, Excel, and SDMX downloads
- History: Dataset-specific monthly to annual histories
- Free terms: OECD reuse terms generally require attribution and preserve notices
- Status: **Active**, replacing older OECD.Stat paths
- Best use: Harmonized developed-market panels and policy comparisons

#### BIS Data Portal

- URL: [BIS Data Portal](https://data.bis.org/)
- Coverage: Banking, credit, property prices, debt, FX, and policy rates
- Access: CSV and SDMX downloads
- History: Long quarterly and monthly country panels, varying by dataset
- Free terms: Free access, with BIS copyright and attribution conditions
- Status: **Active**, maintained by the Bank for International Settlements
- Best use: Credit cycles, cross-border banking, leverage, and housing

#### ECB Data Portal

- URL: [ECB Data Portal](https://data.ecb.europa.eu/)
- Coverage: Euro-area money, banking, rates, markets, payments, and macro data
- Access: CSV, XLSX, and SDMX downloads
- History: Dataset-specific daily to annual histories
- Free terms: ECB statistical reuse is broad with attribution, subject to exceptions
- Status: **Active**, replacing the older Statistical Data Warehouse
- Best use: Euro-area policy, liquidity, bank, and yield-curve features

#### Eurostat

- URL: [Eurostat bulk download](https://ec.europa.eu/eurostat/data/bulkdownload)
- Coverage: EU macro, prices, labor, industry, trade, energy, and regions
- Access: Gzip TSV, SDMX-CSV, JSON, XML, and inventory files
- History: Dataset-specific monthly to annual panels
- Free terms: Reuse is allowed with attribution, except marked third-party data
- Status: **Active**, with database updates twice daily
- Best use: Harmonized EU cross-country and regional forecasting panels

#### UN Comtrade

- URL: [UN Comtrade bulk files](https://comtradeplus.un.org/TradeFlow)
- Coverage: Bilateral merchandise and services trade by commodity and country
- Access: CSV bulk and portal extracts, with account-dependent volume limits
- History: Annual series from 1962 and monthly data for many reporters
- Free terms: Free public use has limits, while mass redistribution needs review
- Status: **Active**, on the Comtrade Plus platform
- Best use: Supply chains, trade exposure, commodity demand, and sanctions effects

#### FAOSTAT

- URL: [FAOSTAT bulk downloads](https://bulks-faostat.fao.org/production/)
- Coverage: Agriculture, food, land, emissions, prices, and commodity balances
- Access: Domain-level CSV ZIP files
- History: Mostly annual country and commodity panels from 1961
- Free terms: FAO data terms and CC BY 4.0 IGO apply to most published data
- Status: **Active**, with domain-specific update dates
- Best use: Agricultural supply, food inflation, and climate exposure

#### UK Office for National Statistics

- URL: [ONS dataset catalog](https://developer.ons.gov.uk/dataset/)
- Coverage: UK macro, prices, labor, trade, population, business, and regions
- Access: CSV, XLSX, and versioned dataset downloads
- History: Dataset-specific monthly to decennial histories
- Free terms: Mostly Open Government Licence with attribution
- Status: **Active**, with release and version metadata
- Best use: Canonical UK macro and regional features

#### Bank of England database

- URL: [Bank of England IADB](https://www.bankofengland.co.uk/boeapps/database/)
- Coverage: UK rates, FX, money, credit, banking, and yield curves
- Access: CSV and spreadsheet selections
- History: Daily to annual series, with some very long histories
- Free terms: Free download, with Bank copyright and source conditions
- Status: **Active**, updated with official series releases
- Best use: UK monetary, funding, and financial-condition features

#### Statistics Canada

- URL: [Statistics Canada bulk download](https://www.statcan.gc.ca/en/developers/wds)
- Coverage: Canadian economy, prices, labor, trade, population, and industry
- Access: Full-table CSV ZIP files and metadata packages
- History: Dataset-specific monthly to decennial histories
- Free terms: Statistics Canada Open Licence permits broad reuse with attribution
- Status: **Active**, with complete table downloads
- Best use: Canadian macro panels and North American cross-checks

#### Australian Bureau of Statistics

- URL: [ABS data downloads](https://www.abs.gov.au/statistics)
- Coverage: Australian macro, labor, prices, trade, population, and business
- Access: CSV, XLSX, and Data Explorer downloads
- History: Dataset-specific monthly to census histories
- Free terms: Mostly CC BY 4.0, with marked third-party exceptions
- Status: **Active**, tied to official release calendars
- Best use: Australian macro, commodities exposure, and Asia-Pacific comparisons

#### JODI oil and gas

- URL: [JODI data](https://www.jodidata.org/oil/)
- Coverage: Country oil and gas production, demand, trade, stocks, and capacity
- Access: CSV and database extracts
- History: Monthly oil from 2002 and gas from 2009 for many countries
- Free terms: Free access, with JODI attribution and terms
- Status: **Active**, with monthly submissions and variable completeness
- Best use: Global physical-energy balances and inventory surprise features

### Alternative, textual, geospatial, and physical-economy data

#### GDELT

- URL: [GDELT data](https://www.gdeltproject.org/data.html)
- Coverage: Global news events, themes, entities, locations, links, and tone
- Access: Compressed tab-delimited files and BigQuery tables
- History: Events from 1979, with GDELT 2.0 files every 15 minutes from 2015
- Free terms: Free access, but linked article content keeps publisher copyright
- Status: **Active**, though schemas and machine-coded signals need validation
- Best use: News intensity, geopolitical risk, event, and sentiment features

#### Common Crawl

- URL: [Common Crawl data](https://commoncrawl.org/get-started)
- Coverage: Open web pages, metadata, links, and extracted text
- Access: WARC, WAT, and WET files on public object storage
- History: Large periodic crawl snapshots from 2008 onward
- Free terms: Crawl files are free, but page copyrights and privacy rights remain
- Status: **Active**, with frequent new crawl indexes
- Best use: Domain-specific text corpora after legal and quality filtering

#### Wikimedia dumps and pageviews

- URL: [Wikimedia data dumps](https://dumps.wikimedia.org/)
- Coverage: Wikipedia content, revisions, links, Wikidata, and pageview counts
- Access: XML, SQL, JSON, and compressed hourly or monthly files
- History: Content histories vary, with pageviews from 2015 in the current system
- Free terms: CC BY-SA, GFDL, or CC0 varies by project and artifact
- Status: **Active**, with scheduled dumps and occasional failed runs
- Best use: Entity context, attention signals, and knowledge-graph enrichment

#### USPTO bulk data and PatentsView

- URL: [USPTO bulk data](https://developer.uspto.gov/product/bulk-data-storage-system-bdss)
- Coverage: US patents, applications, grants, assignments, and related documents
- Access: XML, text, image archives, and PatentsView research tables
- History: Deep grant history, with product-specific weekly or annual files
- Free terms: US government records, with embedded third-party material caveats
- Status: **Active**, with ongoing portal changes and schema versions
- Best use: Innovation, technology exposure, inventor, and assignee signals

#### USAspending

- URL: [USAspending data downloads](https://www.usaspending.gov/download_center/award_data_archive)
- Coverage: US federal contracts, grants, loans, agencies, and recipients
- Access: Monthly ZIP archives and custom CSV downloads
- History: Broad award history from fiscal year 2008, with older source gaps
- Free terms: US government data, with recipient and source quality caveats
- Status: **Active**, with monthly archived snapshots
- Best use: Government demand, contractor revenue exposure, and policy shocks

#### FEC bulk files

- URL: [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data)
- Coverage: US campaign committees, candidates, receipts, and disbursements
- Access: Cycle-level ZIP files in pipe-delimited text
- History: Coverage varies, with many core files extending to the 1980s
- Free terms: US government disclosure data, with personal-use restrictions by law
- Status: **Active**, updated on published schedules
- Best use: Political exposure, lobbying context, and policy-network research

#### US Senate lobbying disclosures

- URL: [Senate LDA downloads](https://lda.senate.gov/system/public/)
- Coverage: US federal lobbying registrations, reports, clients, and issues
- Access: Search exports and quarterly XML disclosure archives
- History: Electronic records mainly from 1999 onward
- Free terms: Public disclosures, with statutory and privacy constraints
- Status: **Active**, filed and published quarterly
- Best use: Regulatory attention and company-policy exposure

#### Marine Cadastre AIS

- URL: [US vessel traffic data](https://hub.marinecadastre.gov/pages/vesseltraffic)
- Coverage: AIS vessel positions and voyages in US coastal waters
- Access: Large yearly and zone-level CSV ZIP files
- History: National annual coverage from 2009, with changing collection quality
- Free terms: US government data, with navigation and quality disclaimers
- Status: **Active**, with annual historical releases
- Best use: Port activity, commodity flows, congestion, and supply-chain signals

#### US airline on-time performance

- URL: [BTS airline data](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ)
- Coverage: US domestic flights, delays, cancellations, carriers, and airports
- Access: Monthly compressed CSV extracts
- History: Detailed on-time data from 1987
- Free terms: US government data, with carrier-reported quality caveats
- Status: **Active**, released monthly
- Best use: Travel demand, operational stress, weather, and regional activity

#### NOAA climate archives

- URL: [NOAA data access](https://www.ncei.noaa.gov/access)
- Coverage: Global stations, weather observations, climate, storms, and oceans
- Access: Bulk CSV, fixed-width, NetCDF, and object-store files
- History: Dataset-specific hourly to annual observations, some over a century
- Free terms: Most US government data is open, with identified exceptions
- Status: **Active**, with versioned station and climate products
- Best use: Weather exposure, crop, energy demand, transport, and catastrophe signals

#### Copernicus ERA5

- URL: [ERA5 hourly single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)
- Coverage: Global atmospheric, land, and wave variables on a regular grid
- Access: GRIB and NetCDF subsets through the Climate Data Store
- History: Hourly from 1940 to near present, plus monthly aggregates
- Free terms: CC BY 4.0 with registration and attribution
- Status: **Active**, with recent updates and documented revisions
- Best use: Consistent long-run weather and climate features

#### NASA POWER

- URL: [NASA POWER data access](https://power.larc.nasa.gov/data-access-viewer/)
- Coverage: Global solar, meteorological, and agroclimatology variables
- Access: CSV, JSON, NetCDF, and ASCII downloads
- History: Daily and hourly analysis-ready series, mostly from 1981
- Free terms: NASA open-data policy, with citation requested
- Status: **Active**, with documented source-product versions
- Best use: Lightweight site-level weather, solar, and agriculture features

#### USDA Quick Stats

- URL: [USDA NASS Quick Stats](https://quickstats.nass.usda.gov/)
- Coverage: US crops, livestock, prices, acreage, yield, and farm economics
- Access: Bulk text files and account-key extracts
- History: Survey-specific annual, monthly, and weekly histories
- Free terms: US government data, with suppression and survey caveats
- Status: **Active**, following agricultural release schedules
- Best use: Crop supply, food prices, rural conditions, and commodity models

#### USDA WASDE archives

- URL: [WASDE reports](https://www.usda.gov/oce/commodity/wasde)
- Coverage: Global crop and livestock supply, use, trade, stocks, and prices
- Access: Monthly spreadsheets, text, PDF, and historical archive files
- History: Monthly reports with long historical archives
- Free terms: US government data, with report-version and revision caveats
- Status: **Active**, published on a fixed monthly calendar
- Best use: Commodity balance surprises and release-event features

#### ENTSO-E Transparency Platform

- URL: [ENTSO-E Transparency](https://transparency.entsoe.eu/)
- Coverage: European electricity load, generation, outages, flows, and prices
- Access: CSV exports and registered API retrieval for historical ranges
- History: Mostly hourly or finer data from 2015, varying by country
- Free terms: Free registration, with platform terms and source-owner rights
- Status: **Active**, but missing values and country practices vary
- Best use: European power, renewables, weather, and industrial-demand signals

#### NYC taxi trip records

- URL: [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- Coverage: New York taxi and for-hire trips, fares, zones, and timestamps
- Access: Monthly Parquet files plus zone reference data
- History: Yellow taxi records from 2009, with product-specific starts
- Free terms: NYC Open Data terms, with privacy transformations
- Status: **Active**, with schema changes documented by year
- Best use: High-frequency urban activity and mobility benchmark signals

#### OpenSky historical flight data

- URL: [OpenSky data](https://opensky-network.org/data)
- Coverage: Global aircraft state vectors, tracks, and ADS-B messages
- Access: Research database, downloadable samples, and large historical extracts
- History: Network history from 2013, with receiver-dependent coverage
- Free terms: Free for qualifying research, generally noncommercial and account-gated
- Status: **Academic**, with access approval and infrastructure constraints
- Best use: Air-traffic, logistics, tourism, and industrial-activity research

### Entity, instrument, industry, and geographic reference data

#### GLEIF Golden Copy and delta files

- URL: [GLEIF Golden Copy files](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy)
- Coverage: Global LEIs, legal names, addresses, status, and parent relationships
- Access: Complete and delta files in CSV, JSON, and XML
- History: Current Golden Copy plus issuer historical files and deltas
- Free terms: Open and free to use, with GLEIF license and attribution terms
- Status: **Active**, generated three times daily
- Best use: Canonical entity identity, ownership graphs, and deduplication

#### ISO 10383 Market Identifier Codes

- URL: [ISO MIC list](https://www.iso20022.org/market-identifier-codes)
- Coverage: Exchanges, trading venues, segments, countries, and operating MICs
- Access: Downloadable CSV and Excel lists
- History: Current list plus monthly change files
- Free terms: Free download, but ISO copyright prevents assuming open redistribution
- Status: **Active**, updated monthly by the ISO registration authority
- Best use: Venue normalization and instrument-master validation

#### SEC ticker and exchange mappings

- URL: [SEC company ticker file](https://www.sec.gov/files/company_tickers_exchange.json)
- Coverage: SEC registrant CIK, company name, ticker, and exchange
- Access: JSON files, with separate mutual-fund ticker files
- History: Current snapshots, not a complete symbology event history
- Free terms: Free SEC data, with no guarantee of completeness or stability
- Status: **Active**, but no formal version or archive contract
- Best use: Joining US exchange tickers to EDGAR CIK identifiers

#### Nasdaq Trader symbol directory

- URL: [Nasdaq Trader symbol directory](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
- Coverage: Nasdaq and other listed symbols, ETFs, test issues, and attributes
- Access: Daily pipe-delimited text files over HTTP and FTP
- History: Current daily snapshots, with no official long historical archive
- Free terms: Free reference access, subject to Nasdaq market-data terms
- Status: **Active**, refreshed each trading day
- Best use: Daily US listed universe checks and symbol metadata

#### ESMA FIRDS

- URL: [ESMA Financial Instruments Reference Data](https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_firds)
- Coverage: EU-reportable financial instruments and venue reference attributes
- Access: Daily full and delta XML files, commonly gzip-compressed
- History: MiFID II era from 2018, with daily validity updates
- Free terms: Public regulatory data under EU reuse and portal conditions
- Status: **Active**, but files are large and schemas are complex
- Best use: European ISIN, venue, classification, and trading-status reference

#### Wikidata

- URL: [Wikidata database download](https://www.wikidata.org/wiki/Wikidata:Database_download)
- Coverage: Entities, companies, identifiers, industries, people, and relationships
- Access: Full JSON and RDF dumps plus incremental changes
- History: Current and dated dumps, with revision history in Wikimedia systems
- Free terms: Structured Wikidata statements are CC0
- Status: **Active**, but community edits are not authoritative
- Best use: Entity linking, identifier enrichment, and weak supervision

#### OpenStreetMap planet files

- URL: [OpenStreetMap planet](https://planet.openstreetmap.org/)
- Coverage: Global roads, buildings, land use, amenities, ports, and infrastructure
- Access: Weekly PBF planet files and regional extracts
- History: Current snapshots plus full-history planet files
- Free terms: ODbL attribution, share-alike, and produced-work obligations
- Status: **Active**, with community-dependent completeness
- Best use: Geospatial exposure, logistics networks, and site-level features

#### GeoNames

- URL: [GeoNames export](https://download.geonames.org/export/dump/)
- Coverage: Global places, coordinates, administrative hierarchy, and aliases
- Access: Daily tab-delimited ZIP files
- History: Current snapshots and limited modification files
- Free terms: CC BY 4.0 with attribution
- Status: **Active**, with mixed official and community contributions
- Best use: Fast location resolution and geographic joins

#### FIBO

- URL: [Financial Industry Business Ontology](https://spec.edmcouncil.org/fibo/)
- Coverage: Financial instruments, entities, contracts, markets, and concepts
- Access: RDF, Turtle, OWL, and Git repository releases
- History: Versioned ontology releases rather than observations
- Free terms: MIT license for the ontology repository
- Status: **Active**, governed by the EDM Council
- Best use: Canonical schemas, knowledge graphs, and semantic validation

#### US industry classification files

- URL: [US Census NAICS](https://www.census.gov/naics/)
- Coverage: NAICS industries, descriptions, concordances, and historical versions
- Access: Excel, CSV-compatible tables, PDF, and text
- History: Versioned classifications and crosswalks from 1997 onward
- Free terms: US government data, with source attribution advisable
- Status: **Stable**, revised on a multi-year cycle
- Best use: Time-aware industry normalization and exposure aggregation

### Research benchmarks and synthetic data

#### Monash Time Series Forecasting Repository

- URL: [Monash Forecasting Repository](https://forecastingdata.org/)
- Coverage: Finance, economics, sales, energy, traffic, weather, and other domains
- Access: Zenodo archives in the `.tsf` format with Python and R loaders
- History: Dataset-specific, with multiple frequencies and trainable panels
- Free terms: Research use is intended, with original rights varying by dataset
- Status: **Academic**, with maintained benchmark results
- Best use: Global forecasting architecture and preprocessing comparisons

#### M4 Competition dataset

- URL: [M4 dataset repository](https://github.com/Mcompetitions/M4-methods/tree/master/Dataset)
- Coverage: 100,000 business, finance, economic, demographic, and other series
- Access: CSV train, test, metadata, and evaluation files
- History: Yearly through hourly series with fixed competition horizons
- Free terms: Free research benchmark, with provenance rights not fully uniform
- Status: **Academic**, frozen after the competition
- Best use: Forecasting accuracy, scale, and frequency-generalization benchmarks

#### FI-2010 limit-order-book dataset

- URL: [FI-2010 dataset record](https://etsin.fairdata.fi/dataset/73eb48d7-4dbc-4a10-a52a-32c3e68856c4)
- Coverage: Ten levels of order-book events for five Finnish equities
- Access: Normalized text matrices and labeled prediction horizons
- History: About ten trading days in June 2010
- Free terms: Research download, with license metadata needing confirmation
- Status: **Academic**, frozen and small by modern standards
- Best use: Reproducing DeepLOB-style classification, not performance claims

#### ABIDES market simulation

- URL: [ABIDES](https://github.com/abides-sim/abides)
- Coverage: Synthetic exchange messages, agents, order books, and market scenarios
- Access: Python simulator outputs and configurable experiment logs
- History: Generated event-time histories with user-controlled scenarios
- Free terms: BSD-3-Clause code, with user-generated datasets inheriting no vendor rights
- Status: **Academic**, with community-maintained forks and successors
- Best use: Stress cases, policy training, and controlled microstructure experiments

#### FinQA

- URL: [FinQA dataset](https://github.com/czyssrs/FinQA)
- Coverage: Questions, tables, text, and reasoning programs from financial reports
- Access: JSON splits and source report links
- History: Static benchmark built from S&P 500 earnings reports
- Free terms: Apache-2.0 repository, while source reports retain their rights
- Status: **Academic**, frozen benchmark
- Best use: Financial table reasoning and document-grounded model evaluation

#### FiQA

- URL: [FiQA dataset](https://sites.google.com/view/fiqa/home)
- Coverage: Financial opinion questions, answers, headlines, posts, and sentiment
- Access: Task files and community mirrors linked from the project
- History: Static 2018 shared-task corpus
- Free terms: Research benchmark, with source-platform content rights unresolved
- Status: **Caution**, due to aging links and third-party text
- Best use: Small sentiment and question-answering baselines

#### Financial PhraseBank

- URL: [Financial PhraseBank](https://huggingface.co/datasets/takala/financial_phrasebank)
- Coverage: English financial-news sentences labeled by expert agreement
- Access: Text classification splits through the dataset card
- History: Static corpus of 4,840 sentences
- Free terms: CC BY-NC-SA 3.0, so commercial use is not granted
- Status: **Academic**, stable but small and frequently overfit
- Best use: Sentiment smoke tests and label-quality experiments

#### TAT-QA

- URL: [TAT-QA](https://github.com/NExTplusplus/TAT-QA)
- Coverage: Questions over financial report tables and surrounding prose
- Access: JSON train, validation, and test data with evaluator code
- History: Static benchmark from public annual reports
- Free terms: MIT repository, with source-document rights retained
- Status: **Academic**, frozen benchmark with active descendants
- Best use: Hybrid table-text reasoning and arithmetic evaluation

#### Jordà-Schularick-Taylor Macrohistory Database

- URL: [Macrohistory Database](https://www.macrohistory.net/database/)
- Coverage: Long-run macro, credit, housing, banking crises, and asset returns
- Access: Excel data and replication files
- History: Annual observations for advanced economies from 1870
- Free terms: Free academic download with citation, not an open redistribution grant
- Status: **Academic**, updated by paper and database releases
- Best use: Rare-crisis labels, secular regimes, and long-horizon validation

## Other

### Selection rules

A source is included when it meets all of these tests

- It supplies historical, static, snapshot, or bulk data with financial relevance
- It has an identifiable publisher and usable documentation
- It offers more than a promotional row sample
- Its current access path could be confirmed

The status labels mean

- **Active** — current files or recent official documentation were visible
- **Stable** — maintained by a durable institution, with slower releases expected
- **Academic** — useful for research, but not a production data dependency
- **Caution** — access, licensing, provenance, or maintenance needs extra review

### Material gaps in the free ecosystem

There is no confirmed free source for a production-grade global equity master

No free source combines point-in-time constituents, delistings, and corporate actions well

Free consolidated US options history and full-depth order books are not generally available

CUSIP, SEDOL, and many exchange symbology rights are proprietary

Yahoo Finance has no supported bulk-data contract and is intentionally not cataloged

Kaggle and Hugging Face are discovery venues, not provenance or license authorities

Use their copies only after checking the original source and the dataset card

### Integration and due-diligence checklist

Record these fields for every ingested artifact

- Publisher, landing URL, direct file URL, retrieval time, and checksum
- License version, account terms, allowed purpose, and redistribution rule
- Observation time, publication time, revision time, and ingest time
- Native identifier, identifier type, venue, currency, timezone, and calendar
- Raw schema version, parser version, and all transformations

Apply these controls before a source can train or score a model

- Preserve raw immutable files and file-level metadata
- Separate observation dates from availability dates
- Reconstruct point-in-time universes instead of using current membership
- Detect splits, dividends, symbol changes, mergers, and delistings
- Measure gaps, duplicates, outliers, stale values, and revision behavior
- Compare important fields with a second independent source
- Quarantine sources whose terms do not cover the intended use

### Sources reviewed but not promoted

- Yahoo Finance lacks a supported public bulk-data contract
- Alpha Vantage, Finnhub, and similar products are primarily request APIs
- Free commercial samples rarely provide a trainable broad-market universe
- Community GitHub mirrors can disappear and often omit original licenses
- Competition datasets can have rules that do not permit general redistribution
- Scraped social media can violate platform terms even when a copy is downloadable
