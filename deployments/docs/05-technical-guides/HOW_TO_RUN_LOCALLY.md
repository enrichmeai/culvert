# 🚀 HOW TO RUN LOA LOCALLY - STEP BY STEP

**Time Required**: 5 minutes  
**Cost**: $0  
**Difficulty**: Easy - just copy & paste commands  

---

## 📋 WHAT YOU'LL DO

1. Open Terminal
2. Navigate to project
3. Run test
4. See results in ~2 seconds
5. Understand the output

---

## 🎯 METHOD 1: QUICKEST WAY (Copy & Paste)

### Step 1: Open Terminal
- On Mac: Press `Cmd + Space`, type "Terminal", press Enter
- Or: Applications → Utilities → Terminal

### Step 2: Copy This Entire Command

```bash
cd /path/to/project && python3 test_loa_local.py
```

### Step 3: Paste in Terminal
- Right-click in Terminal → Paste
- Or: Cmd + V

### Step 4: Press Enter
- Watch the output scroll
- Takes about 2-3 seconds

### Step 5: Review Output
- See the LOA test results
- Understand validation
- Read the summary

---

## 🎯 METHOD 2: STEP BY STEP (If you prefer)

### Step 1: Open Terminal
```
Terminal → Applications → Utilities → Terminal
```

### Step 2: Navigate to Project
```bash
cd /path/to/project
```

Press Enter. You should see:
```
yourname@computer legacy-migration-reference %
```

### Step 3: Verify You're in Right Location
```bash
pwd
```

Should show:
```
/path/to/project
```

### Step 4: Check Python is Available
```bash
python3 --version
```

Should show something like:
```
Python 3.9.x or higher
```

### Step 5: Run the Test
```bash
python3 test_loa_local.py
```

### Step 6: Wait for Results
- Takes 2-3 seconds
- You'll see lots of output
- Read through it carefully

---

## 🎯 METHOD 3: USING THE SCRIPT (Automated)

### Step 1: Make Script Executable
```bash
chmod +x /path/to/project/run_local_test.sh
```

### Step 2: Run the Script
```bash
/path/to/project/run_local_test.sh
```

The script will:
- Check Python is installed
- Navigate to the project
- Verify test file exists
- Run the test
- Show results

---

## 📊 WHAT YOU'LL SEE

When you run it, you'll see this appear:

```
======================================================================
              LOA BLUEPRINT - LOCAL TEST & DEPLOYMENT
======================================================================

📊 STEP 1: SAMPLE DATA
────────────────────────────────────────────────────────────────────
ID       SSN            Name            Amount    Type        Date
────────────────────────────────────────────────────────────────────
APP001   ***-**-6789    John Doe           $50000  MORTGAGE    2025-01-15
APP002   ***-**-7890    Jane Smith         $30000  PERSONAL    2025-01-14
APP003   ***-**-0000    Bad SSN            $25000  MORTGAGE    2025-01-13
APP004   ***-**-8901    Bob                 -$5000  MORTGAGE    2025-01-12
APP005   ***-**-9012    Alice              $75000  INVALID_TYP 2025-01-11

✅ Created 5 sample records (2 valid, 3 with errors)

📋 STEP 2: VALIDATION RULES
────────────────────────────────────────────────────────────────────

SSN:
  • Must be 9 digits (XXX-XX-XXXX)
  • Cannot be all zeros or same digit
  • Area number (first 3) cannot be 000, 666, or 900-999

[... more rules ...]

⚙️ STEP 3: VALIDATION RESULTS
────────────────────────────────────────────────────────────────────

✅ VALID APP001
  → Ready for BigQuery

✅ VALID APP002
  → Ready for BigQuery

❌ FAILED APP003
  ❌ SSN: Cannot be all zeros or same digit

❌ FAILED APP004
  ❌ Loan Amount: Must be >= $1

❌ FAILED APP005
  ❌ Loan Type: Must be one of: MORTGAGE, PERSONAL, AUTO, HOME_EQUITY

[... more output ...]

✅ LOCAL TEST COMPLETE!
```

---

## ✅ TROUBLESHOOTING

### Problem: "command not found: python3"
**Solution**: 
- Install Python: https://www.python.org/downloads/
- Or use: `python test_loa_local.py` (without the 3)
- Or verify path: `which python3`

### Problem: "No such file or directory: test_loa_local.py"
**Solution**:
- Make sure you're in the right directory: `pwd`
- Should show: `/path/to/project`
- Navigate there first: `cd /path/to/project`

### Problem: "Permission denied"
**Solution**:
- For script: `chmod +x run_local_test.sh`
- Then run: `./run_local_test.sh`

### Problem: Nothing happens / blank output
**Solution**:
- Python might be buffering output
- Try: `python3 -u test_loa_local.py`
- Or wait 5 seconds for output

---

## 📱 COPY-PASTE QUICK COMMANDS

### Just Want to Run It Fast?

**For Mac Terminal:**
```
cd /path/to/project && python3 test_loa_local.py
```

Copy entire line above, paste in Terminal, press Enter. Done!

### Alternative (if above doesn't work):
```
python3 /path/to/project/test_loa_local.py
```

---

## 📖 UNDERSTANDING THE OUTPUT

When the test runs, it shows 6 main sections:

### 1. SAMPLE DATA
Shows 5 test records with their fields marked ✅ or ❌

### 2. VALIDATION RULES
Explains what rules each field must follow

### 3. VALIDATION RESULTS
Shows which records passed and which failed with reasons

### 4. BIGQUERY SCHEMA
Shows the 10 fields that will be in BigQuery

### 5. DATA FLOW
Shows where data goes (valid → raw table, invalid → error table)

### 6. METRICS
Shows performance: 5 records processed, 40% valid, $0 cost

---

## ✨ WHAT HAPPENS NEXT

After you run the test:

1. **Review the output** (5 minutes)
   - Read why each record passed/failed
   - Understand the validation rules
   - See the data flow

2. **Read the guide** (15 minutes)
   - Open: `LOCAL_DEPLOYMENT_GUIDE.md`
   - Understand the code patterns
   - Learn how it works

3. **Study the code** (30 minutes)
   - Open: `loa_common/validation.py`
   - Open: `loa_common/schema.py`
   - Read through the modules

4. **Ready for next step** (1 week)
   - Deploy to GCP
   - Test with real data
   - Optimize and scale

---

## 🎯 QUICK REFERENCE

| What | Command |
|------|---------|
| Navigate | `cd /path/to/project` |
| Run test | `python3 test_loa_local.py` |
| Check Python | `python3 --version` |
| See location | `pwd` |
| List files | `ls` |
| Run script | `bash run_local_test.sh` |

---

## 🚀 RIGHT NOW

### Copy this command:
```
cd /path/to/project && python3 test_loa_local.py
```

### Paste in Terminal, press Enter

### See results in 2-3 seconds

### Read the output

### Done! ✅

---

## 💡 TIPS

- **First time?** Use Method 1 (copy & paste)
- **Like to understand?** Use Method 2 (step by step)
- **Want automation?** Use Method 3 (script)
- **Stuck?** Check troubleshooting section above
- **Questions?** Read LOCAL_DEPLOYMENT_GUIDE.md

---

## ✅ SUCCESS = 

You'll know it worked when:
- Command runs without errors
- You see lots of output
- Test results displayed
- Shows "✅ LOCAL TEST COMPLETE!"

---

**That's it! Simple as that.** 

Run the command, see the results, understand the system. 

You've got this! 🚀

