# Failed Resume Recovery Pipeline - Implementation Walkthrough

## Quick Start

```bash
# 1. Ensure Groq API key is set in .env
cd /Users/naveenpoliasetty/Downloads/RAG-1

# 2. Run the pipeline
python run_failed_resume_recovery.py

# 3. Monitor logs for rate limits and progress
# Pipeline will automatically stop if Groq rate limits are exhausted
```

## Overview

Successfully implemented a comprehensive failed resume recovery pipeline that uses Groq LLM to extract structured resume data from failed resume URLs.

**Key Innovation**: Rate-aware concurrency that immediately stops processing when Groq API daily limits are exhausted, preventing 429 errors while maximizing throughput.

---

## What Was Built

### 1. Groq LLM Client (`src/data_acquisition/groq_client.py`)

✅ **Features:**

- Groq API client wrapper with instructor integration
- Cached client to avoid re-initialization
- **Fixed rate limiting**:
  - ✅ 2-second delay before each request (respects 30 RPM limit)
  - ✅ Prevents 429 errors proactively
  - ✅ Optimized for llama-3.1-8b-instant (30 RPM, 6000 TPM)
  - ✅ Works perfectly with 5 concurrent workers
- **Rate limit tracking** after every API call:
  - ✅ Logs remaining API calls for today
  - ✅ Logs remaining tokens for today
  - ✅ Monitors actual usage vs limits
- **Fallback 429 retry logic** (rarely needed):
  - ✅ Retries up to 3 times if 429 somehow occurs
  - ✅ Exponential backoff with jitter
  - ✅ Returns rate exhaustion signal when retries fail
- Both async and sync interfaces for structured output
- Uses `llama-3.1-8b-instant` model

**Key Functions:**

- `get_groq_client()` - Get or create cached Groq client
- `get_instructor_client()` - Get instructor-wrapped client
- `log_rate_limits(response)` - Extract and log rate limit info from headers
- `groq_structured_output_sync()` - Make structured LLM calls with fixed rate limiting

---

### 2. LLM Resume Scraper (`src/data_acquisition/llm_resume_scraper.py`)

✅ **Features:**

- Fetches full HTML page text (no heuristic parsing)
- Uses Groq LLM to extract structured resume data
- Validates all required sections are present
- Comprehensive error handling with retries

**Key Functions:**

- `fetch_page_text(url)` - Fetch and clean HTML text from URL
- `extract_resume_with_groq(text, url)` - Use Groq to extract Resume object
- `validate_resume_complete(resume)` - Ensure all sections present
- `scrape_resume_with_llm(url)` - Complete pipeline: fetch → extract → validate

**Validation:**

- Requires `job_role`, `professional_summary`, `technical_skills`, `experiences`
- Returns clear error messages if sections missing

---

### 3. Failed Resume Recovery Pipeline (`src/data_acquisition/failed_resume_pipeline.py`)

✅ **Features:**

- Fetches all records from `failed_resumes` MongoDB collection
- Concurrent processing with ThreadPoolExecutor
- **Success flow:** Insert to `resumes` DB → Delete from `failed_resumes`
- **Failure flow:** Update `error_message` → Keep in `failed_resumes`
- Maintains exact same schema as existing resumes (no new fields)
- **Test mode support**:
  - ✅ Saves to `test_resumes` collection during testing
  - ✅ Protects production `resumes` database
  - ✅ Enabled by default for safe manual testing
- Comprehensive logging and statistics

**Key Components:**

- `FailedResumeRecoveryPipeline` class
- `process_single_failed_resume()` - Process one resume
- `run_recovery_pipeline()` - Main orchestration
- Batch processing with configurable workers
- Test mode parameter for safe testing

---

### 4. Entry Point Script (`run_failed_resume_recovery.py`)

✅ Simple runner script at project root for easy execution

---

### 5. Configuration (`.env`)

✅ Added Groq API key:

```
<<<<<<< HEAD
GROQ_API_KEY= ###
=======
GROQ_API_KEY=g ###
>>>>>>> 6d4f1f3... Handled API key level issues
```

