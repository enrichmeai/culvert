# FILE FORMATS SPECIFICATION

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Component:** Phase 3, Component 2  
**Status:** Production Ready

---

## 📋 Overview

This document specifies the CSV file formats for all entity types processed by the LOA Blueprint pipeline. Each format is derived from mainframe legacy data and normalized for cloud processing.

### File Processing Rules

All input files must:
1. ✅ Be in CSV format with UTF-8 encoding
2. ✅ Include header row with column names
3. ✅ Use comma (`,`) as field delimiter
4. ✅ Use double quotes (`"`) for field enclosure
5. ✅ Use CRLF (`\r\n`) line endings
6. ✅ Contain no empty rows
7. ✅ Match expected column count

### Entity Types

| Entity | File Pattern | Record Count | Frequency |
|--------|-------------|--------------|-----------|
| **Applications** | `applications_*.csv` | 10,000-100,000 | Daily |
| **Customers** | `customers_*.csv` | 50,000-500,000 | Weekly |
| **Branches** | `branches_*.csv` | 100-1,000 | Monthly |
| **Collateral** | `collateral_*.csv` | 5,000-50,000 | Daily |

---

## 1️⃣ APPLICATIONS CSV FORMAT

### Purpose
Loan application records from mainframe systems. Each row represents a single application with borrower information and loan details.

### File Naming Convention
```
applications_YYYYMMDD_HHMMSS.csv
applications_20250101_143022.csv
```

### CSV Structure

#### Header Row
```
run_id,processed_timestamp,source_file,application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
```

#### Column Specifications

| Column | Type | Required | Format | Example | Notes |
|--------|------|----------|--------|---------|-------|
| `run_id` | String | ✅ Yes | UUID or run timestamp | `run_20250101_143022` | Unique per pipeline run |
| `processed_timestamp` | DateTime | ✅ Yes | ISO 8601 | `2025-01-01T14:30:22Z` | Server timestamp |
| `source_file` | String | ❌ No | Filename | `APP_EXTRACT_20250101.txt` | Original mainframe filename |
| `application_id` | String | ✅ Yes | Alphanumeric, 1-20 chars | `APP123456789` | Must be unique |
| `ssn` | String | ❌ No | ###-##-#### | `123-45-6789` | PII - masked in logs |
| `applicant_name` | String | ❌ No | Text, max 100 chars | `JOHN DOE` | Converted to UPPERCASE |
| `loan_amount` | Integer | ❌ No | Whole dollars | `250000` | $0-$10,000,000 range |
| `loan_type` | String | ❌ No | MORTGAGE, PERSONAL, AUTO, HOME_EQUITY | `MORTGAGE` | Normalized values only |
| `application_date` | Date | ❌ No | YYYY-MM-DD | `2025-01-15` | Date application submitted |
| `branch_code` | String | ❌ No | Code, 1-10 chars | `BRANCH001` | Maps to branches table |

### Validation Rules

#### Required Field Rules
- `run_id`: Must not be empty
- `processed_timestamp`: Must be valid ISO 8601 datetime
- `application_id`: Must not be empty, must be unique within file

#### Format Validation
- `ssn`: If provided, must match pattern `XXX-XX-XXXX` (Xs = digits)
- `applicant_name`: If provided, must be alphabetic characters + spaces, no special chars
- `loan_amount`: If provided, must be integer ≥ 0
- `loan_type`: If provided, must be one of: MORTGAGE, PERSONAL, AUTO, HOME_EQUITY
- `application_date`: If provided, must be valid date (YYYY-MM-DD format)
- `branch_code`: If provided, must exist in branches table

#### Value Constraints
- Row count per file: 1 to 100,000 records (plus header)
- File size: max 500 MB
- No null bytes
- No control characters (except CRLF)

### Sample Data

