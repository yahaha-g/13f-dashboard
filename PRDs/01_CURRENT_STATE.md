# 13F Dashboard - Current System Snapshot

## 1. Project Overview

This document describes the current implementation state of the 13F Dashboard.
It serves as a reference baseline before structural upgrades.

No code should be modified based on this document.
This is a documentation-only snapshot.

---

## 2. Deployment & Infrastructure

### Hosting
- Platform: (e.g. Vercel)
- Repository: (GitHub repo name)
- Branch strategy: (main / feature branches)

### Automation
- GitHub Actions enabled: Yes / No
- 13F auto-fetch schedule: (cron time)
- Data update flow:
  1. Fetch from SEC
  2. Parse infotable
  3. Transform to JSON
  4. Commit & push

---

## 3. Data Layer

### Data Location
- data/13f/*.json

### Core Entities (Observed from current JSON)

#### Institution
- cik
- name

#### Filing
- quarter
- filing_date
- infotable_url

#### Holding
- issuer
- cusip
- value_usd_k
- shares
- weight (calculated)
- change_type (new/add/trim/exit)

---

## 4. Diff Engine (Current Behavior)

Change detection rules (as currently implemented):

- new: position not present in previous quarter
- add: shares increased vs previous quarter
- trim: shares decreased vs previous quarter
- exit: present last quarter but not current quarter

Comparison logic:
- Based on CUSIP matching
- Quarter-over-quarter comparison

Location of diff logic:
- (file path, e.g. scripts/diff.py or lib/diff.ts)

---

## 5. Frontend Structure

### Pages

- Home page
  - Institution list
  - Latest quarter
  - Holdings count
  - Top1 holding
  - Behavior summary (if implemented)

- Institution detail page
  - Statistics section
  - Holdings table
  - Change tag color display

- (Optional) Stock page

### UI Observations
- Change tags color-coded
- Table-based layout
- No global behavior summary page yet

---

## 6. Strengths of Current System

- Automated 13F data fetching
- Stable JSON-based data structure
- Working diff engine
- Deployed and publicly accessible
- Change tag implemented correctly

---

## 7. Known Limitations

- No cross-institution behavior aggregation
- No conviction tracking timeline
- Limited summary visualization
- UI not optimized for behavior-first display

---

## 8. Upgrade Constraints

During Phase 1–2 upgrades:

- Do NOT modify data schema without updating DATA.md
- Do NOT break diff engine logic
- Do NOT remove GitHub Action workflow
- UI changes must not affect data generation pipeline

v1 是单页 HTML、数据在 data/13f/，Actions 负责生成；v2 要并行迁移，不破坏 v1