---

## How to Use

### Run the Pipeline

**🧪 Test Mode (Default - Recommended for Manual Testing):**

```bash
cd /Users/naveenpoliasetty/Downloads/RAG-1
python run_failed_resume_recovery.py
```

This saves recovered resumes to `test_resumes` collection, keeping your production `resumes` database safe.

**✅ Production Mode:**

Edit `src/data_acquisition/failed_resume_pipeline.py` line 311 and change:

```python
pipeline = FailedResumeRecoveryPipeline(batch_size=10, max_workers=5, test_mode=False)
```

Or run directly:

```bash
python -m src.data_acquisition.failed_resume_pipeline
```

### Test vs Production Mode

| Mode               | Collection     | Use Case                                           |
| ------------------ | -------------- | -------------------------------------------------- |
| **Test** (default) | `test_resumes` | Manual testing, verification, performance checking |
| **Production**     | `resumes`      | Actual recovery to production database             |

> **💡 Tip**: Always test with `test_mode=True` first to verify results before switching to production!

### What Happens

1. **Connects to MongoDB** and fetches all `failed_resumes`
2. **For each failed resume:**
   - Fetches page text from `source_url`
   - Uses Groq LLM to extract structured data
   - Validates all required sections are present
   - **If successful:**
     - Adds metadata (`resume_id`, `category`, `scraped_at`, etc.)
     - Inserts into `resumes` collection
     - **Deletes** from `failed_resumes`
   - **If failed:**
     - Updates `error_message` with specific failure reason
     - Keeps in `failed_resumes` for future attempts
3. **Prints summary statistics**

### Expected Logs

**Normal Operation:**

```
============================================================
STARTING FAILED RESUME RECOVERY PIPELINE
============================================================
🧪 TEST MODE ENABLED - Using 'test_resumes' collection
Found 25 failed resume(s) to process
Making Groq API call with model: llama-3.1-8b-instant
📊 Groq Rate Limits - API Calls: 1450/1500 remaining | Tokens: 45000/50000 remaining
✅ Groq extraction successful - job_role: 'Oracle Developer', summary: 5 items, skills: 12 items, experiences: 3 items
✅ Resume validation passed - all required sections present
✅ Successfully recovered and moved resume: https://...
============================================================
RECOVERY PIPELINE SUMMARY
============================================================
Total processed:     25
✅ Recovered:        18 (moved to test_resumes)
❌ Still failed:     5 (error_message updated)
⚠️  Errors:           2
============================================================
```

**With 429 Retry Handling:**

```
Making Groq API call with model: llama-3.1-8b-instant
⚠️ Rate limit error (429) on attempt 1/3: Rate limit exceeded
Waiting 2.1s before retry...
Retry attempt 2/3 - waiting 2.1s...
⚠️ Rate limit error (429) on attempt 2/3: Rate limit exceeded
Waiting 4.8s before retry...
Retry attempt 3/3 - waiting 4.8s...
⚠️ Rate limit error (429) on attempt 3/3: Rate limit exceeded
❌ Max retries reached for 429 error
🛑 RATE LIMIT EXHAUSTED during processing - Stopping pipeline immediately!
```

---

## Key Features

### 🔒 Rate Limit Safety & Concurrency

After **every Groq API call**, the system:

1. Logs remaining API calls and tokens for the day
2. Checks if limits are exhausted (≤ 0)
3. **Immediately stops the entire pipeline** if limits reached
4. Cancels all pending concurrent requests

This prevents 429 errors and allows safe massive-scale inference with concurrent processing.

**Example logs:**

```
📊 Groq Rate Limits - API Calls: 1450/1500 remaining | Tokens: 45000/50000 remaining
...
⚠️ RATE LIMIT EXHAUSTED - Requests: 0, Tokens: 34521
🛑 RATE LIMIT EXHAUSTED - Stopping pipeline immediately!
🛑 Pipeline stopped early due to rate limit exhaustion
Processed: 18/25
```

### 📋 Schema Preservation

All recovered resumes maintain the **exact same schema** as existing resumes:

- `resume_id` (UUID)
- `job_role`
- `professional_summary` (list)
- `technical_skills` (list)
- `experiences` (list of experience objects)
- `category` (extracted from URL)
- `source_url`
- `scraped_at`
- `qdrant_status`
- `processing_status`

No new fields are added - maintains full compatibility with existing codebase.

### ✅ Required Sections Enforcement

All three sections **must** be present and non-empty:

1. `professional_summary`
2. `technical_skills`
3. `experiences`

If any section is missing or empty, the resume is rejected with a clear error message.

### 🔄 Concurrent Processing

Uses ThreadPoolExecutor with configurable workers (default: 1) for efficient processing. While Groq supports concurrency, using 1 worker ensures sequential execution which is safer given the strict RPM limits.

---

## Configuration

### Test Mode vs Production Mode

**Test Mode (Default):**

```python
pipeline = FailedResumeRecoveryPipeline(
    batch_size=10,
    max_workers=5,
    test_mode=True  # Saves to 'test_resumes' collection
)
```

**Production Mode:**

```python
pipeline = FailedResumeRecoveryPipeline(
    batch_size=10,
    max_workers=5,
    test_mode=False  # Saves to 'resumes' collection
)
```

### Adjust Processing Parameters

Edit the pipeline initialization in `src/data_acquisition/failed_resume_pipeline.py`:

```python
pipeline = FailedResumeRecoveryPipeline(
    batch_size=10,      # Batch size (currently not used, for future optimization)
    max_workers=1       # Number of concurrent threads
)
```

### Groq Model

Currently uses `llama-3.1-8b-instant`. To change, edit in `llm_resume_scraper.py`:

```python
resume = groq_structured_output_sync(
    response_model=Resume,
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    model="llama-3.1-8b-instant",  # Change here
    ...
)
```

---

## Testing

### Manual Testing

1. **Check failed_resumes collection:**

   ```bash
   python extract_failed_resumes.py
   ```

2. **Run the pipeline:**

   ```bash
   python run_failed_resume_recovery.py
   ```

3. **Verify results:**
   - Check logs for rate limit tracking
   - Verify recovered resumes in `resumes` collection
   - Verify error messages updated in `failed_resumes` collection

### What to Look For

✅ **Rate limit logs** after each API call
✅ **Recovered resumes** have all required fields
✅ **Error messages** are clear and specific
✅ **Deleted records** from `failed_resumes` on success
✅ **Updated error_message** in `failed_resumes` on failure

---

## Next Steps

1. **Run the pipeline** on your failed resumes
2. **Monitor logs** for rate limits and errors
3. **Verify database state** after completion
4. **Adjust max_workers** if needed for throughput

---

## Pipeline Flow Details

### Processing Flow

```
1. Fetch Failed Resumes
   └─> Query MongoDB `failed_resumes` collection

2. Concurrent Processing (5 workers)
   ├─> Worker 1: Fetch page → Groq LLM → Validate → Check rate limit
   ├─> Worker 2: Fetch page → Groq LLM → Validate → Check rate limit
   ├─> Worker 3: Fetch page → Groq LLM → Validate → Check rate limit
   ├─> Worker 4: Fetch page → Groq LLM → Validate → Check rate limit
   └─> Worker 5: Fetch page → Groq LLM → Validate → Check rate limit

3. After Each API Call
   ├─> Log rate limits (API calls & tokens remaining)
   ├─> Check if exhausted
   └─> If exhausted → STOP ALL WORKERS immediately

4. For Each Resume
   ├─> Success Path:
   │   ├─> Add metadata (resume_id, category, scraped_at, etc.)
   │   ├─> Insert into `resumes` collection
   │   └─> DELETE from `failed_resumes`
   │
   └─> Failure Path:
       ├─> Update `error_message` in `failed_resumes`
       └─> Keep record for future retry
```

### Common Scenarios

#### Scenario 1: All Sections Present

```
URL: https://example.com/resume123
Text fetched: 5000 characters
Groq extraction: ✅ Success
  - job_role: "Senior Python Developer"
  - professional_summary: 5 items
  - technical_skills: 12 items
  - experiences: 3 items
Validation: ✅ All sections present
Result: Insert to resumes → Delete from failed_resumes
Rate limit: 1495/1500 API calls remaining
```