#### Valid Examples
```csv
run_id,processed_timestamp,source_file,application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
run_20250101_143022,2025-01-01T14:30:22Z,APP_EXTRACT_20250101.txt,APP123456789,123-45-6789,JOHN DOE,250000,MORTGAGE,2025-01-15,BRANCH001
run_20250101_143022,2025-01-01T14:30:22Z,APP_EXTRACT_20250101.txt,APP987654321,,JANE SMITH,75000,PERSONAL,2025-01-10,BRANCH002
run_20250101_143022,2025-01-01T14:30:22Z,APP_EXTRACT_20250101.txt,APP555555555,456-78-9012,BOB JOHNSON,,AUTO,,BRANCH001
```

#### Invalid Examples
```csv
# Missing run_id (INVALID - required field)
,2025-01-01T14:30:22Z,APP_EXTRACT.txt,APP123456789,123-45-6789,JOHN,250000,MORTGAGE,2025-01-15,BRANCH001

# Invalid SSN format (INVALID - must be XXX-XX-XXXX)
run_20250101,2025-01-01T14:30:22Z,APP_EXTRACT.txt,APP123456789,1234567890,JOHN,250000,MORTGAGE,2025-01-15,BRANCH001

# Invalid loan_type (INVALID - must be predefined value)
run_20250101,2025-01-01T14:30:22Z,APP_EXTRACT.txt,APP123456789,123-45-6789,JOHN,250000,INVALID_TYPE,2025-01-15,BRANCH001

# Invalid application_date format (INVALID - must be YYYY-MM-DD)
run_20250101,2025-01-01T14:30:22Z,APP_EXTRACT.txt,APP123456789,123-45-6789,JOHN,250000,MORTGAGE,01/15/2025,BRANCH001
```

### Processing Pipeline

```
Input File (applications_*.csv)
    ↓
FileValidator.validate_csv_format()
    ↓
FileValidator.validate_encoding()
    ↓
Required Field Check (run_id, processed_timestamp, application_id)
    ↓
Format Validation (SSN, dates, types)
    ↓
Referential Integrity (branch_code → branches table)
    ↓
BigQuery Load (applications_raw table)
    ↓
FileArchiver.archive_file()
```

### Error Handling

When validation fails:
1. Record rejected, logged in `applications_errors` table
2. Error reason captured: `missing_required_field`, `invalid_format`, `referential_integrity`
3. File moved to error bucket: `gs://error-bucket/applications/YYYYMMDD/`
4. Alert sent to monitoring system
5. No partial loads into production table

---

## 2️⃣ CUSTOMERS CSV FORMAT

### Purpose
Customer profile records with account information, contact details, and credit data. Each row represents a unique customer.

### File Naming Convention
```
customers_YYYYMMDD_HHMMSS.csv
customers_20250110_093015.csv
```

### CSV Structure

#### Header Row
```
run_id,processed_timestamp,source_file,customer_id,ssn,customer_name,account_number,email,phone,credit_score,customer_since,branch_code
```

#### Column Specifications

| Column | Type | Required | Format | Example | Notes |
|--------|------|----------|--------|---------|-------|
| `run_id` | String | ❌ No | UUID or run timestamp | `run_20250110_093015` | Unique per pipeline run |
| `processed_timestamp` | DateTime | ❌ No | ISO 8601 | `2025-01-10T09:30:15Z` | Server timestamp |
| `source_file` | String | ❌ No | Filename | `CUST_MASTER_20250110.txt` | Original mainframe filename |
| `customer_id` | String | ✅ Yes | Alphanumeric, 1-20 chars | `CUST00123456` | Must be unique |
| `ssn` | String | ❌ No | ###-##-#### | `456-78-9012` | PII - masked in logs |
| `customer_name` | String | ❌ No | Text, max 100 chars | `JANE SMITH` | Converted to UPPERCASE |
| `account_number` | String | ❌ No | Numeric/alphanumeric, 1-20 | `123456789` | Bank account identifier |
| `email` | String | ❌ No | Valid email format | `jane.smith@email.com` | Validated as email |
| `phone` | String | ❌ No | ###-###-#### or +1### format | `555-123-4567` | Formatted consistently |
| `credit_score` | Integer | ❌ No | 300-850 range | `750` | Fair Isaac score |
| `customer_since` | Date | ❌ No | YYYY-MM-DD | `2020-06-15` | Account opening date |
| `branch_code` | String | ❌ No | Code, 1-10 chars | `BRANCH002` | Maps to branches table |

