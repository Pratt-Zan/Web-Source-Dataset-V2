# Corporate Website Source Dataset Pipeline

> A scalable web crawling framework for discovering corporate website URLs and extracting textual content from S&P 500 companies.
>
> **Data Source**: WRDS (Wharton Research Data Services) — S&P 500 company identifiers and homepage URLs.
>
> **Pipeline**: 3 phases + parallel execution support.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Phase 0: Data Preparation](#phase-0-data-preparation)
4. [Phase 1: URL List Generation & Splitting](#phase-1-url-list-generation--splitting)
5. [Phase 2: Subdomain / Subpage URL Discovery](#phase-2-subdomain--subpage-url-discovery)
6. [Phase 3: Text Content Extraction](#phase-3-text-content-extraction)
7. [Supplementary Module: Parallel Execution Across Subfolders](#supplementary-module-parallel-execution-across-subfolders)
8. [Requirements & Installation](#requirements--installation)
9. [Usage Guide](#usage-guide)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This project implements a **three-phase web crawling pipeline** designed for financial/academic research. Starting from WRDS-provided company data, it:

1. **Prepares data** — Merges two WRDS CSVs (`current.csv` and `web.csv`) to create a unified company-to-URL mapping, then splits it into manageable chunks.
2. **Discovers URLs** — For each company homepage, performs a **BFS crawl** up to a configurable depth to discover all same-domain subpages and subdirectories.
3. **Extracts text** — Visits every discovered URL and extracts the **visible textual content** (via `document.body.innerText`), stripping away non-text resources (images, CSS, fonts, etc.).

The system is designed for **parallel execution** — the company set is divided into 50 subsets, each processed independently, allowing concurrent crawling across multiple browser windows or machines.

---

## Project Structure

```
.
├── check.ipynb                          # Jupyter: merge WRDS CSVs → export company_weburl.json
├── current.csv                          # WRDS: S&P 500 constituents (indexname, gvkey, tic, companyname)
├── web.csv                              # WRDS: company web URLs (gvkey, conm, tic, weburl, ...)
├── company_weburl.json                  # Merged output: 500 {companyname, weburl} records
│
├── python_code/
│   ├── folder_creation/
│   │   ├── split_company_json.py        # Split company_weburl.json → N=50 chunks
│   │   └── create_json_iter_folders.py  # Create json_iter/ subfolder in each chunk dir
│   │
│   ├── main_url.py                      # [Phase 2] Master: invoke URL discovery across sets
│   ├── iter_update_url.py               # [Phase 2] Core: BFS subpage URL discovery per company
│   │
│   ├── main_text.py                     # [Phase 3] Master: invoke text extraction across sets
│   ├── iter_update_text.py              # [Phase 3] Core: text extraction per URL per company
│   │
│   └── run_parallel.bat                 # [Supplementary] Batch: parallel text extraction
│
└── company_set/                         # Created by Phase 0 scripts
    ├── company_set_1/
    │   ├── company_1.json               #   10 company records (name + homepage URL)
    │   └── json_iter/                   #   Output directory for crawling results
    │
    ├── company_set_2/
    │   ├── company_2.json
    │   └── json_iter/
    │
    ├── ...
    │
    └── company_set_50/
        ├── company_50.json
        └── json_iter/
```

### Intermediate & Output Files

| File Pattern | Description | Produced By |
|---|---|---|
| `current.csv` | S&P 500 constituents (from WRDS) | WRDS download |
| `web.csv` | Company website URLs (from WRDS) | WRDS download |
| `company_weburl.json` | Merged list: 500 `{companyname, weburl}` | `check.ipynb` |
| `company_set_N/company_N.json` | Split chunk (≈10 companies per chunk) | `split_company_json.py` |
| `company_set_N/json_iter/Company_iter_url_N_YYYYMM.json` | Discovered same-domain URLs per company | `main_url.py` / `iter_update_url.py` |
| `company_set_N/json_iter/Company_iter_full_N_YYYYMM.json` | Extracted page text per URL per company | `main_text.py` / `iter_update_text.py` |

---

## Phase 0: Data Preparation

### 0.1 Merging WRDS CSVs (`check.ipynb`)

The pipeline starts with two CSV files downloaded from **WRDS (Wharton Research Data Services)**:

- **`current.csv`**: Contains S&P 500 index constituents with columns `[indexname, gvkey, tic, companyname]`.
- **`web.csv`**: Contains company website URLs with columns `[costat, curcd, datafmt, indfmt, consol, gvkey, datadate, conm, tic, weburl]`.

**`check.ipynb`** performs the following steps:

1. **Load** both CSV files using `pandas.read_csv()`.
2. **Deduplicate** each DataFrame by the `gvkey` column (GVKEY is WRDS's unique firm identifier) — keeping the first occurrence of each company.
3. **Merge** the two DataFrames on `gvkey` using an **inner join**, producing a DataFrame of 500 S&P 500 companies with both index membership and website URL information.
4. **Export** the merged result as `company_weburl.json` — a JSON array of objects, each containing:
   ```json
   {
     "companyname": "3M Company",
     "weburl": "www.3m.com"
   }
   ```

> **Note**: The `companyname` field (from `current.csv`) is preferred over `conm` (from `web.csv`) for clearer company names.

### 0.2 Splitting into Subsets (`split_company_json.py`)

Since crawling 500 corporate websites sequentially would be extremely slow, the 500-record JSON is **split into 50 subsets** (≈10 companies each):

- Reads `company_weburl.json` (500 records)
- Creates `company_set/` as the root directory
- Divides records into 50 chunks: `chunk_size = 500 // 50 = 10`
- For each chunk `i` (1–50):
  - Creates directory `company_set/company_set_{i}/`
  - Writes `company_{i}.json` containing the chunk's records
- **Note**: The 50th chunk (`i=50`) receives any remainder records.

### 0.3 Creating Output Directories (`create_json_iter_folders.py`)

After splitting, each `company_set_{i}` folder needs a `json_iter/` subdirectory to store crawling outputs:

- Iterates `i = 1..50`
- Creates `company_set/company_set_{i}/json_iter/` (if not exists)
- This directory will later hold:
  - `Company_iter_url_{i}_{YYYYMM}.json` — discovered URLs
  - `Company_iter_full_{i}_{YYYYMM}.json` — extracted text

---

## Phase 1: URL List Generation & Splitting

> 🔍 **Core Objective**: Transform raw company homepage URLs into an organized, chunked dataset ready for distributed crawling.

This phase is purely about **data preparation** — it does NOT involve web crawling. It takes the raw WRDS data and produces the structured folder hierarchy that Phases 2 and 3 consume.

### Key Scripts

| Script | Purpose |
|---|---|
| `check.ipynb` | Merge & deduplicate WRDS CSVs → `company_weburl.json` |
| `split_company_json.py` | Split JSON into 50 per-company-set files |
| `create_json_iter_folders.py` | Create output subdirectories for each set |

### Data Flow

```
current.csv ─┐
             ├── check.ipynb ──→ company_weburl.json ──→ split_company_json.py ──→ company_set_1/company_1.json
web.csv ─────┘                                                                    ├── company_set_2/company_2.json
                                                                                  ├── ...
                                                                                  └── company_set_50/company_50.json
                                                                                            │
                                                                          create_json_iter_folders.py
                                                                                            │
                                                                                            ▼
                                                                            company_set_N/json_iter/   (empty, ready)
```

### Why Split Into 50 Sets?

- **Parallelism**: Each of the 50 subsets can be crawled independently — by separate processes, terminals, or even different machines.
- **Fault isolation**: If one subset fails, the rest are unaffected.
- **Incremental processing**: You can process only specific subsets (e.g., `--set 5` processes only `company_set_5`).
- **Checkpoint granularity**: Outputs are saved per-subset, making partial results straightforward to aggregate.

---

## Phase 2: Subdomain / Subpage URL Discovery

> 🔍 **Core Objective**: For each company's homepage, perform a **BFS (Breadth-First Search)** crawl to discover all **same-domain** subpages and subdirectories.

This is the first actual web crawling phase. It takes each company's homepage URL and systematically discovers all links within the same domain up to a configurable depth.

### Key Scripts

| Script | Role |
|---|---|
| `main_url.py` | **Orchestrator** — iterates over company_set folders, delegates to `iter_update_url.py` |
| `iter_update_url.py` | **Worker** — BFS crawl logic for a single company website |

### Architecture

```
main_url.py
├── Scans company_set/ for all company_set_{i} folders
├── Creates a single shared Playwright browser instance
├── For each folder (or a specific one with --set N):
│   ├── Input:  company_set_{i}/company_{i}.json
│   ├── Calls:  iter_update_url.run_url_discovery()
│   └── Output: company_set_{i}/json_iter/Company_iter_url_{i}_{YYYYMM}.json
└── Reports summary: total URLs discovered per set
```

### Core Algorithm: `crawl_urls_only()`

The function in `iter_update_url.py` implements a **BFS crawl** constrained to a single domain. Below is the actual code with annotated explanations.

#### Domain Isolation & URL Normalization

Utility functions control what gets crawled and what gets filtered out:

```python
def get_domain(url):
    """Extract the netloc (e.g., 'www.3m.com') for same-origin checking."""
    return urlparse(url).netloc

def is_valid_link(link):
    """Filter out non-HTML links and file downloads."""
    if not link:
        return False
    if link.startswith(('javascript:', 'mailto:', '#', 'tel:')):
        return False
    # Block binary/file download extensions
    if any(link.lower().endswith(ext) for ext in
           ['.jpg', '.png', '.gif', '.pdf', '.mp4',
            '.zip', '.exe', '.css', '.doc', '.docx',
            '.xls', '.xlsx']):
        return False
    return True

def is_permanent_error(error_msg):
    """Identify errors where retrying is pointless."""
    permanent_patterns = [
        "404", "403",
        "ERR_NAME_NOT_RESOLVED",
        "ERR_ADDRESS_UNREACHABLE"
    ]
    return any(p in error_msg for p in permanent_patterns)
```

`get_domain()` is the **gatekeeper** for same-domain crawling — only URLs whose `netloc` matches the company's homepage domain are enqueued. `is_valid_link()` prevents the crawler from chasing email links, JavaScript anchors, or downloading binary files (PDFs, images, etc.). `is_permanent_error()` distinguishes unrecoverable errors (404 Not Found, 403 Forbidden, DNS failure) from transient errors that deserve a retry.

#### The BFS Main Loop

The core crawling loop processes URLs **depth by depth**, maintaining a `visited` set to avoid cycles and an `enqueued` set to prevent duplicate queue entries:

```python
async def crawl_urls_only(browser, start_url, site_name, max_depth):
    target_domain = get_domain(start_url)
    visited = set()
    enqueued = set([start_url])
    queue = [(start_url, 0)]       # (url, depth) tuples
    new_urls = []

    # Single browser context reused across all URLs at this depth
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
    )

    while queue:
        # --- Step A: Dequeue all URLs at current depth (batch) ---
        current_depth = queue[0][1]
        batch = []
        while queue and queue[0][1] == current_depth:
            url, _ = queue.pop(0)
            if url not in visited:
                visited.add(url)
                batch.append(url)

        if not batch:
            continue
        if current_depth > max_depth:
            break
```

The BFS is **depth-batched**: all depth-0 URLs are processed first, then all depth-1, etc. This ensures systematic, level-by-level exploration and gives clean progress output. Once `current_depth > max_depth`, the crawl terminates.

#### Per-URL Processing with Retry Logic

Each URL gets an isolated page within the shared context. The retry strategy handles three error categories distinctly:

```python
        async def process_one(url):
            async with semaphore:
                new_urls.append(url)
                if current_depth >= max_depth:
                    return   # Record URL but don't navigate deeper

                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                try:
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    await page.goto(url,
                        wait_until="domcontentloaded", timeout=150000)

                    # Extract ALL <a href=""> links from the DOM
                    hrefs = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a'))
                                    .map(a => a.href);
                    }""")

                    for href in hrefs:
                        if not is_valid_link(href):
                            continue
                        full_url = urljoin(url, href)
                        # Only enqueue same-domain links
                        if get_domain(full_url) == target_domain:
                            clean_url = full_url.split('#')[0]
                            discovered_this_batch.add(clean_url)

                except Exception as e:
                    error_msg = str(e)
                    # --- Category 1: File downloads (skip, no retry) ---
                    if "Download is starting" in error_msg:
                        print(f" 跳过下载文件: {url}")
                    # --- Category 2: Transient (retry once) ---
                    elif "net::ERR_CONNECTION_CLOSED" in error_msg:
                        # Retry after 1s delay
                        ...
                    elif "Timeout" in error_msg:
                        # Retry after 3s delay
                        ...
                    # --- Category 3: Permanent (skip, no retry) ---
                    elif is_permanent_error(error_msg):
                        print(f" 永久错误，跳过: {url}")
                    else:
                        print(f" 跳过: {url}: {str(e)[:80]}")
                finally:
                    await page.close()
```

Key retry logic patterns:
- **Connection closed** (`net::ERR_CONNECTION_CLOSED`): waits 1 second, then retries the full navigation + link extraction
- **Timeout**: waits 3 seconds (hoping the server recovers), then retries
- **Permanent errors** (404, 403, DNS failure): skipped immediately — `is_permanent_error()` catches these
- **Downloads**: detected via Playwright's "Download is starting" event, skipped without retry
- All retries use the **same page object** within the same `try` block, then close it in `finally`

After each URL is processed, `page.close()` ensures memory is freed. The stealth layer (`playwright_stealth.Stealth`) modifies browser fingerprints to reduce the chance of bot detection.

#### Enqueue New Discoveries

Once all URLs at the current depth are processed, newly discovered links are enqueued for the next depth:

```python
        # 4. 将新发现的链接入队
        for clean_url in discovered_this_batch:
            if clean_url not in enqueued:
                enqueued.add(clean_url)
                queue.append((clean_url, current_depth + 1))

        await asyncio.sleep(0.1)
    await context.close()
    return new_urls
```

The `enqueued` set prevents the same URL from appearing in the queue twice, while `visited` prevents reprocessing. The 0.1s sleep after each depth layer prevents overwhelming the server.

#### Real-Time Checkpointing

After each company completes, results are atomically saved:

```python
    # Atomic file write: .tmp → rename prevents corruption
    os.makedirs(os.path.dirname(output_url_path), exist_ok=True)
    temp_file = output_url_path + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    shutil.move(temp_file, output_url_path)   # atomic on same filesystem
```

The `.tmp` → `shutil.move()` pattern ensures the output file is never left in a half-written state if the script crashes mid-write.

### Output Format

`Company_iter_url_{i}_{YYYYMM}.json`:
```json
{
  "3M Company": [
    "https://www.3m.com/",
    "https://www.3m.com/about",
    "https://www.3m.com/products",
    "https://www.3m.com/careers",
    ...
  ],
  "Abbott Laboratories": [
    "https://www.abbott.com/",
    "https://www.abbott.com/investors",
    ...
  ]
}
```

### CLI Usage

```bash
# Process ALL company sets
python main_url.py

# Process only a specific set (e.g., company_set_5)
python main_url.py --set 5
```

---

## Phase 3: Text Content Extraction

> 📝 **Core Objective**: Visit every discovered URL from Phase 2 and extract the **visible text content**, stripping away non-textual page resources.

This is the second web crawling phase. It consumes the URL lists produced by Phase 2 and produces structured text data suitable for NLP, full-text search, or LLM ingestion.

### Key Scripts

| Script | Role |
|---|---|
| `main_text.py` | **Orchestrator** — iterates over company_set folders, delegates to `iter_update_text.py` |
| `iter_update_text.py` | **Worker** — text extraction for a single company's URLs |

### Architecture

```
main_text.py
├── Scans company_set/ for all company_set_{i} folders
├── Creates a single shared Playwright browser instance
├── For each folder (or a specific one with --set N):
│   ├── Input:  company_set_{i}/json_iter/Company_iter_url_{i}_{YYYYMM}.json
│   ├── Calls:  iter_update_text.run_text_extraction()
│   └── Output: company_set_{i}/json_iter/Company_iter_full_{i}_{YYYYMM}.json
└── Reports summary: total pages extracted per set
```

### Core Algorithm: `run_text_extraction()` / `extract_one()`

The functions in `iter_update_text.py` process each company's URL list. Below is the actual code with annotations.

#### Resource Blocking for Speed

Before navigation, a route interceptor blocks non-text resources:

```python
async def handle_route(route):
    if route.request.resource_type in [
        "image", "stylesheet", "media", "font"
    ]:
        await route.abort()    # Block — we only need text
    else:
        await route.continue_()  # Allow documents, scripts, XHR
```

This `page.route("**/*", handle_route)` is set on every new page. Blocking images, CSS, fonts, and media at the **network request level** reduces bandwidth by 60–90% and dramatically speeds up page loads, since only the HTML document and its JavaScript are fetched.

#### URL-Level Text Extraction with Retry

Each URL is processed in an isolated browser context with up to 2 retries:

```python
async def extract_one(url):
    """每个URL使用独立context"""
    async with semaphore:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
        )
        page = await context.new_page()
        await page.route("**/*", handle_route)
        try:
            max_retries = 2
            retry_delays = [2, 4]           # Exponential backoff

            for attempt in range(max_retries + 1):
                try:
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    await page.goto(url,
                        wait_until="domcontentloaded", timeout=15000)

                    # Extract visible text via browser's render engine
                    text = await page.evaluate(
                        "() => document.body ? document.body.innerText.trim() : ''"
                    )
                    return url, text

                except Exception as e:
                    error_msg = str(e)
                    # --- Skip without retry ---
                    if "Download is starting" in error_msg:
                        return url, None
                    elif "net::ERR_ABORTED" in error_msg:
                        return url, None
                    elif is_permanent_error(error_msg):
                        return url, None
                    # --- Retry with backoff ---
                    elif "net::ERR_CONNECTION_CLOSED" in error_msg:
                        if attempt < max_retries:
                            wait = retry_delays[attempt]
                            await asyncio.sleep(wait)
                        else:
                            return url, None
                    elif attempt < max_retries:
                        wait = retry_delays[attempt]
                        await asyncio.sleep(wait)
                    else:
                        return url, None
        finally:
            await context.close()
```

Key design points:
- **`document.body.innerText`** uses the browser's native rendering engine, not raw HTML parsing. This means it captures text exactly as a human sees it — including content rendered by JavaScript — while automatically excluding `<script>`, `<style>`, hidden elements, and comments.
- **15-second timeout** is aggressive but sufficient for corporate websites (which are typically fast). This prevents the crawler from hanging on slow pages.
- **Exponential backoff**: 2 seconds → 4 seconds → fail. The first retry waits 2s, the second waits 4s, then gives up.
- **Permanent errors** (404, 403, DNS failure) skip immediately without wasting retry budget.
- Every URL gets its **own `browser.new_context()`** — completely isolated cookies, localStorage, and sessions. This prevents cross-site contamination.

#### Orchestrator: Processing All URLs for a Company

The outer function iterates over companies and dispatches parallel extraction tasks:

```python
async def run_text_extraction(url_source_path, output_text_path, browser=None):
    # Load URL source file
    with open(url_source_path, 'r', encoding='utf-8') as f:
        company_urls = json.load(f)     # {company_name: [url1, url2, ...]}

    all_results = {}
    semaphore = asyncio.Semaphore(1)    # One concurrent page at a time

    for company_name, urls in company_urls.items():
        if not urls:
            continue

        all_results[company_name] = {}
        urls_to_extract = [normalize_url(u) for u in urls]

        # Dispatch all URLs for this company in parallel
        tasks = [extract_one(url) for url in urls_to_extract]
        results = await asyncio.gather(*tasks)

        # Collect results
        for url, text in results:
            if text is not None:
                all_results[company_name][url] = text

        # Real-time save after each company
        os.makedirs(os.path.dirname(output_text_path), exist_ok=True)
        temp_file = output_text_path + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
        shutil.move(temp_file, output_text_path)

    # Strip empty companies
    clean_results = {k: v for k, v in all_results.items() if v}
    return sum(len(texts) for texts in clean_results.values())
```

Key design points:
- **`asyncio.gather(*tasks)`** dispatches ALL URLs for a company concurrently (limited by `Semaphore(1)`). Since each URL creates its own browser context, they truly run in parallel.
- **Per-company checkpointing** via `.tmp` → `shutil.move()`: if the script crashes after processing 5 companies, those 5 are already saved. Only the current company's data is lost.
- The `Semaphore(1)` can be increased (e.g., `Semaphore(3)`) to allow 3 simultaneous page loads per company, trading politeness for speed.

### Output Format

`Company_iter_full_{i}_{YYYYMM}.json`:
```json
{
  "3M Company": {
    "https://www.3m.com/": "3M Homepage\nInnovation at work\nScience applied to life...\n...",
    "https://www.3m.com/about": "About 3M\nFounded in 1902...\n...",
    "https://www.3m.com/products": "3M Products\nAdhesives\nAbrasives\n...",
    ...
  },
  "Abbott Laboratories": {
    "https://www.abbott.com/": "Abbott\nGlobal healthcare company...\n...",
    ...
  }
}
```

### CLI Usage

```bash
# Process ALL company sets
python main_text.py

# Process only a specific set (e.g., company_set_5)
python main_text.py --set 5
```

---

## Supplementary Module: Parallel Execution Across Subfolders

> ⚡ **Core Objective**: Run Phase 2 (URL discovery) and Phase 3 (text extraction) **concurrently across multiple company subsets** to maximize throughput.

Since the 50 company sets are fully independent, they can be processed in parallel. This module provides strategies and tools for parallel execution.

### Why Parallel Execution?

| Metric | Sequential (1 set at a time) | Parallel (8 sets at a time) |
|---|---|---|
| Total crawl time (50 sets) | 50 × T | ~(50/8) × T ≈ 6.25 × T |
| Wall clock for 1 set | T | T |
| Fault impact | One failure blocks everything | Isolated to one process |
| Resource utilization | Low (1 browser, ~1 CPU core) | High (N browsers, N CPU cores) |

Where **T** ≈ (avg pages per set) × (avg page load time)

Tip: After several tests using different settings on the parallel number, 8 windows works well on the end with 16 GB RAM and 24 core CPU. The best condition for different number setting should base on the situation of the end itself, to choose a suitable number.

### Strategy 1: Multiple Terminals / Console Windows

The simplest approach — open multiple terminal windows and run different subsets in each.

**URL Discovery:**
```bash
# Terminal 1
python main_url.py --set 1

# Terminal 2
python main_url.py --set 2

# Terminal 3
python main_url.py --set 3
# ... and so on
```

**Text Extraction:**
```bash
# Terminal 1
python main_text.py --set 4

# Terminal 2
python main_text.py --set 5

# Terminal 3
python main_text.py --set 6
# ... and so on
```

**Pros**: Simple, no extra tooling. **Cons**: Manual, doesn't scale well beyond 5–6 terminals.

### Strategy 2: Windows Batch Script (`run_parallel.bat`)

The included `run_parallel.bat` automates launching multiple processes from a single console:

```batch
@echo off
start "Task 1" python main_text.py --set 4
start "Task 2" python main_text.py --set 5
start "Task 3" python main_text.py --set 6
start "Task 4" python main_text.py --set 7
echo All tasks started!
pause
```

- Each `start` command opens a **new console window** running the specified Python script.
- Windows are titled ("Task 1", "Task 2", etc.) for easy identification.
- All processes run **independently and simultaneously**.
- To create your own batch script, copy the pattern and adjust `--set` values.

**For URL Discovery** (`run_parallel_url.bat`):
```batch
@echo off
start "URL Set 1" python main_url.py --set 1
start "URL Set 2" python main_url.py --set 2
start "URL Set 3" python main_url.py --set 3
start "URL Set 4" python main_url.py --set 4
echo All URL tasks started!
pause
```

### Parallel Execution Best Practices

| Practice | Recommendation |
|---|---|
| **Worker count** | Start with 4–8 parallel windows (depends on CPU cores & network bandwidth) |
| **Set assignment** | Avoid overlapping sets across workers |
| **Network throttling** | Each browser instance consumes bandwidth — spread out startups |
| **Logging** | Redirect output to files: `python main_text.py --set 1 > log_set1.txt` |
| **Staggered start** | Launch workers 10–30 seconds apart to avoid simultaneous rate limits |
| **Resume capability** | Re-running `--set 5` simply overwrites that set's output — no cleanup needed |

---

## Requirements & Installation

### System Requirements

- **OS**: Windows (primary target), Linux/macOS (with path adjustments)
- **Python**: 3.8+
- **Browser**: Chromium (installed by Playwright)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd corporate-website-pipeline

# 2. Install Python dependencies
pip install pandas playwright playwright-stealth

# 3. Install Playwright browsers
playwright install chromium
```

> **Note**: If you encounter issues with `playwright_stealth`, you can comment out the Stealth lines in `iter_update_url.py` — it only affects anti-bot evasion and is optional.

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pandas` | ≥1.3 | CSV processing |
| `playwright` | ≥1.40 | Browser automation |
| `playwright-stealth` | any | Anti-bot evasion (optional) |

---

## Usage Guide

### Complete Pipeline (Step by Step)

```bash
# Step 0: Prepare data
# Run check.ipynb in Jupyter to generate company_weburl.json

# Step 1: Create folder structure
python python_code/folder_creation/split_company_json.py
python python_code/folder_creation/create_json_iter_folders.py

# Step 2: Discover URLs (BFS crawl)
#   Option A: All 50 sets sequentially
python python_code/main_url.py
#   Option B: Single set
python python_code/main_url.py --set 1
#   Option C: Run 8 sets in parallel (see Supplementary Module)

# Step 3: Extract text
#   Option A: All 50 sets sequentially
python python_code/main_text.py
#   Option B: Single set
python python_code/main_text.py --set 1
#   Option C: Run 8 sets in parallel
python python_code/main_text.py --set 1
# ... (in another terminal) ...
python python_code/main_text.py --set 2
```

### Typical Workflow for Large Crawls

```
1. Run Phase 1 (data split) → 30 seconds
2. Run Phase 2 (URL discovery) on a few test sets → verify output quality
3. Run Phase 2 on all 50 sets in parallel batches → 2-8 hours (depending on depth)
4. Run Phase 3 (text extraction) on a few test sets → verify text quality
5. Run Phase 3 on all 50 sets in parallel → 1-4 hours
```

### Configuration Parameters

| Parameter | File | Default | Description |
|---|---|---|---|
| `MAX_DEPTH` | `main_url.py` | `2` | BFS crawl depth (0=homepage only, 1=homepage+direct links, 2=two link levels) |
| `num_pages` | `iter_update_text.py` | `1` | Max concurrent pages per company (increase for speed, decrease for politeness) |
| Timeout (navigation) | `iter_update_url.py` | `150000` ms (150s) | Max wait for page load |
| Timeout (text) | `iter_update_text.py` | `15000` ms (15s) | Max wait for text extraction |
| Retry delays | `iter_update_text.py` | `[2, 4]` seconds | Exponential backoff between retries |
| `headless` | `main_url.py` / `main_text.py` | `True` | Run browser in headless mode (set to `False` for debugging) |
---

## License

This project is intended for academic research purposes. The WRDS data is subject to Wharton Research Data Services' terms of use. Respect website `robots.txt` and terms of service when crawling.

---

> **End of English Documentation**

---

# 企业网站数据采集管道

> 一个可扩展的网络爬虫框架，用于发现 S&P 500 企业的网站 URL 并提取文本内容。
>
> **数据来源**：WRDS（沃顿研究数据服务）—— S&P 500 企业标识符及主页 URL。
>
> **流程**：3 个阶段 + 并行执行支持。

---

## 目录

1. [概述](#概述)
2. [项目结构](#项目结构)
3. [阶段 0：数据准备](#阶段-0数据准备)
4. [阶段 1：URL 列表生成与分割](#阶段-1url-列表生成与分割)
5. [阶段 2：子域名/子页面 URL 发现](#阶段-2子域名子页面-url-发现)
6. [阶段 3：文本内容提取](#阶段-3文本内容提取)
7. [补充模块：多子文件夹并行执行](#补充模块多子文件夹并行执行)
8. [安装与依赖](#安装与依赖)
9. [使用指南](#使用指南)
10. [常见问题排查](#常见问题排查)

---

## 概述

本项目实现了一个**三阶段网络爬虫管道**，专为金融/学术研究设计。从 WRDS 提供的公司数据出发：

1. **准备数据** —— 合并两个 WRDS CSV 文件（`current.csv` 和 `web.csv`），创建统一的企业-URL 映射，然后将其切分为可管理的块。
2. **发现 URL** —— 对每个企业主页执行**广度优先搜索（BFS）爬取**，深度可配置，以发现所有同域子页面和子目录。
3. **提取文本** —— 访问每个发现的 URL，提取**可见文本内容**（通过 `document.body.innerText`），并剥离非文本资源（图片、CSS、字体等）。

该系统设计为**并行执行**——整个企业集合被划分为 50 个子集，每个子集可独立处理，允许多个浏览器窗口或机器**同时**爬取。

---

## 项目结构

```
.
├── check.ipynb                          # Jupyter 笔记本：合并 WRDS CSV → 导出 company_weburl.json
├── current.csv                          # WRDS：S&P 500 成分股 (indexname, gvkey, tic, companyname)
├── web.csv                              # WRDS：企业网站 URL (gvkey, conm, tic, weburl, ...)
├── company_weburl.json                  # 合并输出：500 条 {companyname, weburl} 记录
│
├── python_code/
│   ├── folder_creation/
│   │   ├── split_company_json.py        # 拆分 company_weburl.json → N=50 份
│   │   └── create_json_iter_folders.py  # 在每个份目录中创建 json_iter/ 子目录
│   │
│   ├── main_url.py                      # [阶段 2] 主控：跨集合调用 URL 发现
│   ├── iter_update_url.py               # [阶段 2] 核心：每个企业的 BFS 子页面 URL 发现
│   │
│   ├── main_text.py                     # [阶段 3] 主控：跨集合调用文本提取
│   ├── iter_update_text.py              # [阶段 3] 核心：每个企业每个 URL 的文本提取
│   │
│   └── run_parallel.bat                 # [补充] 批处理：并行文本提取
│
└── company_set/                         # 由阶段 0 脚本创建
    ├── company_set_1/
    │   ├── company_1.json               #   10 条企业记录（名称 + 主页 URL）
    │   └── json_iter/                   #   爬取结果输出目录
    │
    ├── company_set_2/
    │   ├── company_2.json
    │   └── json_iter/
    │
    ├── ...
    │
    └── company_set_50/
        ├── company_50.json
        └── json_iter/
```

### 中间及输出文件

| 文件模式 | 描述 | 由谁产生 |
|---|---|---|
| `current.csv` | S&P 500 成分股（来自 WRDS） | WRDS 下载 |
| `web.csv` | 企业网站 URL（来自 WRDS） | WRDS 下载 |
| `company_weburl.json` | 合并列表：500 个 `{companyname, weburl}` | `check.ipynb` |
| `company_set_N/company_N.json` | 拆分后的数据块（每块约 10 家企业） | `split_company_json.py` |
| `company_set_N/json_iter/Company_iter_url_N_YYYYMM.json` | 每个企业发现的同域 URL | `main_url.py` / `iter_update_url.py` |
| `company_set_N/json_iter/Company_iter_full_N_YYYYMM.json` | 每个企业每个 URL 提取的页面文本 | `main_text.py` / `iter_update_text.py` |

---

## 阶段 0：数据准备

### 0.1 合并 WRDS CSV 文件（`check.ipynb`）

本管道从两个从 **WRDS（沃顿研究数据服务）** 下载的 CSV 文件开始：

- **`current.csv`**：包含 S&P 500 指数成分股，列：`[indexname, gvkey, tic, companyname]`。
- **`web.csv`**：包含企业网站 URL，列：`[costat, curcd, datafmt, indfmt, consol, gvkey, datadate, conm, tic, weburl]`。

**`check.ipynb`** 执行以下步骤：

1. 使用 `pandas.read_csv()` **加载**两个 CSV 文件。
2. 按 `gvkey` 列对每个 DataFrame **去重**（GVKEY 是 WRDS 的唯一企业标识符）—— 保留每个企业的第一条记录。
3. 使用 **内连接（inner join）** 在两个 DataFrame 上按 `gvkey` **合并**，生成包含 500 家 S&P 500 企业的 DataFrame，同时包含指数成员信息和网站 URL。
4. **导出**合并结果为 `company_weburl.json` —— JSON 对象数组，每个包含：
   ```json
   {
     "companyname": "3M Company",
     "weburl": "www.3m.com"
   }
   ```

### 0.2 拆分为子集（`split_company_json.py`）

由于顺序爬取 500 个企业网站极其缓慢，将 500 条记录的 JSON **拆分为 50 个子集**（每个约 10 家企业）：

- 读取 `company_weburl.json`（500 条记录）
- 创建 `company_set/` 作为根目录
- 将记录分为 50 块：`chunk_size = 500 // 50 = 10`
- 对每个块 `i`（1–50）：
  - 创建目录 `company_set/company_set_{i}/`
  - 写入 `company_{i}.json`，包含该块的记录
- **注意**：第 50 个块（`i=50`）接收所有剩余记录。

### 0.3 创建输出目录（`create_json_iter_folders.py`）

拆分完成后，每个 `company_set_{i}` 文件夹需要一个 `json_iter/` 子目录来存储爬取输出：

- 遍历 `i = 1..50`
- 创建 `company_set/company_set_{i}/json_iter/`（如不存在）
- 该目录稍后将存放：
  - `Company_iter_url_{i}_{YYYYMM}.json` —— 发现的 URL
  - `Company_iter_full_{i}_{YYYYMM}.json` —— 提取的文本

---

## 阶段 1：URL 列表生成与分割

> 🔍 **核心目标**：将原始的企业主页 URL 转换为组织良好、分块的、可直接用于分布式爬取的数据集。

此阶段纯粹是**数据准备**——不涉及网络爬取。它接收原始 WRDS 数据并生成阶段 2 和阶段 3 所需的层级文件夹结构。

### 关键脚本

| 脚本 | 用途 |
|---|---|
| `check.ipynb` | 合并 & 去重 WRDS CSV → `company_weburl.json` |
| `split_company_json.py` | 将 JSON 拆分为每个企业集一个文件（共 50 个） |
| `create_json_iter_folders.py` | 为每个集创建输出子目录 |

### 数据流

```
current.csv ─┐
             ├── check.ipynb ──→ company_weburl.json ──→ split_company_json.py ──→ company_set_1/company_1.json
web.csv ─────┘                                                                      ├── company_set_2/company_2.json
                                                                                    ├── ...
                                                                                    └── company_set_50/company_50.json
                                                                                              │
                                                                            create_json_iter_folders.py
                                                                                              │
                                                                                              ▼
                                                                              company_set_N/json_iter/   （空的，准备就绪）
```

### 为何拆分为 50 个集合？

- **并行性**：50 个子集中的每一个都可以独立爬取——通过独立的进程、终端，甚至不同的机器。
- **故障隔离**：如果一个子集失败，其他子集不受影响。
- **增量处理**：可以只处理特定的子集（例如，`--set 5` 只处理 `company_set_5`）。
- **检查点粒度**：输出按子集保存，使得部分结果的汇总变得直接简单。

---

## 阶段 2：子域名/子页面 URL 发现

> 🔍 **核心目标**：对每个企业主页，执行 **广度优先搜索（BFS）** 爬取，以发现所有**同域**子页面和子目录。

这是第一个实际网络爬取阶段。它获取每个企业的主页 URL，并系统性地发现同一域名内的所有链接，深度可配置。

### 关键脚本

| 脚本 | 角色 |
|---|---|
| `main_url.py` | **编排器** —— 遍历 company_set 文件夹，委托给 `iter_update_url.py` |
| `iter_update_url.py` | **工作者** —— 单个企业网站的 BFS 爬取逻辑 |

### 架构

```
main_url.py
├── 扫描 company_set/ 中所有 company_set_{i} 文件夹
├── 创建一个共享的 Playwright 浏览器实例
├── 对每个文件夹（或使用 --set N 指定特定文件夹）：
│   ├── 输入：  company_set_{i}/company_{i}.json
│   ├── 调用：  iter_update_url.run_url_discovery()
│   └── 输出：  company_set_{i}/json_iter/Company_iter_url_{i}_{YYYYMM}.json
└── 报告汇总：每个集发现的 URL 总数
```

### 核心算法：`crawl_urls_only()`

`iter_update_url.py` 中的函数实现了**约束在单一域名内的 BFS 爬取**：

```
算法：BFS URL 发现（单个企业）

输入：  start_url（企业主页），max_depth（默认：2）
输出： 所有发现的同域 URL 列表

1. 从 start_url 解析 target_domain
2. 初始化：visited = {}, queue = [(start_url, depth=0)]
3. 当 queue 不为空时：
   a. 出队当前深度的所有 URL（批处理）
   b. 如果 current_depth > max_depth：停止
   c. 对批次中的每个 URL（通过 asyncio.gather 并行）：
      - 创建新的页面上下文（每个 URL 隔离）
      - 应用 stealth（反爬虫检测）
      - 使用超时和重试逻辑导航到 URL
      - 从 DOM 中提取所有 <a href=""> 链接
      - 过滤：
        * 拒绝：javascript:、mailto:、tel:、# 锚点
        * 拒绝：文件下载（.jpg、.pdf、.zip、.docx 等）
        * 接受：仅同域 URL
        * 标准化：移除 # 片段、解析相对 URL
      - 收集发现的链接
   d. 将新链接入队到 depth+1（如果尚未访问/入队）
4. 返回所有已访问的 URL（按发现顺序）
```

### 关键设计决策

**共享浏览器，隔离上下文**：
- 一个**共享的 Playwright 浏览器**在所有企业和深度之间共享。
- 每个 URL 获得其**自己的页面上下文**（`browser.new_context()`）——干净的 Cookie，无会话泄漏。
- 上下文在每次 URL 处理后创建并关闭，防止内存泄漏。

**BFS 深度分批处理**：
- URL 按**深度层级**处理 —— 先处理所有深度 0 的 URL，然后是深度 1，依此类推。
- 这允许清晰的进度报告（"深度 0：1 个 URL"、"深度 1：47 个 URL"）并确保系统性的探索。
- `max_depth` 参数（默认：2）控制要遍历的链接层级数。

**并发控制**：
- `Semaphore(1)` 限制每批**一个并发页面**。
- 每个页面导航有 **150 秒超时**时间。
- 连接通过 `random.uniform(0.3, 0.8)` 秒的随机延迟进行节流 —— 礼貌爬取。

**错误处理**：
- **永久错误**（404、403、DNS 解析失败）：立即跳过，不重试。
- **连接关闭**（net::ERR_CONNECTION_CLOSED）：等待 1 秒后自动重试一次。
- **超时**：等待 3 秒后重试一次。
- **下载**：检测到文件下载时跳过。
- **反爬虫**：使用 `playwright_stealth.Stealth` 来规避爬虫检测。

**实时检查点**：
- 每个企业处理完成后，结果保存到 `.tmp` 文件，然后原子性地重命名为目标路径。
- 这防止脚本在管道中途崩溃时数据全部丢失。

### 输出格式

`Company_iter_url_{i}_{YYYYMM}.json`：
```json
{
  "3M Company": [
    "https://www.3m.com/",
    "https://www.3m.com/about",
    "https://www.3m.com/products",
    "https://www.3m.com/careers",
    ...
  ],
  "Abbott Laboratories": [
    "https://www.abbott.com/",
    "https://www.abbott.com/investors",
    ...
  ]
}
```

### CLI 使用方法

```bash
# 处理所有企业集合
python main_url.py

# 仅处理特定集合（例如，company_set_5）
python main_url.py --set 5
```

---

## 阶段 3：文本内容提取

> 📝 **核心目标**：访问阶段 2 发现的每个 URL，提取**可见文本内容**，剥离非文本页面资源。

这是第二个网络爬取阶段。它使用阶段 2 产生的 URL 列表，并生成适合 NLP、全文搜索或 LLM 摄入的结构化文本数据。

### 关键脚本

| 脚本 | 角色 |
|---|---|
| `main_text.py` | **编排器** —— 遍历 company_set 文件夹，委托给 `iter_update_text.py` |
| `iter_update_text.py` | **工作者** —— 单个企业的 URL 列表的文本提取 |

### 架构

```
main_text.py
├── 扫描 company_set/ 中所有 company_set_{i} 文件夹
├── 创建一个共享的 Playwright 浏览器实例
├── 对每个文件夹（或使用 --set N 指定特定文件夹）：
│   ├── 输入：  company_set_{i}/json_iter/Company_iter_url_{i}_{YYYYMM}.json
│   ├── 调用：  iter_update_text.run_text_extraction()
│   └── 输出：  company_set_{i}/json_iter/Company_iter_full_{i}_{YYYYMM}.json
└── 报告汇总：每个集提取的页面总数
```

### 核心算法：`run_text_extraction()` / `extract_one()`

`iter_update_text.py` 中的函数处理每个企业的 URL 列表：

```
算法：文本提取（单个企业）

输入：  企业的 URL 列表（来自阶段 2 输出）
输出：  {url: page_text} 字典，包含成功提取的页面

1. 加载 URL 源文件（Company_iter_url_N_YYYYMM.json）
2. 对每个 company_name 及其 URL 列表：
   a. 标准化所有 URL（缺少协议时添加 https://）
   b. 对每个 URL（通过 asyncio.gather 并行）：
      - 创建隔离的浏览器上下文 + 页面
      - 设置路由拦截器：
        * 阻止：图片、样式表、媒体、字体
        * 允许：文档、脚本、XHR/fetch
      - 导航到 URL，使用：
        * 每次尝试 15 秒超时
        * 最多 2 次重试（指数退避：2 秒、4 秒）
      - 提取：document.body.innerText（修剪）
      - 处理错误：
        * 永久错误（404、403、DNS）：立即跳过
        * 连接关闭：退避后重试
        * 下载/中止：跳过
      - 关闭上下文
   c. 按企业保存结果（实时检查点）
3. 保存最终输出，移除空的企业条目
```

### 关键设计决策

**通过资源阻止加速**：
- 图片、CSS、字体和媒体通过 Playwright 的 `page.route()` 拦截器在**网络层级被阻止**。
- 这极大地减少了页面加载时间和带宽，因为我们只需要文本内容。
- 文档和脚本被允许（某些页面动态加载内容）。

**文本提取方法**：
- 使用 `document.body.innerText` —— 浏览器的原生文本渲染算法。
- 这捕捉了所有用户可见的文本，与人类看到的完全一致，包括动态渲染的内容。
- 不可见文本（隐藏元素、注释、`<script>` 标签、`<style>` 块）被浏览器自动排除。

**并发与重试**：
- `Semaphore(1)` 限制每个企业一次处理一个页面。
- 每次 URL 尝试有 **15 秒超时**（激进设置 —— 适合快速的企业网站）。
- **指数退避**：2 秒 → 4 秒 → 失败。
- 永久错误立即跳过，不重试。

**每企业检查点**：
- 结果保存到 `.tmp`，并在每个企业完成后原子性地重命名。
- 如果脚本被中断，所有已处理的企业数据都被保留。

### 输出格式

`Company_iter_full_{i}_{YYYYMM}.json`：
```json
{
  "3M Company": {
    "https://www.3m.com/": "3M Homepage\nInnovation at work\nScience applied to life...\n...",
    "https://www.3m.com/about": "About 3M\nFounded in 1902...\n...",
    "https://www.3m.com/products": "3M Products\nAdhesives\nAbrasives\n...",
    ...
  },
  "Abbott Laboratories": {
    "https://www.abbott.com/": "Abbott\nGlobal healthcare company...\n...",
    ...
  }
}
```

### CLI 使用方法

```bash
# 处理所有企业集合
python main_text.py

# 仅处理特定集合（例如，company_set_5）
python main_text.py --set 5
```

---

## 补充模块：多子文件夹并行执行

> ⚡ **核心目标**：**并发**运行阶段 2（URL 发现）和阶段 3（文本提取）跨多个企业子集，以最大化吞吐量。

由于 50 个企业集合完全独立，它们可以并行处理。本模块提供并行执行的策略和工具。

### 为何并行执行？

| 指标 | 顺序执行（一次一个集合） | 并行执行（一次 8 个集合） |
|---|---|---|
| 总爬取时间（50 个集合） | 50 × T | ~(50/8) × T ≈ 6.25 × T |
| 1 个集合的时钟时间 | T | T |
| 故障影响 | 一个故障阻塞一切 | 隔离到单一进程 |
| 资源利用率 | 低（1 个浏览器，约 1 个 CPU 核心） | 高（N 个浏览器，N 个 CPU 核心） |

其中 **T** ≈（每个集合平均页面数）×（平均页面加载时间）

Tip: 在并行数量上使用不同设置进行多次测试后，最终发现，在16 GB内存和24核CPU的配置下，8个窗口运行良好。不同数量设置下的最佳条件应根据终端本身的情况来选择合适的数量。

### 策略 1：多终端 / 控制台窗口

最简单的方法 —— 打开多个终端窗口，在每个窗口中运行不同的子集。

**URL 发现：**
```bash
# 终端 1
python main_url.py --set 1

# 终端 2
python main_url.py --set 2

# 终端 3
python main_url.py --set 3
# ... 依此类推
```

**文本提取：**
```bash
# 终端 1
python main_text.py --set 4

# 终端 2
python main_text.py --set 5

# 终端 3
python main_text.py --set 6
# ... 依此类推
```

**优点**：简单，无需额外工具。**缺点**：手动，超过 5–6 个终端不易扩展。

### 策略 2：Windows 批处理脚本（`run_parallel.bat`）

附带的 `run_parallel.bat` 自动化从单个控制台启动多个进程：

```batch
@echo off
start "任务 1" python main_text.py --set 4
start "任务 2" python main_text.py --set 5
start "任务 3" python main_text.py --set 6
start "任务 4" python main_text.py --set 7
echo 所有任务已启动！
pause
```

- 每个 `start` 命令打开一个**新的控制台窗口**运行指定的 Python 脚本。
- 窗口被命名（"任务 1"、"任务 2" 等）以便识别。
- 所有进程**独立且同时**运行。
- 要创建自己的批处理脚本，复制该模式并调整 `--set` 值。

**用于 URL 发现**（`run_parallel_url.bat`）：
```batch
@echo off
start "URL 集合 1" python main_url.py --set 1
start "URL 集合 2" python main_url.py --set 2
start "URL 集合 3" python main_url.py --set 3
start "URL 集合 4" python main_url.py --set 4
echo 所有 URL 任务已启动！
pause
```

### 并行执行最佳实践

| 实践 | 建议 |
|---|---|---|
| **工作进程数** | 从 4–8 个并行窗口开始（取决于 CPU 核心数和网络带宽） |
| **集合分配** | 避免不同窗口处理相同的集合编号 |
| **网络节流** | 每个浏览器实例消耗带宽 —— 错峰启动 |
| **日志记录** | 将输出重定向到文件：`python main_text.py --set 1 > log_set1.txt` |
| **错时启动** | 各窗口间隔 10–30 秒启动，避免同时触发速率限制 |
| **恢复能力** | 重新运行 `--set 5` 仅覆盖该集合的输出，无需清理 |
## 安装与依赖

### 系统要求

- **操作系统**：Windows（主要目标）、Linux/macOS（需调整路径）
- **Python**：3.8+
- **浏览器**：Chromium（由 Playwright 安装）

### 安装步骤

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd corporate-website-pipeline

# 2. 安装 Python 依赖
pip install pandas playwright playwright-stealth

# 3. 安装 Playwright 浏览器
playwright install chromium
```

> **注意**：如果 `playwright_stealth` 安装遇到问题，可以注释掉 `iter_update_url.py` 中的 Stealth 相关行 —— 它只影响反爬虫检测，是可选的。

### 依赖包

| 包 | 版本 | 用途 |
|---|---|---|
| `pandas` | ≥1.3 | CSV 处理 |
| `playwright` | ≥1.40 | 浏览器自动化 |
| `playwright-stealth` | 任意 | 反爬虫检测（可选） |

---

## 使用指南

### 完整管道（逐步执行）

```bash
# 步骤 0：准备数据
# 在 Jupyter 中运行 check.ipynb 生成 company_weburl.json

# 步骤 1：创建文件夹结构
python python_code/folder_creation/split_company_json.py
python python_code/folder_creation/create_json_iter_folders.py

# 步骤 2：发现 URL（BFS 爬取）
#   选项 A：顺序处理全部 50 个集合
python python_code/main_url.py
#   选项 B：单个集合
python python_code/main_url.py --set 1
#   选项 C：并行运行 8 个集合（参见补充模块）

# 步骤 3：提取文本
#   选项 A：顺序处理全部 50 个集合
python python_code/main_text.py
#   选项 B：单个集合
python python_code/main_text.py --set 1
#   选项 C：并行运行 8 个集合
python python_code/main_text.py --set 1
# ...（在另一个终端中）...
python python_code/main_text.py --set 2
```

### 大型爬取的典型工作流

```
1. 运行阶段 1（数据拆分）→ 30 秒
2. 在几个测试集上运行阶段 2（URL 发现）→ 验证输出质量
3. 在所有 50 个集合上并行批量运行阶段 2 → 2-8 小时（取决于深度）
4. 在几个测试集上运行阶段 3（文本提取）→ 验证文本质量
5. 在所有 50 个集合上并行运行阶段 3 → 1-4 小时
```

### 配置参数

| 参数 | 文件 | 默认值 | 描述 |
|---|---|---|---|
| `MAX_DEPTH` | `main_url.py` | `2` | BFS 爬取深度（0=仅主页，1=主页+直接链接，2=两层链接） |
| `num_pages` | `iter_update_text.py` | `1` | 每个企业的最大并发页面数（增加以提高速度，减少以表示礼貌） |
| 超时（导航） | `iter_update_url.py` | `150000` 毫秒（150 秒） | 页面加载最长等待时间 |
| 超时（文本） | `iter_update_text.py` | `15000` 毫秒（15 秒） | 文本提取最长等待时间 |
| 重试延迟 | `iter_update_text.py` | `[2, 4]` 秒 | 重试之间的指数退避时间 |
| `headless` | `main_url.py` / `main_text.py` | `True` | 以无头模式运行浏览器（设为 `False` 进行调试） |
---

## 许可

本项目仅供学术研究目的使用。WRDS 数据受沃顿研究数据服务的使用条款约束。爬取时请尊重网站的 `robots.txt` 和服务条款。
