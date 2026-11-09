# Topic 06 spot check: 20 main-set questions and the tables they need

**What to check:** for each question, would a SQL query that answers it need **these** tables (and no fewer)? The gold tables come from Snowflake's parse of the BIRD team's SQL. Mark **You** with ✓ or ✗, and add a note for every ✗.
The key itself is not changed; disagreements go in the README's limitations.

| # | Question | Needs | Gold tables | You | Note |
|---|---|---|---|---|---|
| 1 | [m-037](#m-037) | 1 | `cybermarket_pattern_large.transaction_products` |  |  |
| 2 | [m-038](#m-038) | 1 | `cybermarket_pattern_large.transactions` |  |  |
| 3 | [m-039](#m-039) | 1 | `cybermarket_pattern_large.alerts` |  |  |
| 4 | [m-120](#m-120) | 1 | `polar_equipment_large.communication` |  |  |
| 5 | [m-130](#m-130) | 1 | `polar_equipment_large.operationmaintenance` |  |  |
| 6 | [m-158](#m-158) | 1 | `sports_events_large.constructor_results` |  |  |
| 7 | [m-159](#m-159) | 1 | `sports_events_large.lap_times` |  |  |
| 8 | [m-104](#m-104) | 2 | `mental_healths_large.assessmentbasics`, `mental_healths_large.assessmentsocialanddiagnosis` |  |  |
| 9 | [m-114](#m-114) | 2 | `polar_equipment_large.equipment`, `polar_equipment_large.equipmenttype` |  |  |
| 10 | [m-133](#m-133) | 2 | `polar_equipment_large.equipment`, `polar_equipment_large.equipmenttype` |  |  |
| 11 | [m-143](#m-143) | 2 | `reverse_logistics_large.financial_management`, `reverse_logistics_large.quality_assessment` |  |  |
| 12 | [m-145](#m-145) | 2 | `reverse_logistics_large.financial_management`, `reverse_logistics_large.returns` |  |  |
| 13 | [m-167](#m-167) | 2 | `sports_events_large.constructor_results`, `sports_events_large.constructors` |  |  |
| 14 | [m-171](#m-171) | 2 | `sports_events_large.drivers`, `sports_events_large.lap_times` |  |  |
| 15 | [m-001](#m-001) | 3 | `archeology_scan_large.pointcloud`, `archeology_scan_large.scans`, `archeology_scan_large.sites` |  |  |
| 16 | [m-015](#m-015) | 4 | `cross_border_large.compliance`, `cross_border_large.dataflow`, `cross_border_large.riskmanagement`, `cross_border_large.vendormanagement` |  |  |
| 17 | [m-029](#m-029) | 3 | `cross_border_large.dataflow`, `cross_border_large.dataprofile`, `cross_border_large.riskmanagement` |  |  |
| 18 | [m-056](#m-056) | 3 | `exchange_traded_funds_large.funds`, `exchange_traded_funds_large.performance`, `exchange_traded_funds_large.risk_metrics` |  |  |
| 19 | [m-086](#m-086) | 8 | `fake_account_large.account_clusters`, `fake_account_large.accounts`, `fake_account_large.cluster_analysis`, `fake_account_large.content_activity`, `fake_account_large.interaction_metrics`, `fake_account_large.network_metrics`, `fake_account_large.platforms`, `fake_account_large.risk_and_moderation` |  |  |
| 20 | [m-123](#m-123) | 3 | `polar_equipment_large.communication`, `polar_equipment_large.powerbattery`, `polar_equipment_large.weatherandstructure` |  |  |

---

## m-037

> What's the overall revenue from digital goods? Round the result to 2 decimal places.

```
Table: cybermarket_pattern_large.transaction_products
- EventLink text — Identifier of the transaction that sold the product. PK (composite). FK to transactions(EventCode).
- ProdCat text — Product category for the sold item. PK (composite). FK to products. Possible values: Data, Digital, Physical, Service.
- Subcategory text — Product subcategory for the sold item. PK (composite). FK to products. Possible values: Type_A, Type_B, Type_C, Type_D.
- ListingAge bigint — Age of the listing at the time of sale. PK (composite). FK to products. Example: 155.
- SellerPointer text — Vendor identifier for the sold listing. PK (composite). FK to products.
- PriceAmt real — Price at which the item was sold. Example: 1166.46.
- QtySold bigint — Quantity of items sold in the transaction. Example: 92.
```

---

## m-038

> What's the average distance traveled for shipments with complex routes? Round the result to 2 decimal places.

```
Table: cybermarket_pattern_large.transactions
- EventCode text — Unique identifier for the commercial event (transaction). PK.
- RecordTag text — Secondary unique tag for cross-system correlation. Example: DN541412.
- EventTimestamp timestamp without time zone — Datetime when the transaction event was recorded. Example: 2024/4/2.
- PlatformKey text — Code of the platform where the transaction occurred. FK to markets(PlatCode).
- VendorLink text — Identifier of the vendor involved in the transaction. FK to vendors(SellerKey). Example: V63085.
- AcqLink text — Identifier of the buyer involved in the transaction. FK to buyers(AcqCode). Example: B41538.
- OriginRegion text — Geographical origin region of the shipment. Possible values: Region_A, Region_B, Region_C, Unknown.
- DestRegion text — Destination region of the shipment. Possible values: Region_X, Region_Y, Region_Z, Unknown.
- CrossBorder bigint — Indicates whether the shipment crosses national borders. Possible values: No, Yes.
- RouteComplex text — Complexity classification of the shipping route. Possible values: Complex, Medium, Simple.
- Transaction_Velocity text — text. The rate at which transactions are completed, measured in USD/hour. Example: 45.67 USD/hour.
- Border_cross_border_pre text — text. The premium associated with cross-border transactions, calculated based on payment amount and cross-border flag. Example: 78.04 USD/border-crossing.
- GeoDistScore text — text. The geographical distance involved in the transaction, measured in km. Example: 137.66 USD/border-crossing.
- transaction_financials jsonb — Contains financial details related to the transaction, such as value, fees, escrow usage, and shipping costs.
```

---

## m-039

> How many critical alerts do we have?

```
Table: cybermarket_pattern_large.alerts
- EventTag text — Identifier of the transaction for which the alert was generated. PK. FK to transactions(EventCode). Example: TX4833222.
- ReviewFreq text — Recommended frequency for reviewing the alert or case. Possible values: Daily, Monthly, Weekly.
- NextReviewDt date — Date of the next scheduled review. Example: 2025/3/17.
- AnnotationCount bigint — Number of analyst annotations attached to the alert record. Example: 3.
- alert_case_management jsonb — Stores details about the alert case, including severity level, response time, and actions taken.
```

---

## m-120

> Let's see how much the antenna's condition matters for our comms. Can you group everything by the antenna status—like normal, warning, or error—and tell me the average communication stability for each? Also, show me how many links are in each group. Make sure to only use records where we have all the necessary data, and list the results with the most stable antenna status on top.

```
Table: polar_equipment_large.Communication
- COMM_ID bigint — Unique identifier for the communication record. PK.
- equipRef text — Reference to the equipment. FK to Equipment.EQUIP_CODE.
- loc_link text — Reference to the location. FK to Location.STATION_name.
- GPS_signal text — GPS signal status. **NULL means no GPS signal data recorded.**. Possible values: Medium, Strong, Weak.
- sat_conn_stat text — Satellite connection status. **NULL means no satellite connection status recorded.**. Possible values: Connected, Disconnected, Limited.
- radioSignal_dBm real — Radio signal strength in dBm. Example: -97.8.
- radioFreq_mhz real — Radio frequency in MHz. Example: 731.2.
- antenna_stat text — Antenna status. Possible values: Error, Normal, Warning.
- netLatency_ms real — Network latency in milliseconds. Example: 1006.0.
- dataRate_kbps real — Data rate in kilobits per second. Example: 389.6.
- wifiSignal_dBm real — Wi-Fi signal strength in dBm. **NULL means no Wi-Fi signal data recorded.**. Example: -61.7.
- btStatus text — Bluetooth status. Possible values: Error, Off, On, Pairing.
- opmaint_link bigint — Reference to the operation and maintenance record. FK to OperationMaintenance.OP_MAINT_ID.
```

---

## m-130

> I need to check how ready our equipment is. Can you go through all the maintenance records and calculate the score for its operational readiness for each one? Just show me a list with the record ID, its operating hours, maintenance cycle hours, its current status, and the final readiness score.

```
Table: polar_equipment_large.OperationMaintenance
- OP_MAINT_ID bigint — Unique identifier for operation and maintenance record. PK.
- equipRef text — Reference to the equipment. FK to Equipment.EQUIP_CODE.
- OPER_hours real — Total operational hours of the equipment. Example: 17843.
- maintCycleHrs real — Maintenance cycle hours. **NULL means no maintenance cycle defined.**. Example: 2047.0.
- LAST_maint_date date — Date of the last maintenance. **NULL means no maintenance date provided.**. Example: 25-Feb-24.
- NEXT_due_date date — Date of the next scheduled maintenance. **NULL means no next maintenance date provided.**. Example: 2025/11/16.
- OPER_status text — Operational status of the equipment. Possible values: Active, Maintenance, Repair, Standby, Storage.
- MAINT_COST_usd real — Maintenance cost in USD. Example: 7632.51.
- repairCostUsd real — Repair cost in USD. Example: 3297.13.
- operating_cost_usd real — Operating cost in USD. **NULL means no operating cost recorded.**. Example: 338.79.
- crewCertStatus text — Certification status of the crew. Possible values: Expired, Pending, Valid.
- inspect_status text — Inspection status of the equipment. Possible values: Failed, Passed, Pending.
- COMPLIANCE_state text — Compliance state of the equipment. **NULL means no compliance state recorded.**. Possible values: Compliant, Non-compliant, Review.
- docu_status text — Documentation status for the equipment. Possible values: Complete, Incomplete, Updated.
- comm_link bigint — Optional reference to communication link.
```

---

## m-158

> Which constructor has the best track record for finishing races? Calculate the reliability rate among all constructors who have participated in at least 5 races, which shows the races finished out of races started, and return the highest reliability percentage, rounded to two decimal places.

```
Table: sports_events_large.constructor_results
- cresref integer — Unique result reference. PK. Example: 15178.
- matchref integer — Foreign key to the races table (RAK_ID). FK to races. Example: 943.
- unitnode integer — Foreign key to the constructors table (CSTR_Key). FK to constructors. Example: 9.
- scoreval real — Points scored by constructor in the race. **NULL means the constructor was unclassified or data are missing.**. Example: 22.0.
- st_mark text — Status mark for the result. Possible values: D, \N.
```

---

## m-159

> Find drivers with at least 10 laps recorded, and identify the highest stability of a driver's lap times during a race. Give me the top score rounded to two decimals.

```
Table: sports_events_large.lap_times
- rc_index integer — Foreign key to the races table (RAK_ID). FK to races. Example: 1093.
- wheel_unit integer — Foreign key to the drivers table (DRV_MAIN). FK to drivers. Example: 4.
- lapval integer — Lap value in the race. Example: 55.
- pp integer — Position for the lap. Example: 7.
- tmdesc text — Recorded lap-time string. **NULL means the lap time was not captured or is invalid.**. Example: 1:43.848.
- msec_val integer — Lap time in milliseconds. Example: 103848.
```

---

## m-104

> I'm trying to decide where to focus our new goal-setting program. I have a hunch that our PTSD patients are struggling more to make progress than our anxiety patients. Can you check this for me? I want to see a comparison: on average, how many recovery goals would a PTSD patient achieve in a full year versus an anxiety patient? I just need those two numbers side-by-side to see if my hunch is right.

```
Table: mental_healths_large.assessmentbasics
- ab_key text — A TEXT primary key uniquely identifying each assessment record in the mental health database.
- a_type text — Type of mental health assessment conducted. Contains values: 'Initial', 'Emergency', 'Routine', 'Follow-up'.
- a_method text — Method used to conduct the assessment. Contains values: 'Phone', 'Self-report', 'In-person', 'Telehealth'.
- a_dur_min bigint — Duration of the assessment session in minutes.
- a_lang text — Primary language used during the assessment. Contains values: 'Chinese', 'French', 'English', 'Spanish'.
- a_valid text — Validity rating of the assessment results. Contains values: 'Questionable', 'Invalid', 'Valid'.
- resp_consist text — Consistency of patient responses throughout the assessment. Contains values: 'Medium', 'High', 'Low'. Contains NULL when response consistency is not evaluated.
- sympt_valid text — Validity of reported symptoms during the assessment. Contains values: 'Questionable', 'Valid', 'Invalid'.
- pat_owner_ref text — Foreign key referencing Patients(Pat_Key), linking the assessment to the specific patient.
- depr_improve_rate text — The rate at which depression symptoms improve, calculated as the reduction in PHQ-9 score per month of therapy. Example: 1.2 points/month.
- therapy_exp_intensity text — The total hours spent on therapy per month, based on the frequency and duration of therapy sessions. Example: 8 hours/month.
- med_side_eff_density text — The density of side effects experienced from medications, calculated as the severity of side effects per medication per month. Example: 0.03 side-effects/med/month.
- crisis_event_rate text — The rate at which crisis events occur, calculated as the total number of crisis interventions and emergency contacts per month. Example: 0.2 events/month.
- func_recovery_eff text — The efficiency of functional recovery, calculated as the total Quality of Life score per month of therapy. Example: 4.5 QoL-points/month.
- adherence_index text — A measure of treatment adherence, calculated as the adherence score per therapy appointment. Example: 0.75 adherence-score/appointment.
- sympt_fluct_index text — A measure of the fluctuation in symptoms (PHQ-9, GAD7, Mood scores), calculated as the average fluctuation per assessment. Example: 3.2 fluctuation-points/assessment.
- hosp_risk_density text — The risk of hospitalization, calculated as the total number of hospitalizations per year based on previous hospitalizations and diagnosis duration. Example: 1.5 risk-score/year.
- med_change_freq text — The frequency of medication changes, calculated as the number of changes in medication type or dosage per month. Example: 0.1 changes/month.
- support_util_rate text — The rate of social support utilization, calculated as the level of support used per emergency contact. Example: 2.0 support-level/contact.
- treatment_cost_eff text — The cost-efficiency of treatment, calculated as the Quality of Life score per dollar spent on treatment. Example: 0.15 QoL-points/$.
- recovery_goal_vel text — The speed at which recovery goals are achieved, calculated as the number of goals achieved per month of therapy. Example: 0.5 goals/month.
```

```
Table: mental_healths_large.assessmentsocialanddiagnosis
- asd_key text — A TEXT primary key uniquely identifying each social and diagnosis assessment record, linking to AssessmentBasics(AB_Key).
- rec_status text — Patient's recovery status and stage in treatment. Contains values: 'Relapse', 'Stable', 'Advanced', 'Early'.
- prim_dx text — Patient's primary mental health diagnosis. Contains values: 'Anxiety', 'PTSD', 'Bipolar', 'Schizophrenia', 'Depression'.
- sec_dx text — Patient's secondary or comorbid mental health diagnosis. Contains values: 'OCD', 'Personality Disorder', 'Substance Use', 'Eating Disorder'. Contains NULL when secondary diagnosis is not applicable.
- dx_dur_m bigint — Duration of the primary diagnosis in months since initial onset or first diagnosis.
- prev_hosp bigint — Number of previous psychiatric hospitalizations or inpatient admissions for mental health treatment.
- last_hosp_dt text — Date of the patient's last psychiatric hospitalization, stored as text with format yyyy/mm/dd like '2024/12/13', '2023/11/09', '2025/02/13' due to noise modifications.
- qol_scr bigint — Quality of Life score typically ranging from 1 to 100.
- func_imp text — Functional impairment assessment. Contains values: 'SEVERE', 'MODERATE', 'severe', 'moderate', 'mild', 'Severe', 'Moderate', 'Mild'. Contains noise with mixed case variations like 'SeVerE', 'MODErate', 'SEVErE', 'mIld', 'MILD'. Contains NULL when functional impairment is not assessed.
- funcassess jsonb — Groups functional assessment metrics including work functioning, social functioning, ADL functioning, stress levels, coping skills, resilience, insight, and motivation into a comprehensive functional profile.
```

---

## m-114

> Let's compare how efficient our equipment is versus how safe it is. Can you show me a list with the equipment type, its code, its efficiency score, and its safety score? Then, for each equipment type, rank them by efficiency and by safety. I also want to see how big the gap is between those two ranks. Sort everything by type, and then by the best efficiency score.

```
Table: polar_equipment_large.Equipment
- EQUIP_CODE text — Unique identifier for the equipment. PK. Example: PE593707.
- EquipType text — Reference to the equipment type. FK to EquipmentType.EquipType.
- model_name text — Model name of the equipment. **NULL means no model name provided.**. Example: Model-925.
- MakerName text — Name of the equipment manufacturer. **NULL means no manufacturer provided.**. Example: Lee, Meyers and Hamilton.
- SERVICE_YRS bigint — Number of years the equipment has been in service. Example: 4.
- utilPercent real — Utilization percentage of the equipment. Example: 53.
- RELIAB_IDX real — Reliability index of the equipment. Example: 97.8.
```

```
Table: polar_equipment_large.EquipmentType
- EquipType text — Unique identifier for the equipment type. PK.
- type_indices jsonb — Bundles the various performance-, efficiency-, safety- and sustainability-related indices that characterise an equipment family.
```

---

## m-133

> I need a list of our safest and best-performing equipment. Can you find all the gear with a top-tier performance index of overall safety-say, anything over 0.75? For each item on the list, show me its equipment code, its calculated efficiency rating, and the final safety/performance score.

```
Table: polar_equipment_large.Equipment
- EQUIP_CODE text — Unique identifier for the equipment. PK. Example: PE593707.
- EquipType text — Reference to the equipment type. FK to EquipmentType.EquipType.
- model_name text — Model name of the equipment. **NULL means no model name provided.**. Example: Model-925.
- MakerName text — Name of the equipment manufacturer. **NULL means no manufacturer provided.**. Example: Lee, Meyers and Hamilton.
- SERVICE_YRS bigint — Number of years the equipment has been in service. Example: 4.
- utilPercent real — Utilization percentage of the equipment. Example: 53.
- RELIAB_IDX real — Reliability index of the equipment. Example: 97.8.
```

```
Table: polar_equipment_large.EquipmentType
- EquipType text — Unique identifier for the equipment type. PK.
- type_indices jsonb — Bundles the various performance-, efficiency-, safety- and sustainability-related indices that characterise an equipment family.
```

---

## m-143

> How dirty and pricey is it to scrap items in different states? how me the average values, rounded to two decimals.

```
Table: reverse_logistics_large.financial_management
- creditref text — Unique identifier for the financial record. PK. Example: CM78914.
- casetag character varying — Foreign key to the returns table (CaseNum). FK to returns.
- dispcost real — Disposal cost for the return item. Example: $86.84.
- cost_breakdown jsonb — Captures the financial breakdown of refund, recovery, and sustainability-related fees for a return case.
```

```
Table: reverse_logistics_large.quality_assessment
- inspectref character varying — Foreign key to the returns table (CaseNum). PK, FK to returns.
- assessment_summary jsonb — Summarizes quality inspection, usage, and documentation state for a returned product.
```

---

## m-145

> Tell me the overall gain or loss from all returns: take what we got back after processing and subtract the combined out-of-pocket amount (transport, getting it sellable again, label fixes, end-of-life handling, fix-up quote). Include the net figure and both parts, rounded to two decimals.

```
Table: reverse_logistics_large.financial_management
- creditref text — Unique identifier for the financial record. PK. Example: CM78914.
- casetag character varying — Foreign key to the returns table (CaseNum). FK to returns.
- dispcost real — Disposal cost for the return item. Example: $86.84.
- cost_breakdown jsonb — Captures the financial breakdown of refund, recovery, and sustainability-related fees for a return case.
```

```
Table: reverse_logistics_large.returns
- casenum character varying — Unique identifier for the return case. PK. Example: RL924605.
- logtime character varying — Timestamp when the return was logged. Example: 2024/11/04.
- srctxn character varying — Foreign key to the orders table (TxnNum). FK to orders. Example: ORD89293.
- itemlink character varying — Foreign key to the products table (ItemCode). FK to products. Example: PRD00023.
- revdate text — Date when the return was processed. Example: 2025-01-20.
- dayslapsed bigint — Number of days lapsed since the transaction. Example: 33.
- return_channel character varying — Channel through which the return was made.
- return_details jsonb — Groups together metadata about the return reason, authorization, and shipping logistics.
```

---

## m-167

> To analyze team performance, can you calculate the rate of constructor reliability for each team? I need to see the team names, their total races started, total races finished, the reliability rate as a percentage, and give them a reliability rank. Only include constructors with significant participation so we get meaningful data, and sort them from most reliable to least reliable.

```
Table: sports_events_large.constructor_results
- cresref integer — Unique result reference. PK. Example: 15178.
- matchref integer — Foreign key to the races table (RAK_ID). FK to races. Example: 943.
- unitnode integer — Foreign key to the constructors table (CSTR_Key). FK to constructors. Example: 9.
- scoreval real — Points scored by constructor in the race. **NULL means the constructor was unclassified or data are missing.**. Example: 22.0.
- st_mark text — Status mark for the result. Possible values: D, \N.
```

```
Table: sports_events_large.constructors
- cstr_key integer — Unique identifier for the constructor. PK. Example: 1.
- refcod text — Constructor reference code. Example: mclaren.
- namelabel text — Full team name. **NULL means the constructor name has not been resolved or released.**. Example: McLaren.
- naty text — Nationality of the constructor. **NULL means the team's nationality is not specified in the dataset.**. Example: British.
- linkpage text — URL to the constructor's page. **NULL means the reference link is missing.**. Example: http://en.wikipedia.org/wiki/BMW_Sauber.
```

---

## m-171

> Can you rank the drivers based on the stability of their average lap time? Please show me each driver's surname and first_name in a JSON format, their average consistency score, and the number of Races Analyzed. Just focus on drivers who have competed in more than five races, and list the most consistent ones at the top.

```
Table: sports_events_large.drivers
- drv_main integer — Unique identifier for the driver. PK. Example: 1.
- driver_identity jsonb — Consolidates driver’s identity, nationality, and references.
```

```
Table: sports_events_large.lap_times
- rc_index integer — Foreign key to the races table (RAK_ID). FK to races. Example: 1093.
- wheel_unit integer — Foreign key to the drivers table (DRV_MAIN). FK to drivers. Example: 4.
- lapval integer — Lap value in the race. Example: 55.
- pp integer — Position for the lap. Example: 7.
- tmdesc text — Recorded lap-time string. **NULL means the lap time was not captured or is invalid.**. Example: 1:43.848.
- msec_val integer — Lap time in milliseconds. Example: 103848.
```

---

## m-001

> I'd like to see which of our dig sites have the best scan quality ratings. Could you show me each site's ID and name along with their average quality score, sorted best to worst?

```
Table: archeology_scan_large.pointcloud
- cloudregistry bigint — Auto-generated unique identifier for point cloud record. PK = PointCloud(CloudRegistry).
- crewref text — Reference to operator who generated point cloud. FK to Personnel.
- arcref text — Reference to associated archeologys project. FK to Projects.
- cloud_metrics jsonb — Point cloud quality and density measurements including resolution, coverage, overlap, and noise analysis
```

```
Table: archeology_scan_large.scans
- questregistry text — Unique identifier for scan session record. PK = Scans(QuestRegistry). Example: ASD409481.
- chronotag text — Precise timestamp when scan was performed. Example: 2024-09-03 07:20:28.479288 GMT+8.
- arcref text — Reference to associated archeologys project. FK to Projects.
- crewref text — Reference to operator who performed the scan. FK to Personnel.
- zoneref text — Reference to site where scan was conducted. FK to Sites.
- scancount text — Total number of individual scans in session. Example: 5 scans, moderate coverage session.
- climtune text — Weather conditions during scanning session. **NULL means weather conditions not recorded or monitoring equipment unavailable.**. Example: Windy conditions, potential equipment stability issues.
- huecatch text — Color capture mode or settings used during scan. **NULL means color capture not enabled or settings not recorded.**. Possible values: Grayscale, RGB.
- fmtfile text — File format used for storing scan data. Example: PTS.
- size text — Total file size of scan data in gigabytes. Example: 24.71 GB.
- scan_cost text — Equipment cost per GB. Example: 3.22 USD/GB.
- scanning_rate text — Data acquisition rate during scanning. Example: 63 MB/min.
```

```
Table: archeology_scan_large.sites
- zoneregistry text — Unique site code identifier for archeologys zone. PK = Sites(ZoneRegistry). Example: SC9016.
- zonelabel text — Descriptive name of the archeologys site. Example: Site-North Alexanderville.
- digunit text — Excavation unit designation within the site. Example: Unit-C9.
- gridtrace text — Grid reference system coordinates for site location. Example: S29-E8.
- phasefactor text — Cultural period or chronological phase classification. **NULL means cultural period classification is undetermined or analysis incomplete.**. Example: Iron Age.
- guessdate text — Estimated date or age of archeologys materials. Example: -2929 BCE.
- typesite text — Classification of archeologys site type. **NULL means site type classification is pending or cannot be determined.**. Example: Bur..
- guardhint text — Weather protection measures in place at site. **NULL means weather protection assessment not completed or not applicable.**. Possible values: Permanent, Temporary.
- geo_position jsonb — Geographic positioning data including coordinates, elevation, and excavation depth measurements
- site_status jsonb — Site condition and security assessment including preservation, access, safety, and risk evaluation status
```

---

## m-015

> Let’s create a list that keeps track of data flows with compliance issues when data crosses borders. For each flow that has this compliance gap, we need to include details like the record ID, the flow tag, the countries involved (origin and destination), the compliance status with relevant data protection laws, the status of compliance with local regulations, and the vendor trace ID.

```
Table: cross_border_large.Compliance
- complianceTrace bigint — Unique identifier for the compliance trace. PK. Example: 75.
- risk_tie bigint — Foreign key linking to RiskManagement(RISKTRACE). Example: 75.
- vendorTie bigint — Foreign key linking to VendorManagement(Vendor_Trace). Example: 75.
- recordRegistry text — Foreign key to the record registry. Example: CB735421.
- LEGALBASE text — The legal basis for data processing. Possible values: Legitimate Interest, Legal Obligation, Consent, Contract.
- consent_state text — The current state of user consent. Possible values: Pending, Expired, Valid, Not Required.
- ConsentColl date — Date of consent collection.
- consent_exp date — The expiration date of the user consent. Example: 2025-03-11.
- purp_limit text — The level of purpose limitation applied to data processing. Possible values: Specific, Multiple, General.
- PURP_DESC text — Description of the purpose for data processing. Possible values: Compliance, Research, Marketing, Business Operations.
- gdprComp text — Compliance status with the General Data Protection Regulation (GDPR). Possible values: Compliant, Partial, Non-compliant.
- CCPA_COMP text — Compliance status with the California Consumer Privacy Act (CCPA). Possible values: Partial, Compliant, Non-compliant.
- PIPLcomp text — Compliance status with China's Personal Information Protection Law (PIPL). Possible values: Compliant, Partial, Non-compliant.
- loc_law_comp text — Compliance status with local laws. Possible values: Partial, Compliant, Non-compliant.
- RegApprovals text — Status of regulatory approvals. Possible values: Obtained, Pending, Not Required.
- priv_imp_assess text — Status of the privacy impact assessment. Possible values: Required, Completed, In Progress.
- Datasubjright text — Status of support for data subject rights. Possible values: Partial, Limited, Fully Supported.
```

```
Table: cross_border_large.DataFlow
- RecordRegistry text — Unique identifier for the data flow record. PK. Example: CB100138.
- FLOWSTAMP text — Timestamp of the data flow event. Example: 2024-11-17T06:28:54.
- flow_overview jsonb — A JSON object containing a detailed overview of the data flow. Example: {"routing": {"protocol": "HTTPS", ...}}.
```

```
Table: cross_border_large.RiskManagement
- RISKTRACE bigint — Unique identifier for the risk trace. PK. Example: 461.
- flow_link text — Foreign key linking to the data flow. Example: CB604907.
- recordRegistry text — Foreign key to the record registry. Example: CB604907.
- risk_management_profile jsonb — A JSON object containing the detailed risk management profile. Example: {"assessment": {"risk_score": 30.5, ...}}.
```

```
Table: cross_border_large.VendorManagement
- Vendor_Trace bigint — Unique identifier for the vendor trace. PK. Example: 75.
- SEC_JOIN bigint — Foreign key to SecurityProfile(SECURITY_TRACE). Example: 75.
- riskassoc bigint — Foreign key for associated risks to RiskManagement(RISKTRACE). Example: 75.
- recordregistry text — Foreign key to the record registry. Example: CB735421.
- VENDASSESS text — The status of the vendor assessment. Possible values: Due, Completed, In Progress.
- vendSecRate text — The vendor's security rating. Possible values: D, A, C, B.
- VEND_AUD_DATE date — The date of the last vendor audit. Example: 2024-06-23.
- contrState text — The state of the vendor contract. Possible values: Under Review, Active, Expired.
- CONTR_EXPIRE date — The contract expiration date. Example: 2025-09-07.
- dpa_state text — The state of the Data Processing Agreement (DPA). Possible values: Required, Pending, Signed.
- SCCSTATE text — The state of Standard Contractual Clauses (SCCs). Possible values: Partial, Implemented, Not Required.
- bcr_state text — The state of Binding Corporate Rules (BCRs). Possible values: Pending, Not Applicable, Approved.
- docuState text — The state of vendor documentation. Possible values: Partial, Complete, Incomplete.
- pol_comp text — The vendor's policy compliance status. Possible values: Partial, Non-compliant, Full.
- procComp text — The vendor's process compliance status. Possible values: Partial, Non-compliant, Full.
- train_state text — The status of vendor training. Possible values: Overdue, Current, Due.
- certState text — The status of vendor certifications. Possible values: Expired, Valid, Pending.
- MONSTATE text — The state of vendor monitoring. Possible values: Active, Partial, Inactive.
- rep_state text — The status of vendor reporting. Possible values: Overdue, Current, Delayed.
- stakeComm text — The level of stakeholder communication. Possible values: Regular, Limited, Poor.
```

---

## m-029

> Let's look at data flows that cross borders and calculate their associated risk based on their volume. For each flow, I need to see the flow ID, its risk factor (rounded to two decimal places), the total risk (rounded to two decimal places), and how each flow ranks based on its total risk. Give me the flows where the total risk exceeds 1000, and sort them from highest to lowest. Please limit the results to the top 5 flows.

```
Table: cross_border_large.DataFlow
- RecordRegistry text — Unique identifier for the data flow record. PK. Example: CB100138.
- FLOWSTAMP text — Timestamp of the data flow event. Example: 2024-11-17T06:28:54.
- flow_overview jsonb — A JSON object containing a detailed overview of the data flow. Example: {"routing": {"protocol": "HTTPS", ...}}.
```

```
Table: cross_border_large.DataProfile
- profileTrace bigint — Unique identifier for the data profile trace. PK. Example: 461.
- Flow_Sign text — Foreign key to DataFlow(RecordRegistry). Example: CB604907.
- riskJoin bigint — Foreign key to RiskManagement(RISKTRACE). Example: 461.
- Record_Registry text — Foreign key to the record registry. Example: CB604907.
- DATATYPE text — The general type of the data. Possible values: Financial, Personal, Industrial, Medical, Commercial.
- dataSense text — The sensitivity level of the data. Possible values: Critical, High, Medium, Low.
- vol_gb real — The volume of the data in gigabytes. Example: 9289.72.
- REC_TALLY bigint — A tally of the records processed. Example: 3823424.
- subjectTally bigint — A tally of the data subjects involved. Example: 620647.
- ret_days bigint — The data retention period in days. Example: 3116.
- FormatType text — The format type of the data. Possible values: Unstructured, Structured, Mixed.
- qlty_score real — The calculated data quality score. Example: 1.9.
- Int_check text — The status of the integrity check. Possible values: Partial, Failed, Passed.
- CSUMVERIFY text — Status of checksum verification. Possible values: Success, Failed, Pending.
- srcValState text — The validation state at the source. Possible values: Failed, Verified, Pending.
- DEST_VAL_state text — The validation state at the destination. Possible values: Failed, Verified, Pending.
```

```
Table: cross_border_large.RiskManagement
- RISKTRACE bigint — Unique identifier for the risk trace. PK. Example: 461.
- flow_link text — Foreign key linking to the data flow. Example: CB604907.
- recordRegistry text — Foreign key to the record registry. Example: CB604907.
- risk_management_profile jsonb — A JSON object containing the detailed risk management profile. Example: {"assessment": {"risk_score": 30.5, ...}}.
```

---

## m-056

> I want to know the average Information Ratio after adjusting for how consistent it is. I just need that one final number.

```
Table: exchange_traded_funds_large.funds
- productnum bigint — A SERIAL primary key uniquely identifying each fund product in the database.
- tickersym character varying — Unique ticker symbol for the fund as traded on exchanges (e.g., 'SPY', 'VTI', 'QQQ'). Must be unique across all records.
- quotemode character varying — Type of security quotation or fund structure classification. All records are ETFs in this dataset. Possible values: ETF.
- geozone character varying — Geographic region or country focus of the fund's investments. All values represent United States with varying formats. Possible values: USA, US, United States, U.S., U.S.A., America, usa, us, UNITED_STATES.
- shortlabel character varying — Abbreviated display name of the fund for user interfaces and brief references. Contains  NULL when short label is not available or fund uses only full description.
- fulldescription text — Complete official name and description of the fund including investment objective and strategy details. Contains  NULL when detailed description is not available or pending.
- currencybase character varying — Base currency in which the fund is denominated and NAV is calculated. All values represent US Dollar with varying formats. Possible values: USD, US Dollar, US_DOLLAR, Usd, Dollar, US$, DOLLAR, usd, AmericanDollar.
- strategytype character varying — Investment style or strategy classification for equity funds, indicating the fund's approach to stock selection. Possible values: Growth, Value, Blend. Contains NULL when the fund does not hold equities or strategy classification is not applicable (e.g., bond funds, sector funds).
- capsize character varying — Market capitalization focus of the fund's equity holdings, indicating the size category of companies the fund primarily invests in. Possible values: Small, Medium, Large. Contains NULL when the fund does not hold equities or cap size classification is not applicable (e.g., bond funds).
- parentgroup character varying — Foreign key referencing families.GroupName, indicating which fund family or asset management company manages this fund.
- listingvenue character varying — Foreign key referencing exchanges.MarketCode, indicating the primary exchange where the fund is listed and traded.
- productclass character varying — Foreign key referencing categories.ClassType, indicating the fund's investment category classification.
- networth bigint — Total net asset value (NAV) of the fund in base currency units, representing assets under management. Example: 26004670464, 145110080, 8899219. Contains NULL when NAV data is not yet reported or fund is in liquidation process.
- yieldrate real — Distribution yield or dividend yield of the fund, expressed as a decimal (e.g., 0.0467 = 4.67%). Example: 0.3153, 0.0061, 0.0454. Contains NULL when the fund does not distribute dividends or yield data is not yet calculated.
- launchdate date — Date when the fund was first established and began operations (YYYY-MM-DD). Contains  NULL when launch date is not available or fund is in pre-launch phase.
- turnoverratio real — Annual portfolio turnover ratio indicating how frequently the fund trades its holdings, expressed as a decimal (e.g., 1.6 = 160% turnover). Example: 1.6, 0.43, 0.1879. Contains NULL when turnover data is not yet available or fund has insufficient trading history.
- strategynotes text — Detailed text description of the fund's investment strategy, objectives, and methodology. Contains  NULL when strategy notes are not available or not provided by fund management.
- expensenet real — Net expense ratio representing the annual cost to investors after fee waivers and reimbursements, expressed as a decimal (e.g., 0.0132 = 1.32%). Example: 0.0132, 0.0101, 0.0014. Contains NULL when expense ratio data is not yet reported or fund is too new to have established fees.
- benchmarkexp real — Benchmark expense ratio representing the cost of tracking the fund's benchmark index, expressed as a decimal (e.g., 0.0022 = 0.22%). Example: 0.0022, 0.0028, 0.0038. Contains NULL when benchmark expense data is not available or fund does not track a benchmark index.
- vol3m bigint — Average daily trading volume over the past 3 months, indicating liquidity and trading activity. Example: 43115, 499616, 705119.
- volrecent real — Most recent trading volume or current period volume figure. Example: 716570, 155510, 1961860. Contains NULL when recent volume data is not available or trading was halted.
- ma50 real — 50-day moving average price of the fund, used for medium-term trend analysis. Example: 38.636, 147.557, 25.59. Contains NULL when insufficient trading history exists to calculate 50-day average.
- ma200 real — 200-day moving average price of the fund, used for long-term trend analysis. Example: 56.79, 78.798, 39.194. Contains NULL when insufficient trading history exists to calculate 200-day average.
- equityweight real — Proportion of fund assets allocated to equity/stock holdings, expressed as a decimal between 0 and 1 (e.g., 0.9937 = 99.37%). Example: 0.9937, 0.9977, 0.1244. Contains NULL when asset allocation data is not available or fund structure does not support weight breakdown.
- bondweight real — Proportion of fund assets allocated to bond/fixed-income holdings, expressed as a decimal between 0 and 1 (e.g., 0.9977 = 99.77%). Example: 0.0697, 0.0934, 0.9977. Contains NULL when asset allocation data is not available or fund structure does not support weight breakdown.
- pb_ratio real — Price-to-book ratio of the fund's underlying equity holdings, indicating valuation relative to book value. Example: 1.6, 2.35, 4.32. Contains NULL when the fund does not hold equities or P/B calculation is not applicable (e.g., bond funds).
- pcf_ratio real — Price-to-cash-flow ratio of the fund's underlying equity holdings, measuring valuation relative to operating cash flow. Example: 12.01, 16.22, 10.87. Contains NULL when the fund does not hold equities or P/CF calculation is not applicable.
- pe_ratio real — Price-to-earnings ratio of the fund's underlying equity holdings, indicating valuation relative to earnings. Example: 10.87, 24.59, 34.94. Contains NULL when the fund does not hold equities or P/E calculation is not applicable (e.g., bond funds, funds with negative earnings).
- ps_ratio real — Price-to-sales ratio of the fund's underlying equity holdings, measuring valuation relative to revenue. Example: 6.19, 0.64, 2.04. Contains NULL when the fund does not hold equities or P/S calculation is not applicable.
- avgmaturity real — Average maturity period of bonds held in the fund portfolio, measured in years. Relevant for fixed-income funds to assess interest rate sensitivity. Example: 2.22, 5.13, 10.27. Contains NULL when the fund does not hold fixed-income securities or maturity data is not applicable (e.g., pure equity funds).
- duration real — Modified duration of the fund's bond portfolio, measuring sensitivity to interest rate changes in years. Higher values indicate greater interest rate risk. Example: 3.12, 2.73, 11.58. Contains NULL when the fund does not hold fixed-income securities or duration calculation is not applicable.
- fundclass jsonb — Consolidates fund classification and strategy information including geographic focus, investment strategy, market cap focus, and basic fund characteristics.
- fundmetrics jsonb — Groups fundamental financial metrics and operational data including assets under management, yield rates, expense ratios, and turnover statistics.
- tradingdata jsonb — Aggregates trading and market data including volume metrics and moving averages for technical analysis and liquidity assessment.
- allocweights jsonb — Contains asset allocation percentages and portfolio composition data including equity, bond weights and bond characteristics for portfolio analysis.
- valuationratios jsonb — Consolidates fundamental valuation ratios for equity holdings including price-to-book, price-to-earnings, price-to-cash-flow, and price-to-sales ratios.
```

```
Table: exchange_traded_funds_large.performance
- perfid bigint — A SERIAL primary key uniquely identifying each fund performance record.
- productref character varying — Foreign key referencing funds.TickerSym, ensuring 1:1 relationship for performance data per fund.
- reportdate date — Date when the performance data was calculated or reported (YYYY-MM-DD). Contains  NULL when report date is not available.
- high52w real — Highest trading price reached in the past 52 weeks. Example: 30.6, 62.6, 52.17. Contains NULL when insufficient trading history exists for 52-week calculation.
- highdelta real — Absolute price difference between current price and 52-week high. Negative values indicate current price is below the high. Example: -2.9842, -6.348, -28.98. Contains NULL when 52-week high data is not available or calculation cannot be performed.
- highdeltapct real — Percentage difference between current price and 52-week high, expressed as a decimal. Negative values indicate distance below the high. Example: -0.03489, -0.39683, -0.06735. Contains NULL when 52-week high data is not available.
- low52w real — Lowest trading price reached in the past 52 weeks. Example: 30.6, 89.5, 24.59. Contains NULL when insufficient trading history exists for 52-week calculation.
- lowdelta real — Absolute price difference between current price and 52-week low. Positive values indicate current price is above the low. Example: 2.9145, 8.22, 11.7508. Contains NULL when 52-week low data is not available or calculation cannot be performed.
- lowdeltapct real — Percentage difference between current price and 52-week low, expressed as a decimal. Positive values indicate distance above the low. Example: 0.28562, 0.10058, 0.15487. Contains NULL when 52-week low data is not available.
- rangemove real — Absolute price range between 52-week high and low, indicating price volatility span. Example: 8.92, 107.982, 45.06. Contains NULL when insufficient trading history for 52-week range calculation.
- rangemovepct real — Percentage price range relative to 52-week low, measuring relative volatility. Example: 0.09161, 0.17467, 0.25442. Contains NULL when insufficient trading history for calculation.
- rytd real — Fund's year-to-date return, expressed as a decimal. Example: 0.4286, -0.3981, 0.338. Contains NULL when YTD return data is not yet calculated or fund launched during current year.
- benchrytd real — Benchmark index year-to-date return, expressed as a decimal. Example: 0.0392, 0.1375, 0.1483. Contains NULL when benchmark YTD return data is not available.
- r1m real — Fund's return over the past 1 month, expressed as a decimal. Example: -0.049, 0.0805, 0.1031. Contains NULL when monthly return data is not yet calculated or fund was not trading for full month.
- benchr1m real — Benchmark index return over the past 1 month, expressed as a decimal. Negative values indicate losses. Example: 0.0128, -0.001, -0.0199. Contains NULL when benchmark return data is not available for the period.
- r3m real — Fund's return over the past 3 months, expressed as a decimal. Example: -0.049, -0.1339, -0.1841. Contains NULL when the fund does not have 3-month operating history or data is pending.
- benchr3m real — Benchmark index return over the past 3 months, expressed as a decimal. Example: 0.032, 0.0562, -0.0519. Contains NULL when benchmark return data is not available for the period.
- r1y real — Fund's return over the past 1 year, expressed as a decimal. Example: 0.623, 0.4885, -0.2411. Contains NULL when the fund does not have 1-year operating history.
- benchr1y real — Benchmark index return over the past 1 year, expressed as a decimal. Example: 0.0494, -0.0223, 0.1736. Contains NULL when benchmark return data is not available for the period.
- r3y real — Fund's annualized return over 3 years, expressed as a decimal. Example: 0.1576, 0.1197, 0.0593. Contains NULL when the fund does not have 3-year operating history.
- benchr3y real — Benchmark index annualized return over 3 years, expressed as a decimal. Example: 0.0024, 0.0589, 0.1317. Contains NULL when benchmark does not have 3-year history or data is not available.
- r5y real — Fund's annualized return over 5 years, expressed as a decimal. Example: 0.0454, 0.1031, 0.0854. Contains NULL when the fund does not have 5-year operating history.
- benchr5y real — Benchmark index annualized return over 5 years, expressed as a decimal. Example: 0.1576, 0.032, 0.1473. Contains NULL when benchmark does not have 5-year history or data is not available.
- r10y real — Fund's annualized return over 10 years, expressed as a decimal. Negative values indicate losses. Example: 0.0061, 0.0454, -0.4632. Contains NULL when the fund does not have 10-year operating history.
- benchr10y real — Benchmark index annualized return over 10 years, expressed as a decimal (e.g., 0.0348 = 3.48%). Used for comparing fund performance against its benchmark. Example: 0.0348, 0.0467, 0.0703. Contains NULL when benchmark does not have 10-year history or benchmark data is not available.
- positiveyears real — Count of calendar years with positive total returns since fund inception. Used to assess historical consistency. Example: 13, 18, 4. Contains NULL when historical annual return data is incomplete or fund is too new.
- negativeyears real — Count of calendar years with negative total returns since fund inception. Used to assess historical downside frequency. Example: 13, 2, 9. Contains NULL when historical annual return data is incomplete or fund is too new.
- topholdings text — List or description of the fund's largest portfolio holdings by weight. Contains NULL when holdings data is not disclosed or fund does not report top holdings.
- topweight real — Combined weight percentage of top holdings in the portfolio. Contains NULL when holdings weight data is not disclosed or not applicable.
- pricerange52w jsonb — Groups 52-week price range data including highs, lows, deltas, and percentage changes for price movement analysis and volatility assessment.
- returnmetrics jsonb — Aggregates fund performance returns across different time periods including fund and benchmark returns for comprehensive performance comparison.
- histstats jsonb — Consolidates historical performance statistics including positive/negative year counts and top holdings information for fund analysis.
```

```
Table: exchange_traded_funds_large.risk_metrics
- riskid bigint — A SERIAL primary key uniquely identifying each risk metrics record for funds.
- investmentref character varying — Foreign key referencing funds.TickerSym, ensuring 1:1 relationship for risk analysis per fund.
- alpha3y real — Jensen's alpha measuring fund's risk-adjusted excess return over 3 years relative to its benchmark. Example: 10.87, -2.35, 4.32. Contains NULL when alpha calculation data is incomplete.
- beta3y real — Beta coefficient measuring fund's systematic risk relative to benchmark over 3 years. Example: -2.35, 0.43, 5.15. Contains NULL when beta calculation data is incomplete.
- avgreturn3y real — Average annual return over 3 years, expressed as percentage points. Example: 0.43, 1.6, -1.32.
- rsquared3y real — R-squared value over 3 years, expressed as percentage. Higher values indicate closer tracking to benchmark. Example: 45.06, 86.01, 88.01. Contains NULL when R-squared calculation data is incomplete.
- volatility3y real — Annualized standard deviation of returns over 3 years. Example: 12.01, 5.13, 25.59.
- sharperatio3y real — Sharpe ratio over 3 years. Negative values indicate returns below risk-free rate. Example: 0.89, -1.09, 0.37. Contains NULL when Sharpe ratio calculation data is incomplete.
- treynorratio3y real — Treynor ratio over 3 years. Example: 24.59, 16.13, -13.96.
- alpha5y real — Jensen's alpha measuring fund's risk-adjusted excess return over 5 years relative to its benchmark. Example: -2.35, 1.81, 28.12. Contains NULL when the fund does not have 5-year history or benchmark data is unavailable.
- beta5y real — Beta coefficient measuring fund's systematic risk relative to benchmark over 5 years. Example: -2.35, 3.18, 1.6. Contains NULL when the fund does not have 5-year history or benchmark data unavailable.
- avgreturn5y real — Average annual return over 5 years, expressed as percentage points. Example: 1.6, 0.43, -1.44. Contains NULL when the fund does not have 5-year operating history.
- rsquared5y real — R-squared value over 5 years, expressed as percentage. Example: 98.8, 89.5, 52.17. Contains NULL when the fund does not have 5-year history.
- volatility5y real — Annualized standard deviation of returns over 5 years. Example: 15.33, 40.25, 8.22. Contains NULL when the fund does not have 5-year history.
- sharperatio5y real — Sharpe ratio over 5 years. Example: 0.89, 1.43, -1.41. Contains NULL when the fund does not have 5-year history.
- treynorratio5y real — Treynor ratio over 5 years. Example: 0.84, -0.46, 17.81. Contains NULL when the fund does not have 5-year history.
- alpha10y real — Jensen's alpha measuring fund's risk-adjusted excess return over 10 years relative to its benchmark. Positive values indicate outperformance. Example: -2.35, 1.81, 8.45. Contains NULL when the fund does not have 10-year history or benchmark comparison is not available.
- beta10y real — Beta coefficient measuring fund's systematic risk/volatility relative to its benchmark over 10 years. Values >1 indicate higher volatility than benchmark. Example: 17.11, 0.43, 1.6. Contains NULL when the fund does not have 10-year history or benchmark comparison unavailable.
- avgreturn10y real — Average annual return over 10 years, expressed as percentage points. Negative values indicate average losses. Example: 1.6, 0.43, -1.32. Contains NULL when the fund does not have 10-year operating history.
- rsquared10y real — R-squared value indicating how much of the fund's movement is explained by benchmark movement over 10 years, expressed as percentage (0-100). Example: 14.03, 69.04, 93. Contains NULL when the fund does not have 10-year history.
- volatility10y real — Annualized standard deviation of returns over 10 years, measuring total risk/price variability. Higher values indicate greater volatility. Example: 16, 18.67, 30.86. Contains NULL when the fund does not have 10-year history.
- sharperatio10y real — Sharpe ratio measuring risk-adjusted return over 10 years (excess return per unit of volatility). Higher values indicate better risk-adjusted performance. Example: -1.55, 0.35, 0.89. Contains NULL when the fund does not have 10-year history.
- treynorratio10y real — Treynor ratio measuring excess return per unit of systematic risk (beta) over 10 years. Example: 15.33, -11.05, 11.41. Contains NULL when the fund does not have 10-year history or beta is unavailable.
- risk3y jsonb — Groups 3-year risk and performance metrics including alpha, beta, returns, volatility, and risk-adjusted ratios for short-term risk analysis.
- risk5y jsonb — Groups 5-year risk and performance metrics including alpha, beta, returns, volatility, and risk-adjusted ratios for medium-term risk analysis.
- risk10y jsonb — Groups 10-year risk and performance metrics including alpha, beta, returns, volatility, and risk-adjusted ratios for long-term risk analysis.
```

---

## m-086

> By platform kind, average a score built as: how manipulated the content looks, times how urgently it should be reviewed, times how central it is in the network.

```
Table: fake_account_large.account_clusters
- acct_bridge text — Account reference for the cluster. PK. FK to accounts.
- clu_ref text — Cluster reference identifier. PK. FK to cluster_analysis.
```

```
Table: fake_account_large.accounts
- acct_ref text — Unique account reference. PK. Example: ACC7210284.
- plt_key text — Platform code reference. FK to platforms.
- OrigStamp date — Original account creation timestamp. **NULL means account creation timestamp not provided.**. Example: 26-Dec-23.
- AGE_D bigint — Age of the account in days. Example: 393.
- StateFlag text — Current state of the account. Possible values: Active, Deleted, Dormant, Suspended.
- acct_form text — Account form or type. Possible values: Bot, Business, Hybrid, Personal.
- VerifyMark text — Verification status of the account. Possible values: Failed, Pending, Suspicious, Unverified.
- ProfileScore real — Profile score of the account. Example: 0.167.
```

```
Table: fake_account_large.cluster_analysis
- CLSTR_PIN text — Unique cluster identifier. PK. Example: CL0029.
- ClusterQty bigint — Number of accounts in the cluster. Example: 5.
- CluRole text — Role or function of the cluster. Possible values: Botnet, Community, InfluenceNetwork, SocialGroup, SpamRing.
- NetInfl real — Network influence score. Example: 0.362.
- CoordScore real — Coordination score. Example: 0.363.
```

```
Table: fake_account_large.content_activity
- acct_slot text — Account reference for content activity. PK. FK to accounts.
- content_metrics jsonb — Packs post-rate, linguistic diversity, hashtag / mention patterns and media-sharing ratios into one JSONB blob for real-time content-quality scoring.
```

```
Table: fake_account_large.interaction_metrics
- acct_dm text — Account reference for direct messaging metrics. PK. FK to accounts.
- MsgSim real — Message similarity score. Example: 0.041.
- MsgFreq real — Message frequency. Example: 60.1.
- MsgTargetDiv real — Message target diversity. Example: 0.498.
- RespTimePtn text — Response time pattern. **NULL means response time pattern not recorded.**. Possible values: Delayed, Instant, Natural, Random.
- ConvNat real — Conversation nature score. Example: 0.825.
- SentVar real — Sentiment variance score. Example: 0.005.
- LangSoph real — Language sophistication score. Example: 0.03.
- TxtUniq real — Text uniqueness score. Example: 0.44.
- KeyPtnHit real — Key pattern hit score. **NULL means key pattern hit not recorded.**. Example: 0.589.
- TopCoh real — Top coherence score. Example: 0.856.
```

```
Table: fake_account_large.network_metrics
- acct_node text — Account reference for network metrics. PK. FK to accounts.
- FollowNum bigint — Number of followers. Example: 32353.
- FollowgNum bigint — Number of followees. Example: 53330.
- FollGrow real — Follower growth rate. Example: 0.697.
- FingGrow real — Following growth rate. Example: 0.899.
- FollRatio real — Follower-followee ratio. Example: 5.162.
- MutConn real — Mutual connections count. Example: 0.964.
- ConnGrowPtn text — Connection growth pattern. Possible values: Bot-like, Burst, Organic, Suspicious.
- ConnQual real — Connection quality score. Example: 0.819.
- EngRate real — Engagement rate. Example: 0.132.
- EngAuth real — Engagement authority score. Example: 0.954.
- LikeRt real — Like rate score. Example: 0.738.
- ComRt real — Comment rate score. **NULL means comment rate not recorded.**. Example: 0.282.
- ShareRt real — Share rate score. Example: 0.696.
- IntRecip real — Interaction reciprocity score. Example: 0.817.
- IntDiv real — Interaction diversity score. Example: 0.681.
- TempIntPtn text — Temporary interaction pattern. Possible values: Automated, Natural, Periodic, Random.
```

```
Table: fake_account_large.platforms
- PLT_CODE text — Unique platform code. PK. Example: PL331.
- PLT_KIND text — Type of the platform. Not NULL. Possible values: Forum, Microblog, Social Network, Video Platform.
```

```
Table: fake_account_large.risk_and_moderation
- acct_risk text — Account reference for risk and moderation data. PK. FK to accounts.
- risk_profile jsonb — Bundles risk, authenticity / credibility, violation history and overall reputation into one JSONB field for faster trust-and-safety look-ups and enforcement rules.
```

---

## m-123

> How does the cold affect our batteries? I want to see a breakdown of battery health based on how cold it is outside. Group the gear into a few temperature buckets like 'Extreme Cold,' 'Standard Cold,' and 'Mild Cold,' and for each bucket, show how many pieces of equipment are in it and what their average battery health is.

```
Table: polar_equipment_large.Communication
- COMM_ID bigint — Unique identifier for the communication record. PK.
- equipRef text — Reference to the equipment. FK to Equipment.EQUIP_CODE.
- loc_link text — Reference to the location. FK to Location.STATION_name.
- GPS_signal text — GPS signal status. **NULL means no GPS signal data recorded.**. Possible values: Medium, Strong, Weak.
- sat_conn_stat text — Satellite connection status. **NULL means no satellite connection status recorded.**. Possible values: Connected, Disconnected, Limited.
- radioSignal_dBm real — Radio signal strength in dBm. Example: -97.8.
- radioFreq_mhz real — Radio frequency in MHz. Example: 731.2.
- antenna_stat text — Antenna status. Possible values: Error, Normal, Warning.
- netLatency_ms real — Network latency in milliseconds. Example: 1006.0.
- dataRate_kbps real — Data rate in kilobits per second. Example: 389.6.
- wifiSignal_dBm real — Wi-Fi signal strength in dBm. **NULL means no Wi-Fi signal data recorded.**. Example: -61.7.
- btStatus text — Bluetooth status. Possible values: Error, Off, On, Pairing.
- opmaint_link bigint — Reference to the operation and maintenance record. FK to OperationMaintenance.OP_MAINT_ID.
```

```
Table: polar_equipment_large.PowerBattery
- PWR_BATT_ID bigint — Unique identifier for the power battery. PK.
- equip_ref text — Reference to the equipment. FK to Equipment.EQUIP_CODE.
- battery_telemetry jsonb — Captures the full real-time power and battery state of a unit (operating mode, SOC, health, charge parameters, consumption, efficiency) as a single JSONB blob.
```

```
Table: polar_equipment_large.WeatherAndStructure
- WEATHER_ID bigint — Unique identifier for the weather and structure record. PK.
- loc_link text — Reference to the location. FK to Location.STATION_name.
- opmaint_link bigint — Reference to the operation and maintenance record. FK to OperationMaintenance.OP_MAINT_ID.
- extTempC real — External temperature in Celsius. Example: -14.9.
- windSpeed_ms real — Wind speed in meters per second. Example: 26.5.
- windDir_deg real — Wind direction in degrees. **NULL means no wind direction data recorded.**. Example: 71.4.
- baroPress_hpa real — Barometric pressure in hectopascals. Example: 975.3.
- solarRad_wm2 real — Solar radiation in watts per square meter. Example: 541.0.
- snowDepth_cm bigint — Snow depth in centimeters. Example: 143.6.
- iceThick_cm real — Ice thickness in centimeters. Example: 254.4.
- visibility_km real — Visibility in kilometers. Example: 42.8.
- precipType text — Type of precipitation (e.g., rain, snow). **NULL means no precipitation type recorded.**. Possible values: Blowing Snow, Ice, Snow.
- precipRate_mmh real — Precipitation rate in millimeters per hour. Example: 2.4.
- snowLoad_kgm2 bigint — Snow load in kilograms per square meter. Example: 459.7.
- structLoadPct real — Structural load percentage. Example: 62.
- structIntegrityStat text — Structural integrity status. **NULL means no structural integrity status recorded.**. Possible values: Critical, Normal, Warning.
- vibrLevel_mms2 real — Vibration level in millimeters squared. Example: 8.61.
- noiseLevel_dB real — Noise level in decibels. Example: 38.5.
```