### Validation Rules

#### Required Field Rules
- `customer_id`: Must not be empty, must be unique within file

#### Format Validation
- `ssn`: If provided, must match pattern `XXX-XX-XXXX`
- `customer_name`: If provided, max 100 chars, alphanumeric + spaces
- `account_number`: If provided, 1-20 chars, numeric or alphanumeric
- `email`: If provided, must be valid email (contains @ and domain)
- `phone`: If provided, must match `XXX-XXX-XXXX` or `+1XXX` format
- `credit_score`: If provided, must be integer in range [300, 850]
- `customer_since`: If provided, must be valid date (YYYY-MM-DD)
- `branch_code`: If provided, must exist in branches table

#### Value Constraints
- Row count per file: 1 to 500,000 records (plus header)
- File size: max 2 GB
- No duplicate customer_id values
- No null bytes
- No control characters (except CRLF)

### Sample Data

#### Valid Examples
```csv
run_id,processed_timestamp,source_file,customer_id,ssn,customer_name,account_number,email,phone,credit_score,customer_since,branch_code
run_20250110_093015,2025-01-10T09:30:15Z,CUST_MASTER_20250110.txt,CUST00123456,456-78-9012,JANE SMITH,123456789,jane.smith@email.com,555-123-4567,750,2020-06-15,BRANCH002
run_20250110_093015,2025-01-10T09:30:15Z,CUST_MASTER_20250110.txt,CUST00987654,,BOB JONES,,bob@example.com,555-987-6543,,2015-03-22,BRANCH001
run_20250110_093015,2025-01-10T09:30:15Z,CUST_MASTER_20250110.txt,CUST00555555,789-01-2345,ALICE BROWN,987654321,,,680,,
```

#### Invalid Examples
```csv
# Missing customer_id (INVALID - required field)
run_20250110,2025-01-10T09:30:15Z,CUST_MASTER.txt,,456-78-9012,JANE,123456789,jane@email.com,555-123-4567,750,2020-06-15,BRANCH002

# Invalid email format (INVALID - must contain @)
run_20250110,2025-01-10T09:30:15Z,CUST_MASTER.txt,CUST00123456,456-78-9012,JANE,123456789,jane.email.com,555-123-4567,750,2020-06-15,BRANCH002

# Credit score out of range (INVALID - must be 300-850)
run_20250110,2025-01-10T09:30:15Z,CUST_MASTER.txt,CUST00123456,456-78-9012,JANE,123456789,jane@email.com,555-123-4567,900,2020-06-15,BRANCH002

# Invalid phone format (INVALID - must be XXX-XXX-XXXX or +1XXX)
run_20250110,2025-01-10T09:30:15Z,CUST_MASTER.txt,CUST00123456,456-78-9012,JANE,123456789,jane@email.com,5551234567,750,2020-06-15,BRANCH002
```

### Processing Pipeline

```
Input File (customers_*.csv)
    ↓
FileValidator.validate_csv_format()
    ↓
FileValidator.validate_encoding()
    ↓
Required Field Check (customer_id)
    ↓
Format Validation (SSN, email, phone, credit_score)
    ↓
Duplicate Check (customer_id uniqueness)
    ↓
Referential Integrity (branch_code → branches table)
    ↓
BigQuery Load (customers_raw table)
    ↓
FileArchiver.archive_file()
```

### Error Handling

When validation fails:
1. Record rejected, logged in `customers_errors` table
2. Error reason captured: `missing_required_field`, `invalid_format`, `duplicate_key`, `referential_integrity`
3. File moved to error bucket: `gs://error-bucket/customers/YYYYMMDD/`
4. Alert sent to monitoring system
5. No partial loads into production table

