# Data

Research record, predating money_tree/node.py

Historical, bulk, live, and locally committed data sources plus acquisition patterns for the unified `data` concern

Money-tree exposes one generic data interface; the pipe through it is locked, and provider capture is the implementation choice that remains open within that concern

`data(data_config, source): grain`

## Pipe

The pipe is locked

```text
grain(dlt(source))
```

dlt acquires every source and grain shapes every acquisition into model-ready batches

No implementation may skip either stage or substitute another library for it

Sources below are selected for this pipe, not for a choice that is still open

### Grain

[Grain](https://github.com/google/grain) 0.2.18, requiring Python `>=3.11`, is Google's
library for reading and transforming ML training data as chained functional steps

A pipeline is built by composing declarative operations such as `.shuffle()`,
`.map()`, and `.batch()` over a data source

It targets JAX-based workloads but does not require JAX and is used inside
MaxText, Gemma, and other Google projects

Best qualities

- Deterministic, checkpointable iteration order
- Composable functional transform chaining, close to money-tree's own
  `interface(config, value)` shape
- Framework-agnostic despite its JAX origin
- Production-stable release track

Accepted costs

- Younger production surface than Darts or PyTorch Forecasting for
  finance-specific windowing
- No built-in point-in-time or financial-calendar semantics
- Covers loading and batching only, so model definition and fitting stay in the
  models concern

Grain terminates the data pipe; it hands model-native batches to the models
concern and never defines or fits a model

### Live

Tentative

An unbounded source yields grain incrementally as a stream

`live(data_config, source): stream(grain)`

Capture stays outside dlt and hands completed micro-batches back to it, as the
acquisition section describes

Candidate sources are cataloged under live and near-live sources

### Past

Tentative

A bounded window yields grain completely as a batch

`past(data_config, window): batch(grain)`

Candidate sources are cataloged under historical and bulk sources

## Historical and bulk sources

Checked on 2026-07-28

This is a systematic best-effort catalog, not a literal inventory of the internet

It covers credible free sources for offline research and model training

It favors original publishers, regulators, exchanges, and maintained research archives

It excludes products whose useful history is only a live or request-by-request API

Free means that a useful dataset can be obtained without payment

Free access does not imply an open license or a right to redistribute

### Shape-compliant options

#### Recommended foundation

Start with these sources before adding less durable community data

- SEC EDGAR for US filings, fundamentals, holdings, and disclosure text
- GLEIF for legal-entity identity and ownership links
- FRED and ALFRED for macro series and point-in-time vintages
- Government bulk portals for statistics, trade, energy, and weather
- CFTC, FINRA, and SEC market-structure files for positioning and stress signals
- Binance and Kraken public archives for exchange-specific crypto research
- Kenneth French and AQR datasets for factor validation

#### Market prices, returns, positioning, and microstructure

##### Stooq historical database

- URL: [Stooq download](https://stooq.com/db/h/)
- Coverage: Global equities, indices, ETFs, futures, FX, rates, and commodities
- Access: ZIP archives and CSV files grouped by market and interval
- History: Daily and some intraday series, with depth varying by instrument
- Free terms: Free download, but site terms do not grant broad redistribution rights
- Status: **Active**, with opaque adjustment and survivorship methodology
- Best use: Broad exploratory panels and cross-checks, not a security master

##### Nasdaq Data Link free datasets

- URL: [Nasdaq Data Link](https://data.nasdaq.com/search?filters=%5B%22Free%22%5D)
- Coverage: Market, commodity, rates, economic, and publisher-specific datasets
- Access: CSV, JSON, API, and full-dataset downloads where the publisher permits
- History: Dataset-specific, from archival series to daily updates
- Free terms: Account and limits vary, with a separate license for every dataset
- Status: **Active**, but free catalogs and dataset codes can change
- Best use: Discovering documented niche series and reproducible snapshots

##### Binance public market-data archive

- URL: [Binance Public Data](https://data.binance.vision/)
- Coverage: Binance spot, margin, and derivatives symbols
- Access: Daily and monthly ZIP files with checksums
- History: Trades, aggregate trades, klines, and related files by product
- Free terms: No key or fee, but Binance terms govern use and redistribution
- Status: **Active**, with schema notes in the linked GitHub repository
- Best use: High-volume crypto pretraining and exchange-specific backtests

##### Kraken downloadable OHLCVT

- URL: [Kraken OHLCVT downloads](https://support.kraken.com/articles/360047124832)
- Coverage: Kraken currency pairs
- Access: One complete CSV ZIP plus quarterly incremental ZIP files
- History: Market inception onward at 1 to 1,440 minute intervals
- Free terms: Free download, with Kraken terms and market-data rights still applicable
- Status: **Active**, with quarterly archive updates
- Best use: Clean candle baselines and independent crypto validation

##### Dukascopy historical data feed

- URL: [Dukascopy Historical Data](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- Coverage: SWFX FX pairs plus selected commodities, indices, and CFDs
- Access: Browser download in tick or candle formats, commonly CSV and binary
- History: Instrument-specific tick and bar history, often from the early 2000s
- Free terms: Free access, with no clear open redistribution license
- Status: **Active**, but automation uses an undocumented file layout in many clients
- Best use: FX tick research and broker-feed robustness checks

##### HistData

- URL: [HistData downloads](https://www.histdata.com/download-free-forex-data/)
- Coverage: Major and minor FX pairs plus selected metal and index symbols
- Access: Monthly or yearly ZIP files in CSV and platform formats
- History: Tick and one-minute data, with start dates varying by symbol
- Free terms: Free download, with no explicit open-data redistribution grant
- Status: **Caution**, due to limited provenance and quality documentation
- Best use: Low-cost FX prototypes after timestamp and gap validation

##### Cboe historical index data

- URL: [Cboe VIX historical data](https://www.cboe.com/tradable_products/vix/vix_historical_data/)
- Coverage: VIX index, related volatility indices, and selected futures summaries
- Access: CSV and spreadsheet downloads from product pages
- History: Daily VIX values from 1990, with product-specific frequencies elsewhere
- Free terms: Free files, but Cboe website and data-use terms restrict some reuse
- Status: **Active**, with methodology changes documented by Cboe
- Best use: Volatility regimes, stress labels, and benchmark validation

##### CFTC Commitments of Traders

- URL: [CFTC historical compressed files](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)
- Coverage: US futures and options-on-futures positioning by trader category
- Access: Annual compressed text, CSV-compatible, and Excel files
- History: Legacy futures-only reports from 1986, mostly weekly after 1992
- Free terms: US government data, with attribution and source caveats advisable
- Status: **Active**, with weekly releases and historical revisions
- Best use: Crowding, hedger positioning, and medium-horizon regime features

##### FINRA daily short-sale volume

- URL: [FINRA daily short-sale files](https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files)
- Coverage: US exchange-listed and OTC securities reported to FINRA facilities
- Access: Pipe-delimited daily text files by facility and consolidated NMS
- History: Facility-specific, with consolidated NMS files from 2018
- Free terms: Free public files, subject to FINRA terms and interpretation notes
- Status: **Active**, normally posted by 18:00 US Eastern on the trade date
- Best use: Short-activity features, never a proxy for short interest

##### SEC fails-to-deliver

- URL: [SEC fails-to-deliver data](https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data)
- Coverage: Aggregate settlement fails for US equity securities
- Access: Twice-monthly ZIP files containing pipe-delimited text
- History: February 2004 onward, with a coverage rule change in September 2008
- Free terms: Free SEC data, but included CUSIP values have separate rights
- Status: **Active**, published about two weeks after each half-month
- Best use: Settlement stress, crowding, and market-friction features

##### US Treasury interest-rate statistics

- URL: [Treasury interest rate data](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics)
- Coverage: US par yields, real yields, bills, and long-term average rates
- Access: CSV, XML, and queryable table downloads
- History: Daily series, commonly from 1990 or 2003 depending on curve
- Free terms: US government data, with site notices and third-party exceptions
- Status: **Active**, updated on business days
- Best use: Discount curves, duration factors, and risk-free features

##### New York Fed markets data

- URL: [New York Fed markets data](https://www.newyorkfed.org/markets/data-hub)
- Coverage: Reference rates, repo, securities lending, FX, and market operations
- Access: CSV, spreadsheets, and downloadable historical tables
- History: Product-specific daily or operation-level history
- Free terms: Free access, with New York Fed terms and source attribution
- Status: **Active**, maintained alongside official market operations
- Best use: Funding conditions, SOFR history, liquidity, and policy operations

##### Kenneth French Data Library

- URL: [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- Coverage: Equity factors, sorted portfolios, industries, and regional returns
- Access: ZIP-compressed CSV and text files
- History: Monthly, weekly, and daily series, many extending to 1926
- Free terms: Free research downloads, with no blanket redistribution license
- Status: **Active**, with methodology and historical archives
- Best use: Factor targets, sanity checks, and asset-pricing benchmarks

##### AQR Data Library

- URL: [AQR datasets](https://www.aqr.com/Insights/Datasets)
- Coverage: Value, momentum, carry, defensive, trend, and alternative premia
- Access: Excel and browser-selected series downloads
- History: Dataset-specific monthly or daily histories, some near a century
- Free terms: Free research access under AQR site terms and required citations
- Status: **Active**, with recent updates visible on dataset pages
- Best use: Multi-asset factor replication and out-of-sample validation

#### Filings, fundamentals, ownership, and regulated institutions

##### SEC EDGAR archives and bulk APIs

- URL: [SEC EDGAR API and bulk files](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- Coverage: US issuer filings, filing histories, and XBRL company facts
- Access: Filing archives plus nightly `submissions.zip` and `companyfacts.zip`
- History: Filing archives span decades, with structured XBRL mainly from 2009
- Free terms: Free access with a declared user agent and SEC fair-access policy
- Status: **Active**, with bulk ZIP files rebuilt nightly
- Best use: Point-in-time disclosures, text models, and as-filed fundamentals

##### SEC Financial Statement Data Sets

- URL: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets)
- Coverage: Numeric facts from primary statements in XBRL filings
- Access: Quarterly ZIP files with tab-delimited submission, tag, fact, and layout tables
- History: Quarterly files from 2009 onward
- Free terms: Free as-filed data, with filer errors and CUSIP rights caveats
- Status: **Active**, refreshed quarterly under the post-2024 extraction method
- Best use: Compact cross-sectional fundamentals with filing-date controls

##### SEC Financial Statement and Notes Data Sets

- URL: [SEC statement and notes data](https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets)
- Coverage: Primary statements and detailed tagged footnote disclosures
- Access: Large monthly and quarterly ZIP files with normalized text and facts
- History: 2009 onward
- Free terms: Free as-filed data, without a guarantee of filer accuracy
- Status: **Active**, with monthly files for recent periods
- Best use: Rich fundamentals, footnote signals, and accounting-language models

##### SEC Form 13F data sets

- URL: [SEC Form 13F data](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)
- Coverage: Quarterly institutional investment-manager holdings
- Access: Quarterly ZIP files with tab-delimited cover and information tables
- History: Structured quarterly datasets from 2013 onward
- Free terms: Free filing-derived data, with CUSIP redistribution caveats
- Status: **Active**, normally updated quarterly
- Best use: Institutional ownership changes, crowding, and manager features

##### SEC Form N-PORT data sets

- URL: [SEC Form N-PORT data](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)
- Coverage: Registered fund portfolios, risk metrics, and monthly holdings
- Access: Quarterly ZIP files with tab-delimited relational tables
- History: Public structured filings from 2019 onward
- Free terms: Free filing-derived data, with delayed public disclosure
- Status: **Active**, with amended and duplicate filings requiring handling
- Best use: Fund exposures, liquidity, derivatives, and flow-related research

##### Companies House basic company data

- URL: [Companies House free company data](https://download.companieshouse.gov.uk/en_output.html)
- Coverage: Live UK companies, status, address, filing dates, and SIC
- Access: One full or several split monthly CSV ZIP files
- History: Current monthly snapshots rather than a full event history
- Free terms: Free and generally under the UK Crown and OGL framework
- Status: **Active**, updated within five working days of month end
- Best use: UK entity reference data and filing-universe construction

##### Companies House accounts data

- URL: [Companies House accounts bulk data](https://download.companieshouse.gov.uk/en_accountsdata.html)
- Coverage: Electronically filed UK company accounts
- Access: Daily and historical monthly ZIP files containing iXBRL, XBRL, and HTML
- History: Bulk archives from 2013, with recent daily files retained for 60 days
- Free terms: Free and unsupported, with Crown and third-party rights caveats
- Status: **Active**, new files normally Tuesday through Saturday
- Best use: UK as-filed fundamentals and document-model training

##### XBRL International filings index

- URL: [filings.xbrl.org](https://filings.xbrl.org/)
- Coverage: ESEF and other public Inline XBRL reports across many jurisdictions
- Access: Filing packages, JSON index, and generated xBRL-CSV
- History: Primarily European annual reports from the ESEF era
- Free terms: Index software is open, while each filing retains source rights
- Status: **Active**, but jurisdiction discovery remains incomplete
- Best use: Cross-country IFRS facts and multilingual filing models

##### FDIC BankFind bulk data

- URL: [FDIC data downloads](https://www.fdic.gov/bank-data-guide/data-downloads)
- Coverage: US banks, financials, branches, failures, and deposit shares
- Access: CSV, spreadsheet, ZIP, and bulk-generator downloads
- History: Financials from 1992, aggregates from 1984, and structures earlier
- Free terms: US government data, with field-level and site caveats
- Status: **Active**, on weekly, quarterly, and annual schedules
- Best use: Bank fundamentals, distress labels, and regional deposit competition

##### FFIEC Call Reports

- URL: [FFIEC bulk download](https://cdr.ffiec.gov/public/pws/downloadbulkdata.aspx)
- Coverage: US commercial-bank balance sheets, income, assets, and capital
- Access: Quarterly tab-delimited and XBRL bulk files
- History: Broad public bulk coverage from 2001
- Free terms: Free US regulatory data, with a small set of confidential fields absent
- Status: **Active**, initial bulk files arrive about 45 days after quarter end
- Best use: Detailed bank credit, liquidity, asset-quality, and solvency features

##### NCUA quarterly data

- URL: [NCUA quarterly data](https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data)
- Coverage: Federally insured US credit unions and call-report accounts
- Access: Quarterly ZIP and CSV files with account descriptions
- History: Quarterly history from 1994, with schema changes over time
- Free terms: US government data, subject to agency notices
- Status: **Active**, released each quarter
- Best use: Household-credit conditions and community-finance panels

##### Sharadar free sample tier

- URL: [Sharadar data](https://www.sharadar.com/)
- Coverage: US company prices, fundamentals, funds, insiders, and institutions
- Access: Download templates and account-based extracts
- History: Free coverage is narrow, while the paid core exceeds 20 years
- Free terms: The useful free tier is limited to the Dow 30 and sample series
- Status: **Active**, but not a free broad-market foundation
- Best use: Evaluating normalized commercial schemas before buying

#### Macroeconomic, trade, fiscal, and energy data

##### FRED and ALFRED

- URL: [FRED API documentation](https://fred.stlouisfed.org/docs/api/fred/)
- Coverage: US and international macro, rates, credit, markets, and commodities
- Access: CSV and Excel downloads plus bulk release retrieval in API version 2
- History: Series-specific frequencies and depth, with ALFRED vintage dates
- Free terms: Free account and key, but every upstream series keeps its own rights
- Status: **Active**, with current observations and historical revisions
- Best use: Macro features, release calendars, and vintage-safe backtests

##### Federal Reserve Data Download Program

- URL: [Federal Reserve data downloads](https://www.federalreserve.gov/data.htm)
- Coverage: US money, credit, industrial production, banks, rates, and balance sheet
- Access: CSV, XML, and release-specific packages
- History: Daily to annual series, often with long historical depth
- Free terms: Free access, with source notes and Federal Reserve terms
- Status: **Active**, tied to official statistical releases
- Best use: Direct canonical series when FRED provenance is ambiguous

##### FRED-MD and FRED-QD

- URL: [FRED-MD and FRED-QD](https://www.stlouisfed.org/research/economists/mccracken/fred-databases)
- Coverage: Curated monthly and quarterly US macro panels
- Access: Current CSV files and compressed historical vintages
- History: Long panels plus monthly vintages for reproducible forecasting
- Free terms: Public research data, with underlying FRED source rights
- Status: **Active**, updated from FRED
- Best use: Ready-made macro pretraining, nowcasting, and benchmark factors

##### US Bureau of Labor Statistics

- URL: [BLS public data](https://www.bls.gov/data/)
- Coverage: Employment, prices, wages, productivity, occupations, and spending
- Access: Bulk flat files, text, spreadsheets, and series downloads
- History: Dataset-specific monthly, quarterly, and annual histories
- Free terms: US government data, with source attribution requested
- Status: **Active**, following official release calendars
- Best use: Labor, inflation, wage, and recession features

##### US Bureau of Economic Analysis

- URL: [BEA data](https://www.bea.gov/data)
- Coverage: GDP, income, industry, trade, investment, and regional accounts
- Access: CSV, Excel, ZIP, interactive tables, and dataset APIs
- History: Monthly to annual series, with revisions and historical tables
- Free terms: US government data, with BEA citation guidance
- Status: **Active**, tied to official release and revision schedules
- Best use: Growth, profits, input-output, and regional economic features

##### US Census Bureau

- URL: [Census datasets](https://www.census.gov/data/datasets.html)
- Coverage: Population, business, construction, retail, trade, and surveys
- Access: Bulk ZIP, CSV, fixed-width files, and dataset-specific downloads
- History: Survey-specific monthly to decennial histories
- Free terms: US government statistics, with disclosure and geography caveats
- Status: **Active**, across many independently maintained programs
- Best use: Demand, demographics, housing, trade, and regional features

##### US Treasury Fiscal Data

- URL: [Fiscal Data datasets](https://fiscaldata.treasury.gov/datasets/)
- Coverage: Debt, spending, revenue, securities, exchange rates, and auctions
- Access: CSV, JSON, and full-dataset download
- History: Dataset-specific daily, monthly, or annual history
- Free terms: US government data, with documented dataset metadata
- Status: **Active**, with update dates on every dataset
- Best use: Fiscal impulse, issuance, debt structure, and liquidity features

##### US Energy Information Administration

- URL: [EIA data](https://www.eia.gov/opendata/)
- Coverage: Oil, gas, coal, electricity, renewables, prices, and inventories
- Access: CSV, XLSX, ZIP, and API-backed bulk routes by product
- History: Hourly to annual series, with depth varying by survey
- Free terms: US government data, except identified third-party material
- Status: **Active**, with explicit release calendars
- Best use: Energy prices, supply, storage, demand, and weather sensitivity

##### World Bank DataBank and indicators

- URL: [World Bank bulk downloads](https://databank.worldbank.org/)
- Coverage: Development, macro, population, debt, trade, and climate by country
- Access: Full CSV ZIP packages, Excel, and DataBank extracts
- History: Mostly annual series from 1960, with dataset-specific exceptions
- Free terms: Many core datasets use CC BY 4.0, but each dataset must be checked
- Status: **Active**, with source and update metadata
- Best use: Global cross-country panels and structural regime features

##### IMF Data

- URL: [IMF Data](https://data.imf.org/)
- Coverage: Balance of payments, finance, trade, reserves, debt, and forecasts
- Access: Portal downloads, CSV, Excel, and SDMX services
- History: Dataset-specific monthly, quarterly, and annual country histories
- Free terms: Free access, with IMF terms limiting some commercial redistribution
- Status: **Active**, amid migration to the current IMF Data platform
- Best use: International macro, external vulnerability, and sovereign features

##### OECD Data Explorer

- URL: [OECD Data Explorer](https://data-explorer.oecd.org/)
- Coverage: Member and partner country economics, policy, labor, tax, and trade
- Access: CSV, Excel, and SDMX downloads
- History: Dataset-specific monthly to annual histories
- Free terms: OECD reuse terms generally require attribution and preserve notices
- Status: **Active**, replacing older OECD.Stat paths
- Best use: Harmonized developed-market panels and policy comparisons

##### BIS Data Portal

- URL: [BIS Data Portal](https://data.bis.org/)
- Coverage: Banking, credit, property prices, debt, FX, and policy rates
- Access: CSV and SDMX downloads
- History: Long quarterly and monthly country panels, varying by dataset
- Free terms: Free access, with BIS copyright and attribution conditions
- Status: **Active**, maintained by the Bank for International Settlements
- Best use: Credit cycles, cross-border banking, leverage, and housing

##### ECB Data Portal

- URL: [ECB Data Portal](https://data.ecb.europa.eu/)
- Coverage: Euro-area money, banking, rates, markets, payments, and macro data
- Access: CSV, XLSX, and SDMX downloads
- History: Dataset-specific daily to annual histories
- Free terms: ECB statistical reuse is broad with attribution, subject to exceptions
- Status: **Active**, replacing the older Statistical Data Warehouse
- Best use: Euro-area policy, liquidity, bank, and yield-curve features

##### Eurostat

- URL: [Eurostat bulk download](https://ec.europa.eu/eurostat/data/bulkdownload)
- Coverage: EU macro, prices, labor, industry, trade, energy, and regions
- Access: Gzip TSV, SDMX-CSV, JSON, XML, and inventory files
- History: Dataset-specific monthly to annual panels
- Free terms: Reuse is allowed with attribution, except marked third-party data
- Status: **Active**, with database updates twice daily
- Best use: Harmonized EU cross-country and regional forecasting panels

##### UN Comtrade

- URL: [UN Comtrade bulk files](https://comtradeplus.un.org/TradeFlow)
- Coverage: Bilateral merchandise and services trade by commodity and country
- Access: CSV bulk and portal extracts, with account-dependent volume limits
- History: Annual series from 1962 and monthly data for many reporters
- Free terms: Free public use has limits, while mass redistribution needs review
- Status: **Active**, on the Comtrade Plus platform
- Best use: Supply chains, trade exposure, commodity demand, and sanctions effects

##### FAOSTAT

- URL: [FAOSTAT bulk downloads](https://bulks-faostat.fao.org/production/)
- Coverage: Agriculture, food, land, emissions, prices, and commodity balances
- Access: Domain-level CSV ZIP files
- History: Mostly annual country and commodity panels from 1961
- Free terms: FAO data terms and CC BY 4.0 IGO apply to most published data
- Status: **Active**, with domain-specific update dates
- Best use: Agricultural supply, food inflation, and climate exposure

##### UK Office for National Statistics

- URL: [ONS dataset catalog](https://developer.ons.gov.uk/dataset/)
- Coverage: UK macro, prices, labor, trade, population, business, and regions
- Access: CSV, XLSX, and versioned dataset downloads
- History: Dataset-specific monthly to decennial histories
- Free terms: Mostly Open Government Licence with attribution
- Status: **Active**, with release and version metadata
- Best use: Canonical UK macro and regional features

##### Bank of England database

- URL: [Bank of England IADB](https://www.bankofengland.co.uk/boeapps/database/)
- Coverage: UK rates, FX, money, credit, banking, and yield curves
- Access: CSV and spreadsheet selections
- History: Daily to annual series, with some very long histories
- Free terms: Free download, with Bank copyright and source conditions
- Status: **Active**, updated with official series releases
- Best use: UK monetary, funding, and financial-condition features

##### Statistics Canada

- URL: [Statistics Canada bulk download](https://www.statcan.gc.ca/en/developers/wds)
- Coverage: Canadian economy, prices, labor, trade, population, and industry
- Access: Full-table CSV ZIP files and metadata packages
- History: Dataset-specific monthly to decennial histories
- Free terms: Statistics Canada Open Licence permits broad reuse with attribution
- Status: **Active**, with complete table downloads
- Best use: Canadian macro panels and North American cross-checks

##### Australian Bureau of Statistics

- URL: [ABS data downloads](https://www.abs.gov.au/statistics)
- Coverage: Australian macro, labor, prices, trade, population, and business
- Access: CSV, XLSX, and Data Explorer downloads
- History: Dataset-specific monthly to census histories
- Free terms: Mostly CC BY 4.0, with marked third-party exceptions
- Status: **Active**, tied to official release calendars
- Best use: Australian macro, commodities exposure, and Asia-Pacific comparisons

##### JODI oil and gas

- URL: [JODI data](https://www.jodidata.org/oil/)
- Coverage: Country oil and gas production, demand, trade, stocks, and capacity
- Access: CSV and database extracts
- History: Monthly oil from 2002 and gas from 2009 for many countries
- Free terms: Free access, with JODI attribution and terms
- Status: **Active**, with monthly submissions and variable completeness
- Best use: Global physical-energy balances and inventory surprise features

#### Alternative, textual, geospatial, and physical-economy data

##### GDELT

- URL: [GDELT data](https://www.gdeltproject.org/data.html)
- Coverage: Global news events, themes, entities, locations, links, and tone
- Access: Compressed tab-delimited files and BigQuery tables
- History: Events from 1979, with GDELT 2.0 files every 15 minutes from 2015
- Free terms: Free access, but linked article content keeps publisher copyright
- Status: **Active**, though schemas and machine-coded signals need validation
- Best use: News intensity, geopolitical risk, event, and sentiment features

##### Common Crawl

- URL: [Common Crawl data](https://commoncrawl.org/get-started)
- Coverage: Open web pages, metadata, links, and extracted text
- Access: WARC, WAT, and WET files on public object storage
- History: Large periodic crawl snapshots from 2008 onward
- Free terms: Crawl files are free, but page copyrights and privacy rights remain
- Status: **Active**, with frequent new crawl indexes
- Best use: Domain-specific text corpora after legal and quality filtering

##### Wikimedia dumps and pageviews

- URL: [Wikimedia data dumps](https://dumps.wikimedia.org/)
- Coverage: Wikipedia content, revisions, links, Wikidata, and pageview counts
- Access: XML, SQL, JSON, and compressed hourly or monthly files
- History: Content histories vary, with pageviews from 2015 in the current system
- Free terms: CC BY-SA, GFDL, or CC0 varies by project and artifact
- Status: **Active**, with scheduled dumps and occasional failed runs
- Best use: Entity context, attention signals, and knowledge-graph enrichment

##### USPTO bulk data and PatentsView

- URL: [USPTO bulk data](https://developer.uspto.gov/product/bulk-data-storage-system-bdss)
- Coverage: US patents, applications, grants, assignments, and related documents
- Access: XML, text, image archives, and PatentsView research tables
- History: Deep grant history, with product-specific weekly or annual files
- Free terms: US government records, with embedded third-party material caveats
- Status: **Active**, with ongoing portal changes and schema versions
- Best use: Innovation, technology exposure, inventor, and assignee signals

##### USAspending

- URL: [USAspending data downloads](https://www.usaspending.gov/download_center/award_data_archive)
- Coverage: US federal contracts, grants, loans, agencies, and recipients
- Access: Monthly ZIP archives and custom CSV downloads
- History: Broad award history from fiscal year 2008, with older source gaps
- Free terms: US government data, with recipient and source quality caveats
- Status: **Active**, with monthly archived snapshots
- Best use: Government demand, contractor revenue exposure, and policy shocks

##### FEC bulk files

- URL: [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data)
- Coverage: US campaign committees, candidates, receipts, and disbursements
- Access: Cycle-level ZIP files in pipe-delimited text
- History: Coverage varies, with many core files extending to the 1980s
- Free terms: US government disclosure data, with personal-use restrictions by law
- Status: **Active**, updated on published schedules
- Best use: Political exposure, lobbying context, and policy-network research

##### US Senate lobbying disclosures

- URL: [Senate LDA downloads](https://lda.senate.gov/system/public/)
- Coverage: US federal lobbying registrations, reports, clients, and issues
- Access: Search exports and quarterly XML disclosure archives
- History: Electronic records mainly from 1999 onward
- Free terms: Public disclosures, with statutory and privacy constraints
- Status: **Active**, filed and published quarterly
- Best use: Regulatory attention and company-policy exposure

##### Marine Cadastre AIS

- URL: [US vessel traffic data](https://hub.marinecadastre.gov/pages/vesseltraffic)
- Coverage: AIS vessel positions and voyages in US coastal waters
- Access: Large yearly and zone-level CSV ZIP files
- History: National annual coverage from 2009, with changing collection quality
- Free terms: US government data, with navigation and quality disclaimers
- Status: **Active**, with annual historical releases
- Best use: Port activity, commodity flows, congestion, and supply-chain signals

##### US airline on-time performance

- URL: [BTS airline data](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ)
- Coverage: US domestic flights, delays, cancellations, carriers, and airports
- Access: Monthly compressed CSV extracts
- History: Detailed on-time data from 1987
- Free terms: US government data, with carrier-reported quality caveats
- Status: **Active**, released monthly
- Best use: Travel demand, operational stress, weather, and regional activity

##### NOAA climate archives

- URL: [NOAA data access](https://www.ncei.noaa.gov/access)
- Coverage: Global stations, weather observations, climate, storms, and oceans
- Access: Bulk CSV, fixed-width, NetCDF, and object-store files
- History: Dataset-specific hourly to annual observations, some over a century
- Free terms: Most US government data is open, with identified exceptions
- Status: **Active**, with versioned station and climate products
- Best use: Weather exposure, crop, energy demand, transport, and catastrophe signals

##### Copernicus ERA5

- URL: [ERA5 hourly single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)
- Coverage: Global atmospheric, land, and wave variables on a regular grid
- Access: GRIB and NetCDF subsets through the Climate Data Store
- History: Hourly from 1940 to near present, plus monthly aggregates
- Free terms: CC BY 4.0 with registration and attribution
- Status: **Active**, with recent updates and documented revisions
- Best use: Consistent long-run weather and climate features

##### NASA POWER

- URL: [NASA POWER data access](https://power.larc.nasa.gov/data-access-viewer/)
- Coverage: Global solar, meteorological, and agroclimatology variables
- Access: CSV, JSON, NetCDF, and ASCII downloads
- History: Daily and hourly analysis-ready series, mostly from 1981
- Free terms: NASA open-data policy, with citation requested
- Status: **Active**, with documented source-product versions
- Best use: Lightweight site-level weather, solar, and agriculture features

##### USDA Quick Stats

- URL: [USDA NASS Quick Stats](https://quickstats.nass.usda.gov/)
- Coverage: US crops, livestock, prices, acreage, yield, and farm economics
- Access: Bulk text files and account-key extracts
- History: Survey-specific annual, monthly, and weekly histories
- Free terms: US government data, with suppression and survey caveats
- Status: **Active**, following agricultural release schedules
- Best use: Crop supply, food prices, rural conditions, and commodity models

##### USDA WASDE archives

- URL: [WASDE reports](https://www.usda.gov/oce/commodity/wasde)
- Coverage: Global crop and livestock supply, use, trade, stocks, and prices
- Access: Monthly spreadsheets, text, PDF, and historical archive files
- History: Monthly reports with long historical archives
- Free terms: US government data, with report-version and revision caveats
- Status: **Active**, published on a fixed monthly calendar
- Best use: Commodity balance surprises and release-event features

##### ENTSO-E Transparency Platform

- URL: [ENTSO-E Transparency](https://transparency.entsoe.eu/)
- Coverage: European electricity load, generation, outages, flows, and prices
- Access: CSV exports and registered API retrieval for historical ranges
- History: Mostly hourly or finer data from 2015, varying by country
- Free terms: Free registration, with platform terms and source-owner rights
- Status: **Active**, but missing values and country practices vary
- Best use: European power, renewables, weather, and industrial-demand signals

##### NYC taxi trip records

- URL: [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- Coverage: New York taxi and for-hire trips, fares, zones, and timestamps
- Access: Monthly Parquet files plus zone reference data
- History: Yellow taxi records from 2009, with product-specific starts
- Free terms: NYC Open Data terms, with privacy transformations
- Status: **Active**, with schema changes documented by year
- Best use: High-frequency urban activity and mobility benchmark signals

##### OpenSky historical flight data

- URL: [OpenSky data](https://opensky-network.org/data)
- Coverage: Global aircraft state vectors, tracks, and ADS-B messages
- Access: Research database, downloadable samples, and large historical extracts
- History: Network history from 2013, with receiver-dependent coverage
- Free terms: Free for qualifying research, generally noncommercial and account-gated
- Status: **Academic**, with access approval and infrastructure constraints
- Best use: Air-traffic, logistics, tourism, and industrial-activity research

#### Entity, instrument, industry, and geographic reference data

##### GLEIF Golden Copy and delta files

- URL: [GLEIF Golden Copy files](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy)
- Coverage: Global LEIs, legal names, addresses, status, and parent relationships
- Access: Complete and delta files in CSV, JSON, and XML
- History: Current Golden Copy plus issuer historical files and deltas
- Free terms: Open and free to use, with GLEIF license and attribution terms
- Status: **Active**, generated three times daily
- Best use: Canonical entity identity, ownership graphs, and deduplication

##### ISO 10383 Market Identifier Codes

- URL: [ISO MIC list](https://www.iso20022.org/market-identifier-codes)
- Coverage: Exchanges, trading venues, segments, countries, and operating MICs
- Access: Downloadable CSV and Excel lists
- History: Current list plus monthly change files
- Free terms: Free download, but ISO copyright prevents assuming open redistribution
- Status: **Active**, updated monthly by the ISO registration authority
- Best use: Venue normalization and instrument-master validation

##### SEC ticker and exchange mappings

- URL: [SEC company ticker file](https://www.sec.gov/files/company_tickers_exchange.json)
- Coverage: SEC registrant CIK, company name, ticker, and exchange
- Access: JSON files, with separate mutual-fund ticker files
- History: Current snapshots, not a complete symbology event history
- Free terms: Free SEC data, with no guarantee of completeness or stability
- Status: **Active**, but no formal version or archive contract
- Best use: Joining US exchange tickers to EDGAR CIK identifiers

##### Nasdaq Trader symbol directory

- URL: [Nasdaq Trader symbol directory](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
- Coverage: Nasdaq and other listed symbols, ETFs, test issues, and attributes
- Access: Daily pipe-delimited text files over HTTP and FTP
- History: Current daily snapshots, with no official long historical archive
- Free terms: Free reference access, subject to Nasdaq market-data terms
- Status: **Active**, refreshed each trading day
- Best use: Daily US listed universe checks and symbol metadata

##### ESMA FIRDS

- URL: [ESMA Financial Instruments Reference Data](https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_firds)
- Coverage: EU-reportable financial instruments and venue reference attributes
- Access: Daily full and delta XML files, commonly gzip-compressed
- History: MiFID II era from 2018, with daily validity updates
- Free terms: Public regulatory data under EU reuse and portal conditions
- Status: **Active**, but files are large and schemas are complex
- Best use: European ISIN, venue, classification, and trading-status reference

##### Wikidata

- URL: [Wikidata database download](https://www.wikidata.org/wiki/Wikidata:Database_download)
- Coverage: Entities, companies, identifiers, industries, people, and relationships
- Access: Full JSON and RDF dumps plus incremental changes
- History: Current and dated dumps, with revision history in Wikimedia systems
- Free terms: Structured Wikidata statements are CC0
- Status: **Active**, but community edits are not authoritative
- Best use: Entity linking, identifier enrichment, and weak supervision

##### OpenStreetMap planet files

- URL: [OpenStreetMap planet](https://planet.openstreetmap.org/)
- Coverage: Global roads, buildings, land use, amenities, ports, and infrastructure
- Access: Weekly PBF planet files and regional extracts
- History: Current snapshots plus full-history planet files
- Free terms: ODbL attribution, share-alike, and produced-work obligations
- Status: **Active**, with community-dependent completeness
- Best use: Geospatial exposure, logistics networks, and site-level features

##### GeoNames

- URL: [GeoNames export](https://download.geonames.org/export/dump/)
- Coverage: Global places, coordinates, administrative hierarchy, and aliases
- Access: Daily tab-delimited ZIP files
- History: Current snapshots and limited modification files
- Free terms: CC BY 4.0 with attribution
- Status: **Active**, with mixed official and community contributions
- Best use: Fast location resolution and geographic joins

##### FIBO

- URL: [Financial Industry Business Ontology](https://spec.edmcouncil.org/fibo/)
- Coverage: Financial instruments, entities, contracts, markets, and concepts
- Access: RDF, Turtle, OWL, and Git repository releases
- History: Versioned ontology releases rather than observations
- Free terms: MIT license for the ontology repository
- Status: **Active**, governed by the EDM Council
- Best use: Canonical schemas, knowledge graphs, and semantic validation

##### US industry classification files

- URL: [US Census NAICS](https://www.census.gov/naics/)
- Coverage: NAICS industries, descriptions, concordances, and historical versions
- Access: Excel, CSV-compatible tables, PDF, and text
- History: Versioned classifications and crosswalks from 1997 onward
- Free terms: US government data, with source attribution advisable
- Status: **Stable**, revised on a multi-year cycle
- Best use: Time-aware industry normalization and exposure aggregation

#### Research benchmarks and synthetic data

##### Monash Time Series Forecasting Repository

- URL: [Monash Forecasting Repository](https://forecastingdata.org/)
- Coverage: Finance, economics, sales, energy, traffic, weather, and other domains
- Access: Zenodo archives in the `.tsf` format with Python and R loaders
- History: Dataset-specific, with multiple frequencies and trainable panels
- Free terms: Research use is intended, with original rights varying by dataset
- Status: **Academic**, with maintained benchmark results
- Best use: Global forecasting architecture and preprocessing comparisons

##### M4 Competition dataset

- URL: [M4 dataset repository](https://github.com/Mcompetitions/M4-methods/tree/master/Dataset)
- Coverage: 100,000 business, finance, economic, demographic, and other series
- Access: CSV train, test, metadata, and evaluation files
- History: Yearly through hourly series with fixed competition horizons
- Free terms: Free research benchmark, with provenance rights not fully uniform
- Status: **Academic**, frozen after the competition
- Best use: Forecasting accuracy, scale, and frequency-generalization benchmarks

##### FI-2010 limit-order-book dataset

- URL: [FI-2010 dataset record](https://etsin.fairdata.fi/dataset/73eb48d7-4dbc-4a10-a52a-32c3e68856c4)
- Coverage: Ten levels of order-book events for five Finnish equities
- Access: Normalized text matrices and labeled prediction horizons
- History: About ten trading days in June 2010
- Free terms: Research download, with license metadata needing confirmation
- Status: **Academic**, frozen and small by modern standards
- Best use: Reproducing DeepLOB-style classification, not performance claims

##### ABIDES market simulation

- URL: [ABIDES](https://github.com/abides-sim/abides)
- Coverage: Synthetic exchange messages, agents, order books, and market scenarios
- Access: Python simulator outputs and configurable experiment logs
- History: Generated event-time histories with user-controlled scenarios
- Free terms: BSD-3-Clause code, with user-generated datasets inheriting no vendor rights
- Status: **Academic**, with community-maintained forks and successors
- Best use: Stress cases, policy training, and controlled microstructure experiments

##### FinQA

- URL: [FinQA dataset](https://github.com/czyssrs/FinQA)
- Coverage: Questions, tables, text, and reasoning programs from financial reports
- Access: JSON splits and source report links
- History: Static benchmark built from S&P 500 earnings reports
- Free terms: Apache-2.0 repository, while source reports retain their rights
- Status: **Academic**, frozen benchmark
- Best use: Financial table reasoning and document-grounded model evaluation

##### FiQA

- URL: [FiQA dataset](https://sites.google.com/view/fiqa/home)
- Coverage: Financial opinion questions, answers, headlines, posts, and sentiment
- Access: Task files and community mirrors linked from the project
- History: Static 2018 shared-task corpus
- Free terms: Research benchmark, with source-platform content rights unresolved
- Status: **Caution**, due to aging links and third-party text
- Best use: Small sentiment and question-answering baselines

##### Financial PhraseBank

- URL: [Financial PhraseBank](https://huggingface.co/datasets/takala/financial_phrasebank)
- Coverage: English financial-news sentences labeled by expert agreement
- Access: Text classification splits through the dataset card
- History: Static corpus of 4,840 sentences
- Free terms: CC BY-NC-SA 3.0, so commercial use is not granted
- Status: **Academic**, stable but small and frequently overfit
- Best use: Sentiment smoke tests and label-quality experiments

##### TAT-QA

- URL: [TAT-QA](https://github.com/NExTplusplus/TAT-QA)
- Coverage: Questions over financial report tables and surrounding prose
- Access: JSON train, validation, and test data with evaluator code
- History: Static benchmark from public annual reports
- Free terms: MIT repository, with source-document rights retained
- Status: **Academic**, frozen benchmark with active descendants
- Best use: Hybrid table-text reasoning and arithmetic evaluation

##### Jordà-Schularick-Taylor Macrohistory Database

- URL: [Macrohistory Database](https://www.macrohistory.net/database/)
- Coverage: Long-run macro, credit, housing, banking crises, and asset returns
- Access: Excel data and replication files
- History: Annual observations for advanced economies from 1870
- Free terms: Free academic download with citation, not an open redistribution grant
- Status: **Academic**, updated by paper and database releases
- Best use: Rare-crisis labels, secular regimes, and long-horizon validation

### Other

#### Selection rules

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

#### Material gaps in the free ecosystem

There is no confirmed free source for a production-grade global equity master

No free source combines point-in-time constituents, delistings, and corporate actions well

Free consolidated US options history and full-depth order books are not generally available

CUSIP, SEDOL, and many exchange symbology rights are proprietary

Yahoo Finance has no supported bulk-data contract and is intentionally not cataloged

Kaggle and Hugging Face are discovery venues, not provenance or license authorities

Use their copies only after checking the original source and the dataset card

#### Integration and due-diligence checklist

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

#### Sources reviewed but not promoted

- Yahoo Finance lacks a supported public bulk-data contract
- Alpha Vantage, Finnhub, and similar products are primarily request APIs
- Free commercial samples rarely provide a trainable broad-market universe
- Community GitHub mirrors can disappear and often omit original licenses
- Competition datasets can have rules that do not permit general redistribution
- Scraped social media can violate platform terms even when a copy is downloadable

## Live and near-live sources

Systematic best-effort catalog of credible zero-cost live and near-live read APIs

Checked on 2026-07-28 against primary provider documentation

### Shape-compliant options

#### Ranked starting points

| Need | First choice | Why |
| --- | --- | --- |
| US equity prototype | Alpaca IEX | Free RT WebSocket with clear feed identity |
| US consolidated quotes with brokerage | Tradier | RT consolidated equities and options |
| Broad asset prototype | Twelve Data | RT US equities, FX, and crypto on one schema |
| Crypto microstructure | Venue-native WebSockets | Lowest latency and fullest order-book semantics |
| Crypto cross-venue baseline | CoinGecko or CoinMarketCap | Normalized identifiers and one-minute snapshots |
| Filing catalysts | SEC EDGAR APIs plus latest-filings RSS | Official dissemination with measured sub-minute lag |
| Global news factors | GDELT | Broad multilingual NRT coverage with no key |
| US macro factors | Source agency plus FRED | Agency speed with FRED discovery and revision history |
| European macro factors | ECB plus Eurostat | SDMX access and delta-friendly queries |
| Entity normalization | OpenFIGI plus GLEIF | Instrument and legal-entity identifiers |

#### Market and brokerage feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Alpaca Market Data](https://docs.alpaca.markets/docs/about-market-data-api) | US equities, options, crypto, news | REST and WebSocket JSON | RT IEX or D15 SIP on free plan | Key; 200 REST rpm, 1 stream, 30 equity symbols | Market-data agreement applies; display and onward use need entitlement review | Active; best free US equity event feed |
| [Finnhub](https://finnhub.io/pricing) | Stocks, FX, crypto, news, fundamentals | REST and WebSocket JSON | Provider marks free market and news updates RT | Key; 60 REST calls per minute and 50 WS symbols | Free use is limited by provider and exchange terms; no implied resale right | Active; broad prototype feed with generous symbol count |
| [Twelve Data](https://twelvedata.com/pricing) | US equities and ETFs, FX, crypto, reference, press releases | REST and trial WebSocket JSON | RT for listed free markets | Key; 8 credits per minute, 800 per day, 8 trial WS credits | Basic individual plan is personal, internal, and non-commercial | Active 2026; simplest multi-asset normalized schema |
| [Tradier Market Data](https://docs.tradier.com/docs/market-data) | US equities, options, indices, hourly Greeks | HTTPS and streaming JSON | RT consolidated in brokerage API; sandbox is D15 | Bearer token; brokerage account needed for RT; sandbox is free and delayed | Exchange agreements govern display and redistribution | Active; best for options with a Tradier account |
| [OANDA v20](https://developer.oanda.com/rest-live-v20/development-guide/) | FX, metals, and division-specific CFDs | REST JSON and chunked JSON pricing stream | RT tradable quotes; stream is capped at four prices per second per instrument | Practice or live account token; 120 REST rps, 20 streams, 2 new connections per second | Quotes are OANDA prices; terms and regional product rules apply | Mature active service; strong free practice FX stream |
| [London Strategic Edge lse-data](https://github.com/londonstrategicedge/lse-data) | Stocks, FX, crypto, commodities, indices, ETFs | REST and WebSocket JSON | Live and historical, tick-level per the vendor's platform claims | MIT-licensed, self-hosted client; no published rate limits | MIT license covers the client; upstream venue data rights still apply | Active 2026; open-source multi-asset feed from a newly funded startup, unproven at scale |

##### Crypto venue feeds

Public market channels are normally free of API charges

They still inherit venue terms, market-data ownership, sanctions, and geography rules

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Binance Spot](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md) | Spot trades, books, tickers, candles | REST and WebSocket JSON or SBE | RT; stream speeds vary from 100 ms to 1 s | Public channels need no key; 5 inbound messages per second, 1024 streams per connection | Binance terms and regional availability apply; no blanket redistribution grant | Active 2026; deepest retail crypto spot feed in supported regions |
| [Coinbase Advanced Trade](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview) | Spot and supported derivatives, books, trades, candles | REST and WebSocket JSON | RT WebSocket; public REST has a 1 s cache by default | Most market channels need no JWT; channel-specific limits apply | Coinbase market-data terms apply; public access is not a resale license | Active; clean USD and regulated-venue features |
| [Kraken Spot](https://docs.kraken.com/api/docs/websocket-v2/ticker) | Spot books, trades, tickers, OHLC | REST and WebSocket v2 JSON | RT event stream | Public feed needs no key; public REST counters and pair-specific limits apply | Kraken terms apply; derived or displayed products need rights review | Active 2026; reliable sequence-aware spot feed |
| [OKX](https://www.okx.com/docs-v5/en/) | Spot, margin, futures, perpetuals, options | REST and WebSocket JSON | RT; channel push rates are documented per topic | Public channels need no key; 3 connection requests per second and 480 WS ops per hour | OKX terms and regional restrictions apply | Active with 2026 changelog; broad derivatives surface |
| [Bybit v5](https://bybit-exchange.github.io/docs/v5/ws/connect) | Spot, linear and inverse futures, options, spreads | REST and WebSocket JSON | RT; books down to 10 ms and tickers 50 to 100 ms | Public channels need no key; 500 connections per 5 minutes and 1000 market connections per IP | Bybit terms and jurisdiction rules apply | Active 2026; high-rate book and derivatives data |
| [Deribit](https://docs.deribit.com/) | Crypto options, futures, perpetuals, volatility indexes | JSON-RPC over WebSocket or HTTP, plus FIX | RT subscriptions | Public methods need no key; subscribe sustains about 3.3 requests per second with burst 10 | Deribit terms apply; index and market-data reuse needs review | Active 2026; first choice for crypto options surfaces |
| [Bitfinex v2](https://docs.bitfinex.com/docs/ws-public) | Spot and margin tickers, trades, books, candles, status | WebSocket JSON arrays and REST JSON | RT | No key; 20 new public connections per minute; docs conflict at 25 versus 30 subscriptions, so cap at 25 | Bitfinex terms apply; proprietary data cannot be assumed redistributable | Active; useful raw and aggregated order-book modes |
| [Gemini](https://developer.gemini.com/websocket/introduction) | Spot and supported derivatives, books, trades | REST and WebSocket JSON | RT low-latency public stream | Public read needs no key; 120 public REST requests per minute | Market Data Agreement applies; Gemini calls the data proprietary | Production docs updated in 2026; useful regulated spot venue |
| [KuCoin](https://www.kucoin.com/docs-new/websocket-api/base-info/introduction-uta) | Spot, margin, futures, options where available | REST and WebSocket JSON | RT | Pro public WS needs no token; 200 topics per connection and 100 client messages per 10 s | KuCoin terms and region-specific endpoints apply | Active 2026; broad altcoin coverage |
| [Gate API v4](https://www.gate.com/docs/developers/apiv4/ws/en/) | Spot and derivatives books, trades, tickers, candles | REST, WebSocket JSON, and SBE | RT trades; books can push at 100 ms | Public channels need no key; site docs list up to 900 public REST rps and 300 WS connections per IP | Gate terms and local-site restrictions apply | Active with 2026 changelog; useful altcoin and SBE feed |
| [Crypto.com Exchange](https://exchange-developer.crypto.com/exchange/v1) | Spot and derivatives tickers, trades, books, candles | REST and WebSocket JSON | RT | Public market methods need no key; per-method and per-IP limits apply | Exchange terms and geography rules apply | Active; useful secondary centralized venue |
| [Hyperliquid](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket) | On-chain perpetuals and spot, books, trades, mids, candles | REST POST and WebSocket JSON | RT by HyperCore block; book snapshots at least every 500 ms when active | No key for public data; 1200 REST weight per minute, 10 WS connections, 1000 subscriptions | Protocol and interface terms apply; blockchain facts remain independently verifiable | Active 2026; strongest free on-chain order-book stream |
| [dYdX Indexer](https://docs.dydx.xyz/) | dYdX Chain markets, books, trades, candles | REST and WebSocket JSON | RT indexer stream | Public data needs no key; deployment-specific rate limits apply | Open-source code does not waive interface or third-party data terms | Active; decentralized derivatives features |
| [Polymarket CLOB](https://docs.polymarket.com/developers/CLOB/websocket/market-channel) | Prediction-market books, prices, trades, tick sizes | REST and WebSocket JSON | RT market events | Market channel needs no auth; limits are not numerically published | Polymarket terms and regional restrictions apply | Active; event-probability and prediction-market signals |

#### Normalized crypto and on-chain snapshots

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [CoinGecko Demo](https://docs.coingecko.com/docs/setting-up-your-api-key) | Coins, exchanges, market aggregates, metadata | REST JSON | Most market endpoints cache for about 60 s | Demo key; dashboard publishes the current minute and monthly allowance | Demo rights are limited; paid rights differ and redistribution is not implied | Active; strong normalized research baseline |
| [CoinMarketCap Basic](https://coinmarketcap.com/api/pricing/) | Coins, exchanges, rankings, market pairs, selected DEX data | REST JSON | 60 s update frequency on free Basic | Key or restricted keyless endpoint; 15,000 credits monthly and 50 rpm in current pricing | Current Basic pricing says commercial use; standalone resale remains barred | Active 2026; normalized IDs and broad asset metadata |
| [DefiLlama](https://defillama.com/docs/api) | DeFi TVL, protocols, chains, yields, stablecoins, prices | REST JSON | Route-dependent NRT snapshots | Public routes need no key; numeric free limit is not published | Attribute DefiLlama and inspect upstream protocol data rights | Active; best free DeFi state and TVL factors |

#### News and release feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [GDELT 2.0](https://blog.gdeltproject.org/gdelt-3-0-coming-soon/) | Global multilingual news events, entities, tone, links | HTTP files, REST-like DOC and GEO APIs, CSV and JSON | NRT on a 15-minute heartbeat; some v3 products update each minute | No key; no fixed public quota, so cache and throttle | Article copyrights stay with publishers; GDELT metadata is not article ownership | Mature active feed; broad event and sentiment features |
| [Guardian Open Platform](https://open-platform.theguardian.com/access/) | Guardian articles, tags, sections, article text | REST JSON | New content appears after Guardian publication | Developer key; 1 call per second and 500 per day | Free only for non-commercial use; AI, mining, and commercial use need a license | Active; high-quality English news factors |
| [NewsAPI Developer](https://newsapi.org/pricing) | Headlines and article metadata from many publishers | REST JSON | Top headlines live, but article search is delayed 24 h | Key; 100 requests per day | Development and testing only; no staging, production, or full article rights | Active but not a free production feed |
| [SEC latest-filings RSS](https://www.sec.gov/about/rss-feeds) | New EDGAR filings and SEC publications | RSS and Atom XML | Closest free feed to RT filing availability | No key; SEC fair-access maximum is 10 requests per second across sec.gov | Public filings are accessible, but exhibits may retain third-party rights | Active; trigger ingestion before structured XBRL catches up |
| [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm) | Policy statements, speeches, press releases, enforcement | RSS XML | Release-driven | No key; no numeric quota, so conditional GET and polite polling | US government reuse rules apply; linked third-party material may differ | Active; policy-event triggers |
| [ECB RSS](https://www.ecb.europa.eu/home/html/rss.en.html) | Monetary policy, speeches, supervision, press releases | RSS XML | Release-driven | No key; no numeric quota published | ECB copyright and attribution rules apply | Active; euro policy-event triggers |

#### Official macro and regulatory APIs

These feeds are live relative to their publication cadence

They are not tick feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [FRED and ALFRED](https://fred.stlouisfed.org/docs/api/fred/overview.html) | US and global macro series, releases, vintages | REST XML or JSON | Release-driven; aggregator lag varies by source | Free key; exact cap is unpublished and enforced with HTTP 429 | Third-party series can be copyrighted; required FRED notice applies | Active; discovery, revisions, and common macro joins |
| [BLS Public Data](https://www.bls.gov/developers/api_FAQs.htm) | CPI, PPI, payrolls, employment, wages, productivity | REST JSON and XLSX | Release-driven | v1 no key at 25 queries per day; v2 key at 500 per day; both 50 requests per 10 s | US government data is generally reusable with attribution and no endorsement | Active; ingest directly at labor and inflation releases |
| [BEA](https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf) | GDP, income, trade in value added, regional and industry accounts | REST JSON or XML | Release-driven | Free key; adaptive per-minute quota returns 429 and Retry-After | US government reuse rules apply | Active with 2026 guide; national accounts and revisions |
| [Census Data API](https://www.census.gov/data/developers/guidance/api-user-guide.html) | Trade, population, business, housing, surveys | REST JSON | Dataset and release dependent | Key optional for light use; key is required above 500 queries per IP per day | Cite Census; some datasets have their own notes | Active 2026; trade and economic-demographic factors |
| [EIA Open Data v2](https://www.eia.gov/opendata/documentation.php) | Oil, gas, power, coal, renewables, prices, inventories | REST JSON or XML | Constant updates; weekly inventory APIs can lag release by up to 2 h | Free key; stay below about 5 rps and 9000 per hour; 5000 JSON rows per response | Attribution requested; do not falsely represent modified data as EIA | Active v2.1.12 in 2026; energy supply and inventory factors |
| [Treasury Fiscal Data](https://fiscaldata.treasury.gov/api-documentation/) | US debt, auctions, rates, receipts, outlays, securities | REST JSON, CSV, and XML | Dataset and release dependent | No key; no fixed public quota, so paginate and cache | US government reuse rules and dataset notes apply | Active; sovereign funding and fiscal-liquidity features |
| [Federal Reserve Data Download Program](https://www.federalreserve.gov/datadownload/) | Rates, industrial production, money, bank assets, FX | Parameterized HTTP downloads in CSV, XML, or Excel | Release-driven | No key; no numeric quota published | US government reuse rules apply | Active; direct source for selected Fed statistical releases |
| [ECB Data Portal](https://data.ecb.europa.eu/help/api/overview) | Rates, FX, money, credit, markets, balance sheets, macro | SDMX 2.1 REST in XML, JSON, or CSV | Release-driven with `updatedAfter` delta queries | No key; numeric rate cap is not published | ECB copyright, attribution, and no-endorsement rules apply | Active; euro rates and revision-aware ingestion |
| [Eurostat](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction) | EU macro, prices, trade, labor, industry, population | REST SDMX 2.1 or 3.0, JSON-stat, CSV, TSV, XML | Database refreshes at 11:00 and 23:00 CET | No key and free; use async API for large queries | Eurostat reuse policy normally permits reuse with source acknowledgement | Active; broad European panels and trade data |
| [ONS](https://developer.ons.gov.uk/) | UK economy, prices, labor, population, trade | REST JSON and CSV downloads | Release-driven | No key for public data; 120 requests per 10 s and 200 per minute | Open Government Licence applies unless a dataset says otherwise | Active; UK macro at source |
| [OECD Data Explorer](https://www.oecd.org/en/data/insights/data-explainers/2024/11/Api-best-practices-and-recommendations.html) | Cross-country macro, leading indicators, trade, tax, labor | SDMX REST in CSV, JSON, and XML | Mostly release-driven; a few high-frequency indicators | No key; 60 data downloads per hour; VPN traffic is blocked | OECD terms and dataset source rights apply | Active 2026 but rate constrained; normalized country panels |
| [IMF Data API](https://data.imf.org/en/Resource-Pages/IMF-API) | IFS and other IMF macro, financial, fiscal, and external datasets | SDMX 2.1 and 3.0 REST | Release-driven | Free beta portal account currently required for API exploration | IMF terms and dataset-specific source notes apply | Active beta portal; external-sector and cross-country macro |
| [World Bank Indicators](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation) | Development, macro, finance, population, climate indicators | REST JSON or XML | Dataset dependent, usually low frequency | No key; no fixed quota is published | CC BY 4.0 applies to many Bank datasets, with source exceptions | Mature active service; slow-moving structural factors |
| [Bank of England IADB](https://www.bankofengland.co.uk/boeapps/database/Help.asp) | UK rates, SONIA, FX, money, credit, securities, balance sheets | Parameterized HTTP XML, CSV, or HTML | Release or daily cadence | No key; up to 300 series codes per request | Bank terms apply; FX series are explicitly not official market rates | Mature active service; UK rates and lending features |
| [CFTC Public Reporting](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) | Commitments of Traders and other public market reports | Socrata REST, OData, JSON, and CSV | Weekly or report-specific release cadence | No key for normal public calls; Socrata throttles anonymous heavy use | US government reuse rules and report definitions apply | Active 2026; positioning and crowding factors |

#### Filings, fundamentals, and reference data

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [SEC EDGAR data APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Submission history, 10-K and 10-Q facts, 8-K, 20-F, 6-K, frames | REST JSON plus bulk ZIP | Submissions typically under 1 s; XBRL typically under 1 min | No key; identify the client and remain at or below 10 requests per second | Filing access is public; exhibits and third-party content can keep copyright | Active; official live fundamentals and filing events |
| [OpenFIGI v3](https://www.openfigi.com/api/documentation) | FIGI mapping, instrument search, exchange and security metadata | REST JSON | Reference updates rather than market ticks | No key at 25 mappings per minute and 5 searches per minute; free key raises limits | Open Symbology license applies; third-party identifiers are withheld by design | Active v3; normalize instruments before joins |
| [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api) | LEIs, legal entities, parents, children, BIC and ISIN mappings | REST JSON:API | Golden Copy updates and record events | No key; numeric quota is not prominently published | LEI data is open under GLEIF terms with attribution | Active production; issuer and counterparty identity |
| [Companies House](https://developer.company-information.service.gov.uk/) | UK companies, officers, filings, charges, insolvency | REST JSON and streaming API for changed resources | NRT for register changes; filing document timing varies | API key; 600 requests per 5 minutes | Crown and third-party rights vary by field and document | Active; UK company events and issuer reference |

#### Free-looking services that are not free live production feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Massive Stocks Basic](https://massive.com/pricing?product=stocks) | US stocks and reference data | REST JSON and daily files | EOD on free plan; D15 begins on paid Starter | Key; 5 calls per minute on free Stocks Basic | Free plan is individual use; business and redistribution need separate rights | Active; historical bootstrap only |
| [Alpha Vantage](https://www.alphavantage.co/support/) | Stocks, FX, crypto, indicators, news, fundamentals | REST JSON or CSV | Free US stock data is neither RT nor D15; both are premium | Key; 25 requests per day | Provider terms apply and licensed US quote use needs paid entitlement | Active; low-rate research and non-US-stock snapshots |
| [Financial Modeling Prep Basic](https://site.financialmodelingprep.com/pricing-plans) | US profiles, reference, historical data, selected fundamentals | REST JSON | EOD on free Basic | Key; 250 calls per day and 500 MB trailing 30-day bandwidth | Personal use only; display and redistribution require an agreement | Active Stable API; reference and EOD bootstrap |
| [NewsAPI Developer](https://newsapi.org/pricing) | News metadata and headlines | REST JSON | Search articles delayed 24 h; top headlines may be live | Key; 100 requests per day | Development only with no production use | Active; evaluation only |
| [Tradier Sandbox](https://docs.tradier.com/docs/endpoints) | US equities and options plus paper trading | REST and streaming JSON | D15 | Sandbox bearer token | Sandbox and exchange terms apply | Active; integration tests before a brokerage account |
| [OANDA Practice](https://developer.oanda.com/rest-live-v20/development-guide/) | Simulated FX and CFD account with current OANDA quotes | REST and chunked JSON | RT quotes in a non-production account | Free practice account token | Quotes remain subject to OANDA terms | Active; realistic FX pipeline tests |

### Other

#### Scope

`Every` means every credible service found through a category-by-category search

A service qualifies when it has all of these properties

- An official or clearly maintained API
- A non-zero no-cost allowance, demo environment, or public read channel
- Data useful to financial forecasting, risk, or trading
- Documented access that does not depend on scraping a website

Free does not imply real-time, production rights, redistribution rights, or an SLA

Latency labels used below

| Label | Meaning |
| --- | --- |
| `RT` | Event-driven or provider-described real-time data |
| `NRT` | Near-real-time data, normally one minute or less |
| `D15` | At least 15 minutes delayed |
| `release` | Updated around an official scheduled or unscheduled release |
| `EOD` | End-of-day only |
| `trial` | A test surface or restricted symbol set, not a durable live tier |

Limits change often

Read the linked plan, rate-limit, and rights pages before production use

#### Selection rules

1. Prefer the venue-native stream for execution-time features
2. Prefer the issuing agency for scheduled macro releases
3. Add an aggregator for discovery, symbology, and cross-source normalization
4. Record the named feed, not only the vendor
5. Reject any source whose free rights conflict with the intended deployment
6. Treat a trial, sandbox, and free production tier as different products
7. Benchmark observed lag because provider labels are not latency guarantees

#### Live data interface

Every live data implementation should preserve these fields before any tensor conversion

```python:exemplar:live-envelope
{
    "source": "provider-and-feed",
    "instrument": "provider-native-id",
    "event_time": "provider timestamp",
    "received_time": "local monotonic and UTC timestamp",
    "sequence": "provider sequence or null",
    "latency_class": "RT | NRT | D15 | release | EOD | trial",
    "entitlement": "public | key | account | trial",
    "payload": "unaltered provider record",
}
```

Also retain these states

- Snapshot, delta, correction, cancellation, and heartbeat
- Reconnect count and gap detection result
- Provider timezone and trading calendar
- Upstream revision or vintage identifier
- License class and display or redistribution restriction

This makes dlt ingestion idempotent and prevents delayed data from entering an RT feature set

#### Operational cautions

- A WebSocket is transport, not a guarantee of real-time source data
- Free US equities often expose IEX only, D15 SIP, or EOD data
- Crypto feeds need snapshot-plus-delta recovery and sequence-gap handling
- Official macro values can be revised after first release
- News metadata does not grant rights to copy full articles
- Public exchange channels can disappear by jurisdiction without a code change
- Free-plan terms can forbid commercial, shared, display, or model-training use
- No free service in this catalog should be treated as an execution-grade SLA

#### Source maintenance

Review this file at least quarterly

Recheck pricing, limits, market entitlements, geography, and API changelogs before each release

The fastest-changing rows are Alpaca, Finnhub, Twelve Data, crypto venues, and aggregators

## Acquisition and committed datasets

Research checked on 2026-07-28

### Shape-compliant options

#### Decision

[dlt 1.29](https://pypi.org/project/dlt/) is locked as the acquisition stage of the pipe, for reproducible batch and micro-batch ingestion

Land immutable raw data as Parquet and load query-ready tables into DuckDB

Keep WebSocket capture outside dlt and hand completed micro-batches back to dlt

This split keeps acquisition inside one data concern without pretending an ELT library is a tick recorder

#### Fit

| Need | dlt fit | Treatment |
| --- | --- | --- |
| Paginated REST history | Strong | Use the declarative REST source |
| Incremental REST polling | Strong | Persist cursors and merge keys |
| Bulk CSV, JSONL, or Parquet | Strong | Use the filesystem source |
| SQL snapshots or CDC | Strong | Use the SQL source or replication source |
| SDK iterators | Strong | Wrap them as resources |
| WebSocket ticks | Partial | Capture first and yield bounded batches |
| Order-book reconstruction | Weak | Use a dedicated sequenced event log |
| Feature engineering | Wrong layer | Run after raw ingestion |

[Core sources](https://dlthub.com/docs/dlt-ecosystem/verified-sources) cover REST, files, and SQL

#### Source patterns

##### Declarative REST

Use the [REST API source](https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api)
for endpoint trees that share authentication and pagination

Configure these fields per endpoint

- Primary key and merge disposition
- Cursor path and initial value
- Pagination strategy
- Rate-limit backoff
- Response data selector
- Parent-child endpoint binding
- Request timeout and retry budget

Prefer server timestamps over local receipt timestamps for cursors

Retain a small overlap window and deduplicate after every incremental pull

##### Python resource

Use a custom resource for SDKs, signed requests, archives, and unusual pagination

Yield bounded Arrow tables or lists rather than one object at a time

Keep authentication and provider translation inside the provider integration

Keep dlt hints beside the resource so schema and write behavior remain reviewable

##### Live capture bridge

Write WebSocket messages to an append-only local spool before normalization

Rotate by byte size and time rather than by row count alone

Record sequence number, exchange time, receipt time, channel, and connection id

Close a batch atomically and let dlt ingest only closed batches

Never make dlt pipeline state the sole record of an exchange sequence

#### Alternatives

| Option | Strength | Why it is not the default |
| --- | --- | --- |
| Direct Polars and httpx | Small and fast | Rebuilds state, retries, schema, and lineage |
| Airbyte | Large connector catalog | Service footprint is high for this workspace |
| Singer taps | Interchangeable connectors | Quality and state semantics vary by tap |
| Dagster | Strong asset orchestration | Complements ingestion rather than replacing it |
| Prefect | Flexible workflow runtime | Complements ingestion rather than replacing it |
| Kafka or Redpanda | Durable live streams | Operational cost is unjustified before scale |

#### Recommendation

dlt covers historical and polled inputs under the locked pipe

Use DuckDB plus Parquet until data volume or concurrency proves it insufficient

Add a durable stream service only after local spooling fails measured requirements

### Other

#### Recommended layout

```text
provider
  -> capture
  -> dlt resource
  -> raw Parquet
  -> normalized DuckDB tables
  -> point-in-time transforms
  -> grain batches
```

Use one pipeline name per provider, account, environment, and data class

Use one raw table per provider endpoint or event schema

Retain provider payloads before applying a common market schema

##### Local default

| Layer | Default | Reason |
| --- | --- | --- |
| Raw store | Partitioned Parquet | Cheap replay and portable columnar reads |
| Catalog | DuckDB | Local SQL, Parquet scans, and no service dependency |
| Acquisition | dlt | State, retries, schema history, and incremental loading |
| Batch frame | Arrow or Polars | Low-copy handoff into analytics |
| Orchestration | Plain process first | Avoid a scheduler before jobs need one |

The [DuckDB destination](https://dlthub.com/docs/dlt-ecosystem/destinations/duckdb)
supports Parquet, JSONL, and direct connection objects

#### Canonical fields

Every loaded observation should retain these provenance fields where available

| Field | Meaning |
| --- | --- |
| `provider` | Stable provider key |
| `dataset` | Endpoint, feed, or archive key |
| `instrument_id` | Internal point-in-time instrument key |
| `provider_symbol` | Exact upstream symbol |
| `venue` | Listing or execution venue |
| `event_time` | Upstream event time in UTC |
| `available_time` | Earliest time the value was knowable |
| `received_time` | Local receipt time in UTC |
| `sequence` | Upstream sequence or update id |
| `revision` | Provider revision or vintage |
| `ingested_at` | Acquisition timestamp in UTC |
| `payload_hash` | Stable raw-payload fingerprint |

`available_time` is mandatory for macro, fundamentals, news, and revised data

Do not derive it from period end or filing coverage dates

#### State and write rules

| Data behavior | Write disposition | Key |
| --- | --- | --- |
| Immutable trades | Append | Venue plus trade id |
| Mutable bars | Merge | Instrument plus interval plus open time |
| Fundamentals | Append revisions | Entity plus fact plus period plus filing |
| Macro vintages | Append revisions | Series plus observation date plus vintage |
| Reference data | Type-2 history | Provider id plus effective interval |
| News | Append then enrich | Provider article id |
| Full snapshots | Replace staging only | Snapshot id |

Use [schema contracts](https://dlthub.com/docs/general-usage/schema-contracts)
after discovery to stop silent type drift

Allow new nullable fields in raw tables

Require review for removed fields, incompatible types, and key changes

Keep dlt system tables because they provide load and schema lineage

#### Performance

dlt can parallelize extract, normalize, and load stages

The [performance guide](https://dlthub.com/docs/reference/performance) documents
threaded extraction, process normalization, file rotation, and threaded loads

Use these controls in this order

1. Yield larger Arrow or Polars batches
2. Rotate files to expose load parallelism
3. Parallelize independent endpoints
4. Increase normalize workers for nested JSON
5. Increase load workers only when the destination can absorb them
6. Benchmark Parquet against the destination-native default

Do not run the same pipeline name and working directory concurrently

DuckDB serializes some multi-file Parquet loads into one table

Prefer direct Parquet scans when repeated DuckDB ingestion adds no value

#### Reliability controls

- Set explicit connect, read, and total timeouts
- Bound retry time and respect `Retry-After`
- Persist response metadata for quota and cache diagnosis
- Quarantine malformed records rather than dropping them
- Alert on empty successful loads
- Compare expected and observed time coverage
- Reconcile source counts where the provider exposes them
- Check clock skew before live capture
- Encrypt credentials outside pipeline state
- Test restart from every pipeline stage

Schema evolution is automatic by default

Review the [schema evolution behavior](https://dlthub.com/docs/general-usage/schema-evolution)
before accepting upstream changes in curated tables

#### Data interface boundary

A production data implementation should normally read a committed dataset snapshot

It should not perform a remote backfill during a prediction call

The data concern owns acquisition, provenance, normalization, committed snapshots, and
the batching that ends the pipe

The models concern owns feature windows, tensor transforms, and model operations

Expose snapshot identity through observation metadata before enabling live trading

#### Adoption gates

1. Load one daily REST source into Parquet and DuckDB
2. Prove idempotent restart with an overlapping cursor
3. Reproduce a snapshot from raw files alone
4. Detect a deliberately injected schema break
5. Benchmark Arrow batches against row dictionaries
6. Capture and replay one WebSocket channel through the spool bridge
7. Add retention and credential handling before unattended operation