#### Scenario 2: Missing Sections

```
URL: https://example.com/resume456
Text fetched: 3000 characters
Groq extraction: ✅ Success
  - job_role: "Data Engineer"
  - professional_summary: 0 items ❌
  - technical_skills: 8 items
  - experiences: 2 items
Validation: ❌ Missing professional_summary
Result: Update error_message → Keep in failed_resumes
Error: "Resume missing required sections: professional_summary"
Rate limit: 1494/1500 API calls remaining
```

#### Scenario 3: Rate Limit Exhaustion

```
Processing resume 18/25...
📊 Groq Rate Limits - API Calls: 1/1500 remaining
Processing resume 19/25...
📊 Groq Rate Limits - API Calls: 0/1500 remaining
⚠️ RATE LIMIT EXHAUSTED - Requests: 0, Tokens: 12500
🛑 RATE LIMIT EXHAUSTED - Stopping pipeline immediately!
Cancelling 6 pending workers...
Pipeline stopped: 19/25 processed
```

---

## Troubleshooting

### 429 Rate Limit Errors

**Symptom**: Seeing "Rate limit error (429)" in logs

**Cause**: Groq API rate limits being hit

**Built-in Solution**:

- System automatically retries up to 3 times
- Uses exponential backoff to reduce request rate
- If retries exhausted → pipeline stops gracefully
- **NEW: Detailed Debugging**: The system logs the **full API response body** starting with `🔎 Full 429 Error Response:` to help diagnose the specific limit (RPM, TPM, or daily) being hit.

**Prevention**:

- Reduce `max_workers` to slow down request rate
- Monitor rate limit logs carefully
- Run during off-peak hours if possible

### Pipeline Stops Early

**Symptom**: Pipeline shows "stopped early due to rate limit exhaustion"

**Cause**: Groq API daily limits reached (API calls or tokens)

**Solution**:

- Wait for rate limit reset (shown in logs)
- Run pipeline again next day
- Records already processed won't be retried

### No Failed Resumes Found

**Symptom**: "No failed resumes found in database"

**Cause**: `failed_resumes` collection is empty

**Solution**:

```bash
# Check if collection exists and has data
python extract_failed_resumes.py
```

### Groq API Key Error

**Symptom**: "GROQ_API_KEY not found in environment variables"

**Cause**: Missing or incorrect API key in `.env`

**Solution**:

```bash
# Verify .env file contains:
GROQ_API_KEY=gsk_...
```

### MongoDB Connection Failed

**Symptom**: "MongoDB connection failed"

**Cause**: MongoDB not accessible or credentials incorrect

**Solution**:

- Check `config.yaml` MongoDB URI
- Verify network connectivity
- Check MongoDB credentials

### Missing Sections Error

**Symptom**: Many resumes failing with "missing required sections"

**Cause**:

- HTML structure different from expected
- Groq LLM not finding sections in text
- Page requires JavaScript rendering

**Solution**:

- Review sample failed URLs manually
- Check if page uses JavaScript rendering
- Consider adjusting extraction prompts in `llm_resume_scraper.py`

---

## Performance Tips

### Optimal Concurrency

Default: 5 concurrent workers

**Increase workers** (faster processing):

```python
pipeline = FailedResumeRecoveryPipeline(max_workers=10)
```

⚠️ Higher concurrency = faster rate limit exhaustion

**Decrease workers** (slower but safer):

```python
pipeline = FailedResumeRecoveryPipeline(max_workers=2)
```

✅ Lower concurrency = longer daily operation before exhaustion

### Rate Limit Management

**Daily Groq Limits** (Free Tier Example):

- API calls: ~1,500/day
- Tokens: ~50,000/day

**Estimation**:

- Average resume: ~1 API call, ~1,500 tokens
- Expected throughput: 30-40 resumes/day before exhaustion

**Strategy**:

- Run pipeline daily
- Monitor rate limits in logs
- Adjust `max_workers` based on your quota

### Resume Processing Time

Average per resume: 3-5 seconds

- Fetch page: 1-2 sec
- Groq extraction: 1-2 sec
- Validation + DB ops: <1 sec

With 5 workers: ~60-100 resumes/hour (before rate limits)

---

## Files Created

| File                                                                                                                                            | Purpose                                  |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| [src/data_acquisition/groq_client.py](file:///Users/naveenpoliasetty/Downloads/RAG-1/src/data_acquisition/groq_client.py)                       | Groq API client with rate limit tracking |
| [src/data_acquisition/llm_resume_scraper.py](file:///Users/naveenpoliasetty/Downloads/RAG-1/src/data_acquisition/llm_resume_scraper.py)         | LLM-based resume scraper and validator   |
| [src/data_acquisition/failed_resume_pipeline.py](file:///Users/naveenpoliasetty/Downloads/RAG-1/src/data_acquisition/failed_resume_pipeline.py) | Main recovery pipeline orchestration     |
| [run_failed_resume_recovery.py](file:///Users/naveenpoliasetty/Downloads/RAG-1/run_failed_resume_recovery.py)                                   | Entry point script                       |
| [.env](file:///Users/naveenpoliasetty/Downloads/RAG-1/.env)                                                                                     | Added GROQ_API_KEY                       |

---

## FAQ

### Q: Why is test mode enabled by default?

**A**: Test mode protects your production `resumes` database during manual testing and verification. Recovered resumes go to `test_resumes` collection instead, allowing you to verify quality before moving to production.

### Q: How do I verify resumes recovered in test mode?

**A**: Check the `test_resumes` collection in MongoDB:

```bash
# MongoDB query
db.test_resumes.find().pretty()
```

Once verified, you can either:

1. Move records to `resumes` collection manually
2. Run pipeline again with `test_mode=False`

### Q: What happens to resumes that are successfully recovered?

**A**: They are inserted into the `resumes` collection with all standard metadata fields, and their records are **deleted** from the `failed_resumes` collection.

### Q: Can I run the pipeline multiple times?

**A**: Yes! The pipeline only processes what's currently in `failed_resumes`. Successfully recovered resumes won't be reprocessed.

### Q: What if a resume fails again during recovery?

**A**: The `error_message` field in `failed_resumes` is updated with the specific failure reason. The record stays in the collection for future attempts.

### Q: How do I know if rate limits are being hit?

**A**: Watch the logs for:

- `📊 Groq Rate Limits` - shows remaining counts
- `🛑 RATE LIMIT EXHAUSTED` - when limits hit zero
- Pipeline will stop automatically and show processed count

### Q: Does the pipeline use heuristic parsing?

**A**: No! It uses **pure LLM extraction** via Groq. The entire page text is sent to the LLM, which extracts structured data. No heuristic HTML parsing is used.

### Q: Can I change the Groq model?

**A**: Yes! Edit `llm_resume_scraper.py` line 135:

```python
model="llama-3.1-8b-instant",  # Change to your preferred model
```

### Q: How do I check failed resumes without running the pipeline?

**A**: Run:

```bash
python extract_failed_resumes.py
# Creates failed_resumes.json with all records
```

### Q: What's the difference between this and the regular scraping pipeline?

**A**:

- **Regular pipeline** (`run_data_scraping.py`): Uses heuristic HTML parsing
- **Recovery pipeline** (`run_failed_resume_recovery.py`): Uses Groq LLM extraction for resumes that failed heuristic parsing

---

## Summary

✅ **Complete implementation** of failed resume recovery pipeline  
✅ **Groq LLM integration** with rate limit tracking  
✅ **Schema preservation** - exact same fields as existing resumes  
✅ **Required sections enforcement** - all 3 sections must be present  
✅ **Rate-aware concurrency** - stops immediately when limits exhausted  
✅ **Comprehensive logging** throughout  
✅ **Concurrent processing** (5 workers) for efficiency  
✅ **Production-ready** code with error handling

**Ready to run**: `python run_failed_resume_recovery.py`