---

## 3️⃣ BRANCHES CSV FORMAT

### Purpose
Branch location and operations master data. Each row represents a physical branch with staffing and operational info.

### File Naming Convention
```
branches_YYYYMMDD_HHMMSS.csv
branches_20250115_080000.csv
```

### CSV Structure

#### Header Row
```
run_id,processed_timestamp,source_file,branch_code,branch_name,region,state,city,zip_code,manager_name,opened_date,employee_count
```

#### Column Specifications

| Column | Type | Required | Format | Example | Notes |
|--------|------|----------|--------|---------|-------|
| `run_id` | String | ❌ No | UUID or run timestamp | `run_20250115_080000` | Unique per pipeline run |
| `processed_timestamp` | DateTime | ❌ No | ISO 8601 | `2025-01-15T08:00:00Z` | Server timestamp |
| `source_file` | String | ❌ No | Filename | `BRANCH_MASTER_20250115.txt` | Original mainframe filename |
| `branch_code` | String | ✅ Yes | Alphanumeric, 1-10 chars | `BRANCH001` | Must be unique |
| `branch_name` | String | ❌ No | Text, max 100 chars | `NEW YORK MAIN BRANCH` | Full branch name |
| `region` | String | ❌ No | Text, max 50 chars | `Northeast` | Geographic region |
| `state` | String | ❌ No | Two-letter code | `NY` | US state abbreviation |
| `city` | String | ❌ No | Text, max 50 chars | `New York` | City name |
| `zip_code` | String | ❌ No | XXXXX or XXXXX-XXXX | `10001` | US ZIP code |
| `manager_name` | String | ❌ No | Text, max 100 chars | `JOHN MANAGER` | Branch manager name |
| `opened_date` | Date | ❌ No | YYYY-MM-DD | `1995-06-15` | Branch opening date |
| `employee_count` | Integer | ❌ No | Non-negative integer | `45` | Number of employees |

### Validation Rules

#### Required Field Rules
- `branch_code`: Must not be empty, must be unique within file

#### Format Validation
- `branch_code`: 1-10 chars, alphanumeric
- `branch_name`: If provided, max 100 chars
- `region`: If provided, max 50 chars
- `state`: If provided, must be 2-letter US state code
- `city`: If provided, max 50 chars
- `zip_code`: If provided, must match `XXXXX` or `XXXXX-XXXX` pattern
- `manager_name`: If provided, max 100 chars
- `opened_date`: If provided, must be valid date (YYYY-MM-DD)
- `employee_count`: If provided, must be non-negative integer

#### Value Constraints
- Row count per file: 1 to 10,000 records (plus header)
- File size: max 50 MB
- No duplicate branch_code values
- State codes: Valid 2-letter US state abbreviations
- Employee count: 0 to 1,000,000
- No null bytes
- No control characters (except CRLF)

### Valid State Codes
```
AL, AK, AZ, AR, CA, CO, CT, DE, FL, GA, HI, ID, IL, IN, IA, KS, KY, LA, ME, MD,
MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC,
SD, TN, TX, UT, VT, VA, WA, WV, WI, WY, DC
```

### Sample Data

#### Valid Examples
```csv
run_id,processed_timestamp,source_file,branch_code,branch_name,region,state,city,zip_code,manager_name,opened_date,employee_count
run_20250115_080000,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH001,NEW YORK MAIN BRANCH,Northeast,NY,New York,10001,JOHN MANAGER,1995-06-15,45
run_20250115_080000,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH002,,West,CA,San Francisco,94105,,2000-01-01,32
run_20250115_080000,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH003,CHICAGO BRANCH,Midwest,IL,Chicago,60601,JANE DOE,,
```

#### Invalid Examples
```csv
# Missing branch_code (INVALID - required field)
run_20250115,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,,NEW YORK BRANCH,Northeast,NY,New York,10001,JOHN,1995-06-15,45

# Invalid state code (INVALID - must be 2-letter US state)
run_20250115,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH001,NEW YORK BRANCH,Northeast,NEW,New York,10001,JOHN,1995-06-15,45

# Invalid ZIP code format (INVALID - must be XXXXX or XXXXX-XXXX)
run_20250115,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH001,NEW YORK BRANCH,Northeast,NY,New York,1001,JOHN,1995-06-15,45

# Negative employee count (INVALID - must be non-negative)
run_20250115,2025-01-15T08:00:00Z,BRANCH_MASTER.txt,BRANCH001,NEW YORK BRANCH,Northeast,NY,New York,10001,JOHN,1995-06-15,-5
```

### Processing Pipeline

```
Input File (branches_*.csv)
    ↓
FileValidator.validate_csv_format()
    ↓
FileValidator.validate_encoding()
    ↓
Required Field Check (branch_code)
    ↓
Format Validation (state codes, ZIP codes, dates)
    ↓
Duplicate Check (branch_code uniqueness)
    ↓
BigQuery Load (branches_raw table)
    ↓
FileArchiver.archive_file()
```

### Error Handling

When validation fails:
1. Record rejected, logged in `branches_errors` table (if created)
2. Error reason captured: `missing_required_field`, `invalid_format`, `duplicate_key`, `invalid_state_code`
3. File moved to error bucket: `gs://error-bucket/branches/YYYYMMDD/`
4. Alert sent to monitoring system
5. No partial loads into production table

---

## 4️⃣ COLLATERAL CSV FORMAT

### Purpose
Collateral asset records linked to applications. Each row represents an asset used to secure a loan.

### File Naming Convention
```
collateral_YYYYMMDD_HHMMSS.csv
collateral_20250105_162030.csv
```

### CSV Structure

#### Header Row
```
run_id,processed_timestamp,source_file,collateral_id,application_id,collateral_type,collateral_value,appraisal_date,appraiser_name,account_number,branch_code
```

#### Column Specifications

| Column | Type | Required | Format | Example | Notes |
|--------|------|----------|--------|---------|-------|
| `run_id` | String | ❌ No | UUID or run timestamp | `run_20250105_162030` | Unique per pipeline run |
| `processed_timestamp` | DateTime | ❌ No | ISO 8601 | `2025-01-05T16:20:30Z` | Server timestamp |
| `source_file` | String | ❌ No | Filename | `COLL_EXTRACT_20250105.txt` | Original mainframe filename |
| `collateral_id` | String | ✅ Yes | Alphanumeric, 1-20 chars | `COLL123456789` | Must be unique |
| `application_id` | String | ❌ No | Alphanumeric, 1-20 chars | `APP123456789` | Reference to applications |
| `collateral_type` | String | ❌ No | PROPERTY, VEHICLE, SECURITIES | `PROPERTY` | Normalized values only |
| `collateral_value` | Integer | ❌ No | Whole dollars | `450000` | Appraised value |
| `appraisal_date` | Date | ❌ No | YYYY-MM-DD | `2024-12-01` | Appraisal/valuation date |
| `appraiser_name` | String | ❌ No | Text, max 100 chars | `ABC APPRAISALS INC` | Appraiser/company name |
| `account_number` | String | ❌ No | Numeric/alphanumeric, 1-20 | `123456789` | Related account number |
| `branch_code` | String | ❌ No | Code, 1-10 chars | `BRANCH001` | Processing branch code |

### Validation Rules

#### Required Field Rules
- `collateral_id`: Must not be empty, must be unique within file

#### Format Validation
- `collateral_id`: 1-20 chars, alphanumeric
- `application_id`: If provided, 1-20 chars, alphanumeric
- `collateral_type`: If provided, must be one of: PROPERTY, VEHICLE, SECURITIES
- `collateral_value`: If provided, must be integer ≥ 0
- `appraisal_date`: If provided, must be valid date (YYYY-MM-DD)
- `appraiser_name`: If provided, max 100 chars
- `account_number`: If provided, 1-20 chars, numeric or alphanumeric
- `branch_code`: If provided, must exist in branches table (validated externally)

#### Value Constraints
- Row count per file: 1 to 100,000 records (plus header)
- File size: max 500 MB
- No duplicate collateral_id values
- Collateral value: $0 to $100,000,000
- No null bytes
- No control characters (except CRLF)

### Sample Data

#### Valid Examples
```csv
run_id,processed_timestamp,source_file,collateral_id,application_id,collateral_type,collateral_value,appraisal_date,appraiser_name,account_number,branch_code
run_20250105_162030,2025-01-05T16:20:30Z,COLL_EXTRACT_20250105.txt,COLL123456789,APP123456789,PROPERTY,450000,2024-12-01,ABC APPRAISALS INC,123456789,BRANCH001
run_20250105_162030,2025-01-05T16:20:30Z,COLL_EXTRACT_20250105.txt,COLL987654321,,VEHICLE,35000,2024-11-15,,999888777,BRANCH002
run_20250105_162030,2025-01-05T16:20:30Z,COLL_EXTRACT_20250105.txt,COLL555555555,APP987654321,SECURITIES,250000,,,555444333,
```

#### Invalid Examples
```csv
# Missing collateral_id (INVALID - required field)
run_20250105,2025-01-05T16:20:30Z,COLL_EXTRACT.txt,,APP123456789,PROPERTY,450000,2024-12-01,ABC APPRAISALS,123456789,BRANCH001

# Invalid collateral_type (INVALID - must be PROPERTY, VEHICLE, or SECURITIES)
run_20250105,2025-01-05T16:20:30Z,COLL_EXTRACT.txt,COLL123456789,APP123456789,INVALID_TYPE,450000,2024-12-01,ABC APPRAISALS,123456789,BRANCH001

# Negative collateral value (INVALID - must be non-negative)
run_20250105,2025-01-05T16:20:30Z,COLL_EXTRACT.txt,COLL123456789,APP123456789,PROPERTY,-450000,2024-12-01,ABC APPRAISALS,123456789,BRANCH001

# Invalid appraisal date format (INVALID - must be YYYY-MM-DD)
run_20250105,2025-01-05T16:20:30Z,COLL_EXTRACT.txt,COLL123456789,APP123456789,PROPERTY,450000,12/01/2024,ABC APPRAISALS,123456789,BRANCH001
```

### Processing Pipeline

```
Input File (collateral_*.csv)
    ↓
FileValidator.validate_csv_format()
    ↓
FileValidator.validate_encoding()
    ↓
Required Field Check (collateral_id)
    ↓
Format Validation (collateral_type, values, dates)
    ↓
Duplicate Check (collateral_id uniqueness)
    ↓
Referential Integrity (application_id, branch_code)
    ↓
BigQuery Load (collateral_raw table)
    ↓
FileArchiver.archive_file()
```

### Error Handling

When validation fails:
1. Record rejected, logged in `collateral_errors` table (if created)
2. Error reason captured: `missing_required_field`, `invalid_format`, `duplicate_key`, `referential_integrity`
3. File moved to error bucket: `gs://error-bucket/collateral/YYYYMMDD/`
4. Alert sent to monitoring system
5. No partial loads into production table

---

## 📋 COMMON VALIDATION RULES

### Encoding & Character Set

All files must:
- ✅ Use UTF-8 encoding (no BOM)
- ✅ Contain no null bytes (`\x00`)
- ✅ Contain no non-printable control characters (except CRLF)
- ✅ Use consistent line endings (CRLF: `\r\n`)

### CSV Format Requirements

1. **Delimiter**: Comma (`,`) only
   ```
   ✅ CORRECT: field1,field2,field3
   ❌ WRONG: field1|field2|field3
   ❌ WRONG: field1;field2;field3
   ```

2. **Field Enclosure**: Double quotes (`"`) for fields containing:
   - Commas: `"field, with comma"`
   - Quotes: `"field with ""quoted"" text"`
   - Newlines: `"field with newline"`
   ```
   ✅ CORRECT: "field, with comma",normal_field
   ❌ WRONG: field, with comma,normal_field
   ```

3. **Header Row**: First row must be column names
   ```
   ✅ CORRECT: run_id,processed_timestamp,application_id
   ❌ WRONG: (missing header, starts with data)
   ❌ WRONG: # run_id,processed_timestamp,application_id (comment)
   ```

4. **Line Endings**: CRLF (`\r\n`) only
   ```
   ✅ CORRECT: field1,field2\r\nfield3,field4\r\n
   ❌ WRONG: field1,field2\nfield3,field4\n
   ```

5. **No Empty Rows**: No blank lines between data rows
   ```
   ✅ CORRECT:
   run_id,field2,field3
   value1,value2,value3
   value4,value5,value6
   
   ❌ WRONG:
   run_id,field2,field3
   value1,value2,value3
   
   value4,value5,value6
   ```

### Data Type Validation

#### String Fields
- Maximum length enforced (varies by field, specified in column specs)
- Trimmed of leading/trailing whitespace
- No control characters
- Special characters only as specified

#### DateTime Fields
- Format: ISO 8601 with timezone (`2025-01-01T14:30:22Z`)
- Timezone: Must include 'Z' for UTC or offset (+HH:MM or -HH:MM)
- Valid calendar date and time
- No fractional seconds

#### Date Fields
- Format: YYYY-MM-DD only
- Valid calendar date (no time component)
- Year: 1900-2100
- Month: 01-12
- Day: 01-31 (validated against month/year)

#### Integer Fields
- Whole numbers only
- No decimal points
- May be negative (if range allows)
- Range constraints enforced (e.g., credit_score 300-850)

#### Enum/Choice Fields
- Must be exact match to allowed values
- Case-sensitive
- No extra whitespace
- Example values: PROPERTY, VEHICLE, SECURITIES (collateral_type)

### Uniqueness Constraints

| Entity | Field | Constraint |
|--------|-------|-----------|
| Applications | `application_id` | Must be unique within file |
| Customers | `customer_id` | Must be unique within file |
| Branches | `branch_code` | Must be unique within file |
| Collateral | `collateral_id` | Must be unique within file |

**Implementation**: HashSet check during file validation. Duplicates trigger file rejection.

### Referential Integrity

| Field | References | Table | Resolution |
|-------|-----------|-------|-----------|
| Applications.`branch_code` | Branches.`branch_code` | branches_raw | External check (pre-existing data) |
| Customers.`branch_code` | Branches.`branch_code` | branches_raw | External check (pre-existing data) |
| Collateral.`application_id` | Applications.`application_id` | applications_raw | Same-batch or previous load check |
| Collateral.`branch_code` | Branches.`branch_code` | branches_raw | External check (pre-existing data) |

**Implementation**: 
- External references: Checked if data exists in BigQuery
- Same-batch references: Checked in memory during processing
- Missing references: Record marked as error, not loaded

### File Size & Record Count Limits

| Entity | Min Records | Max Records | Max File Size | Typical Size |
|--------|-------------|-------------|---------------|--------------|
| Applications | 1 | 100,000 | 500 MB | 50-100 MB |
| Customers | 1 | 500,000 | 2 GB | 500 MB-1 GB |
| Branches | 1 | 10,000 | 50 MB | 1-5 MB |
| Collateral | 1 | 100,000 | 500 MB | 50-100 MB |

**Rules**:
- Minimum: At least 1 data row (plus header)
- Maximum: Row and file size limits enforced
- Empty files rejected
- Oversized files trigger error and rejection

### PII (Personally Identifiable Information) Handling

#### Fields Containing PII
| Entity | Field | Handling |
|--------|-------|----------|
| Applications | `ssn` | Masked in logs, validated format |
| Customers | `ssn` | Masked in logs, validated format |
| Customers | `email` | Logged normally, validated format |
| Customers | `phone` | Logged normally, validated format |

#### Masking Rules
- SSN: Log as `XXX-XX-****` (last 4 visible)
- Email: Not masked (required for communications)
- Phone: Not masked (required for communications)

#### Validation (No Modification)
- No alteration of original values
- Format validation only (pattern matching)
- Range validation for credit scores
- Masking applied only in logs/monitoring, not in data storage

---

## 🔍 VALIDATION IMPLEMENTATION CHECKLIST

### File-Level Checks
- [ ] File exists in GCS
- [ ] File not empty
- [ ] File encoding is UTF-8
- [ ] File size within limits
- [ ] No null bytes
- [ ] Line ending is CRLF
- [ ] Header row matches expected columns
- [ ] Column count consistent across rows

### Row-Level Checks
- [ ] Required fields not empty
- [ ] String fields within max length
- [ ] DateTime fields valid ISO 8601
- [ ] Date fields valid YYYY-MM-DD
- [ ] Integer fields are whole numbers
- [ ] Enum fields match allowed values
- [ ] Range constraints met

### Data-Level Checks
- [ ] No duplicate unique key values
- [ ] SSN format valid (if provided): `XXX-XX-XXXX`
- [ ] Email format valid (if provided): contains `@`
- [ ] Phone format valid (if provided): `XXX-XXX-XXXX` or `+1XXX`
- [ ] Credit scores in range [300, 850]
- [ ] State codes are valid US states
- [ ] ZIP codes valid format
- [ ] Dates are realistic (not future, not too old)
- [ ] Loan amounts are reasonable ($0-$10M)
- [ ] Employee counts reasonable (0-1M)
- [ ] Collateral values reasonable ($0-$100M)

### Referential Integrity Checks
- [ ] Referenced branch codes exist (for Applications, Customers, Collateral)
- [ ] Referenced application IDs exist (for Collateral)

---

## 📊 EXAMPLE VALIDATION REPORT

When processing `applications_20250101_143022.csv`:

```
File Validation Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
File: applications_20250101_143022.csv
Entity: Applications
Timestamp: 2025-01-01T14:30:22Z
Status: ✅ PASSED

File-Level Validation:
  ✅ File exists in GCS
  ✅ File size: 45.3 MB (within 500 MB limit)
  ✅ Encoding: UTF-8
  ✅ No null bytes detected
  ✅ Line endings: CRLF
  ✅ Header matches schema (10 columns)
  ✅ All rows have consistent column count

Data-Level Validation:
  ✅ Total records: 2,450
  ✅ Required fields complete: 2,450/2,450 (100%)
  ✅ Format validation passed: 2,450/2,450 (100%)
  ✅ No duplicate application_ids
  ✅ Branch code references: 2,430/2,430 valid (100%)
  ⚠️  Missing branch codes: 20 records (will be loaded as-is)
  
Records Processed:
  ✅ Loaded: 2,450
  ❌ Rejected: 0
  ⚠️  Warnings: 0

Summary:
  Status: READY FOR LOAD
  Destination: gs://prod-bucket/applications_raw
  Archive: gs://archive-bucket/applications/2025-01-01/
  Duration: 12.3 seconds
```

---

## 🚀 NEXT STEPS

1. **Phase 3, Component 3**: Implement `test_io_utils.py`
   - Unit tests for FileValidator
   - Unit tests for FileArchiver
   - Unit tests for FileMetadataExtractor
   - Unit tests for FileLifecycleManager

2. **Phase 3, Component 4**: Implement `test_data_factory.py`
   - Fixtures for all 4 entity types
   - Sample data generators
   - Edge case generators

3. **Phase 3, Component 5**: Implement `test_pipeline_end_to_end.py`
   - Full pipeline integration tests
   - Real file processing
   - Error scenario tests

---

## 📝 VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-21 | Initial specification with 4 entity types |

---

**Last Reviewed:** December 21, 2025  
**Status:** ✅ Production Ready  
**Reviewed By:** Architecture Team  
**Approved For:** Phase 3 Implementation

