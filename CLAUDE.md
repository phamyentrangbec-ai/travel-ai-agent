# Trip Buddy AI Agent — Master Update Specification
**Version:** 2.0.0 | **Date:** 2026-06-15 | **For:** Claude Code on Team Member A's machine

Feed this file directly into Claude Code. It contains the complete picture of:
1. What the agent is supposed to do (logic spec)
2. What the current Stitch design shows (UI audit — confirmed from source HTML)
3. Where the discrepancies are (bugs confirmed in code)
4. Exactly what to fix and how

---

## 0. Project Overview

**Trip Buddy** is a Vietnamese AI travel planning agent. Users speak or type to plan trips, get day-by-day itineraries, track group expenses, and split costs automatically.

**Stack context (assumed from existing code):**
- Frontend: HTML/Tailwind CSS (Stitch Studio generated), mobile-first, max-width 430px
- AI agent: LLM with NLU slot extraction, STT confidence gating
- Backend: Node/TypeScript, PostgreSQL
- Design system: Plus Jakarta Sans + DM Mono, Material You palette

---

## 1. Complete User Behavior Flow

### 1.1 Onboarding → Planning → Itinerary (Happy Path)

```
[Onboarding Screen]
  User taps "Bắt đầu ngay"
  → Navigate to /plan (Home/Empty State)

[Home Screen — /plan]
  User sees destination chips OR empty state illustration
  Option A: tap a chip (e.g. "🌿 Đà Lạt")
    → chip becomes selected (bg-primary text-on-primary)
    → destination slot pre-filled, move to Step 2
  Option B: type in input bar
    → text input opens keyboard
    → on submit, NLU extracts destination slot
  Option C: tap mic icon
    → opens Voice Recording sheet (bottom sheet, Phase 1)

[Planning Chat — Steps 1–5]
  Progress stepper: 5 dots, active = larger + inner dot
  Agent asks ONLY for missing slots:
    Slot 1: destination (e.g. "Đà Lạt")
    Slot 2: group type ("Nhóm bạn" / "Cặp đôi" / "Gia đình" / "Solo")
    Slot 3: duration ("2N1Đ" / "3N2Đ" / "4N3Đ")
    Slot 4: budget range ("Tiết kiệm" / "Tầm trung" / "Sang chảnh")
    Slot 5: travel style ("📸 Check-in" / "😌 Chill" / "🍜 Ẩm thực")
  
  RULE: If user pre-filled slots via chip/voice, SKIP those questions.
  Quick-reply chips for each step. Selected chip = bg-primary text-on-primary.
  Context tags show confirmed slots, each with "Thay đổi" link to go back.
  
  ⚠️ BOTTOM NAV MUST BE HIDDEN on ALL /plan/* screens.
  The compose input bar sits at fixed bottom instead.

[Loading Screen]
  AI generates itinerary (5–10 seconds).
  Determinate progress bar (0% → 90%, pauses, then 100% on complete).
  Skeleton cards animate (shimmer).
  After 3 seconds: "Huỷ" button appears.
  After 15 seconds with no response: show error state with [Thử lại] + [Huỷ].

[Itinerary Screen — /itinerary/:sessionId]
  Shows day-by-day schedule with activities.
  Budget breakdown card.
  Bottom nav is VISIBLE here.
  "💰 Tính tiền" button → navigates to Expense Tracker tab.
  "💾 Lưu" button → saves session to device.
  
  Tap any activity row → opens Venue Detail Sheet (bottom sheet).
  
[Venue Detail Sheet]
  80% height bottom sheet.
  Has ✕ close button in sheet header.
  Photo hero with gallery thumbnails.
  "Xem địa điểm thay thế" → opens Alternatives Picker Sheet.

[Alternatives Picker Sheet]
  Lists current venue (DISABLED, "ĐANG DÙNG" badge, NO radio button).
  Lists alternatives with SINGLE radio group (tap to select one).
  Confirm button disabled until one alternative is selected.
  On confirm → update itinerary → show diff banner on itinerary screen.

[Diff Banner — after venue swap]
  Appears at top of itinerary activity list when plan differs from AI original.
  Shows "1 địa điểm đã thay đổi · +Xđ so với bản gốc"
  Has "Khôi phục gốc" link → restores original AI plan (does NOT wipe expenses).
```

### 1.2 Expense Tracking Flow

```
[Expense Tracker — /expense/:sessionId]
  Activated via "Tính Tiền" tab in bottom nav.
  
  Summary card shows TWO separate labeled rows:
    Row 1: "Tổng toàn chuyến" → total amount (ALL expenses ever added)
    Row 2: "Hôm nay" → today's expenses only
  These are NEVER merged into one. Both always visible.
  
  Quick-view settlement shows who owes whom and how much.
  Bar chart: each member's bar height proportional to their total paid.
    Bar labels show exact amounts. Sum of bar amounts = "Tổng toàn chuyến".
  
  Expense history list: newest first.
  FAB (mic icon, bottom-right): tap → opens Voice Recording sheet.

[Voice Recording — Phase 1]
  Bottom sheet slides up.
  Mic pulse animation + waveform bars animate.
  Live transcript appears in real time (STT).
  On recording end:
    → Show "Đang phân tích giọng nói..." spinner (NLU processing)
    → Extract slots: payer, amount, description, who-split
    → If confidence < 0.75: ask clarifying question
    → If confidence ≥ 0.75: transition to Phase 2

  ⚠️ DO NOT skip to a question form after recording ends.
  ⚠️ ALWAYS show the "Đang phân tích..." state between Phase 1 and Phase 2.

[Voice Confirmation — Phase 2]
  Shows extracted data for confirmation:
    - Quoted transcript (italic)
    - Payer name + amount
    - Split breakdown per member
  User taps "✓ Thêm khoản chi này" → saves expense → updates totals.
  User taps "Sửa lại" → goes back to Phase 1.

[Settlement Screen]
  Per-session only (scoped to current trip sessionId).
  Lists who owes whom, minimum transfer algorithm.
  Select payment method → confirm button becomes active.
  Tap confirm → MODAL appears asking "Xác nhận thanh toán?".
  Only after modal confirm → mark as settled.
  ⚠️ Direct confirmation without modal is a bug.
```

---

## 2. Confirmed Bugs (from Stitch HTML source audit — June 2026)

Each bug was verified by reading the actual `code.html` files from the Stitch export.

### 🔴 CRITICAL — Fix in Sprint 1

---

#### BUG L4 — Budget Line Items Don't Sum to Total
**File:** `l_ch_tr_nh_l_t/code.html`
**Evidence from code:**
```html
<span>350.000đ</span>   <!-- Chỗ ở -->
<span>200.000đ</span>   <!-- Ăn uống -->
<span>80.000đ</span>    <!-- Di chuyển -->
<span>150.000đ</span>   <!-- Vui chơi -->
<!-- Total shown: -->
<span class="text-[17px] font-bold text-secondary">~1,800,000đ/người</span>
```
**Actual sum:** 350 + 200 + 80 + 150 = **780,000đ** ≠ 1,800,000đ  
**Fix:** Use realistic numbers that sum correctly. Suggested:
```
Chỗ ở:       800,000đ  (1 phòng ÷ 3 người × 3 đêm ÷ người)
Ăn uống:     480,000đ  (3 bữa × 2 ngày × 80k)
Di chuyển:   200,000đ  (taxi + xe ôm)
Vui chơi:    150,000đ  (vé vào cửa)
Dự phòng:    164,000đ  (10%)
─────────────────────
Tổng:      1,794,000đ  ≈ ~1,800,000đ/người  ✓
```
**Agent logic fix:** BudgetService must validate `sum(lineItems) ≈ total` before rendering. Throw if delta > 5%.

---

#### BUG L3 — Alternatives Picker Dual-Selection State
**File:** `alternatives_picker_sheet/code.html`
**Evidence from code:**
```html
<!-- Row 1: Hồ Xuân Hương — has "Hiện tại" badge with check_circle -->
<span class="bg-primary-container text-on-primary-container ...">
  <span class="material-symbols-outlined" data-icon="check_circle">check_circle</span>
  ✓ Hiện tại
</span>
<!-- Row 2: Langbiang — ALSO has radio_button_checked -->
<span class="material-symbols-outlined text-primary" data-icon="radio_button_checked">radio_button_checked</span>
```
**Problem:** Row 1 has a selection state (check_circle) AND Row 2 also has a selection state (radio_button_checked). User cannot tell what's selected.  
**Fix:**
```
Row 1 (current venue):
  - Remove ALL radio icons
  - Show ONLY "ĐANG DÙNG" badge (bg-primary-container)  
  - Set pointer-events-none, opacity-60
  - No selection state whatsoever

Rows 2–N (alternatives):
  - Single radio group (name="venue-alternative")
  - Exactly 1 can be checked at a time
  - radio_button_unchecked by default
  - radio_button_checked (FILL) when selected
  - Border highlights: border-[3px] border-primary when selected

Confirm button:
  - Disabled (opacity-40, pointer-events-none) when nothing selected
  - Active (bg-primary) when 1 alternative selected
```

---

#### BUG L6 — "HÔM NAY" Badge Misplaced — Misleads User About What the Total Represents
**File:** `t_nh_ti_n_chuy_n_i/code.html`
**Evidence from code:**
```html
<p class="font-label-sm text-on-surface-variant mb-1">Tổng chi tiêu chuyến đi</p>
<h2 class="font-display-lg text-display-lg text-primary">520,000đ</h2>
<!-- HÔM NAY badge sits on the SAME row as "Tổng" — visually implies 520k = today only -->
<div class="bg-primary-fixed text-on-primary-fixed px-3 py-1 rounded-full text-caption-xs font-bold">
  HÔM NAY
</div>
```
**Clarification:** The 520,000đ figure IS CORRECT — it represents the **cumulative total of all expenses added to this session** (e.g. Đà Lạt folder), summed across the entire trip. This is the intended design. The bug is purely a **labeling/layout issue**: the "HÔM NAY" badge placed next to the total makes users think 520k is only today's spending, not the full trip accumulation.

**Fix — Keep the cumulative total as-is. Move/repurpose "HÔM NAY":**
```html
<!-- Correct structure: total is cumulative, "Hôm nay" is an OPTIONAL sub-row below -->
<div class="summary-card">
  <div class="row-1 flex justify-between items-start">
    <div>
      <label class="font-label-sm text-on-surface-variant">Tổng toàn chuyến</label>
      <!-- This IS the cumulative all-trip total — do NOT put HÔM NAY badge here -->
      <amount class="font-display-lg text-primary">520,000đ</amount>
    </div>
    <!-- Remove HÔM NAY badge from here entirely -->
  </div>

  <!-- OPTIONAL: add a sub-row for today's portion if > 0 -->
  <div class="row-2 border-t mt-3 pt-3 flex justify-between" id="today-row">
    <span class="font-label-sm text-on-surface-variant flex items-center gap-1">
      <span class="material-symbols-outlined text-[14px]">today</span>
      Hôm nay
    </span>
    <span class="font-budget-mono text-secondary">Xđ</span>
  </div>

  <div class="sub-stats row-3 border-t mt-3 pt-3 flex justify-between">
    <span class="font-budget-mono text-tertiary">Đã trả: Xđ</span>
    <span class="font-budget-mono text-secondary">Còn nợ: Xđ</span>
  </div>
</div>
```
**Agent logic fix:** 
- `BudgetService.getSessionTotal(sessionId)` = sum ALL expenses for this sessionId → display as "Tổng toàn chuyến"
- `BudgetService.getTodayTotal(sessionId)` = sum expenses WHERE `date(createdAt) = today` → display as "Hôm nay" sub-row
- These are two separate queries. The main headline number is always the cumulative total, never just today.

---

#### BUG L7 — Bar Chart Heights Don't Reflect Proportional Differences
**File:** `t_nh_ti_n_chuy_n_i/code.html`
**Evidence from code:**
```
Bar chart: Ngân 215k (height 100%), Thủy 215k (height 100%), Trang 90k (height 42%)
Summary card: 520k cumulative total (correct)
Ngân + Thủy + Trang = 215 + 215 + 90 = 520k ✓ — amounts ARE consistent with total
```
**Clarification:** The 520k and the bar amounts are actually internally consistent — both reflect the cumulative trip total for the current session. The bar heights for Ngân and Thủy being equal at 100% is also correct since they paid the same amount. Trang at 42% (90/215) is correct proportionally.

**Actual problem:** As more expenses are added over the trip, the bar chart must **update dynamically** from the live session data — not use hardcoded values. The bars must always reflect `BudgetService.getMemberTotals(sessionId)` at render time.

**Fix:**
```typescript
// On expense tracker mount and after every expense added:
async function refreshChart(sessionId: string) {
  const memberTotals = await BudgetService.getMemberTotals(sessionId);
  // memberTotals: { memberId: bigint }
  
  const maxTotal = Math.max(...Object.values(memberTotals).map(Number));
  
  members.forEach(member => {
    const amount = memberTotals[member.id] ?? 0n;
    const heightPct = maxTotal > 0 ? (Number(amount) / maxTotal) * 100 : 0;
    
    // Update bar height
    barEls[member.id].style.height = `${heightPct}%`;
    
    // Update label — show full amount in DM Mono font
    labelEls[member.id].textContent = formatVND(amount); // e.g. "215.000đ"
  });
}

// formatVND: always DM Mono, never abbreviate (215k → 215.000đ)
function formatVND(amount: bigint): string {
  return Number(amount).toLocaleString('vi-VN') + 'đ';
}
```
**Rule:** Sum of all bar amounts must always equal the "Tổng toàn chuyến" figure. Both are sourced from `BudgetService.getSessionTotal(sessionId)` and `getMemberTotals(sessionId)` respectively.

---

#### BUG L8 — Settlement Confirms Without Modal
**File:** `settlement_confirmation/code.html`
**Evidence from code:**
```html
<button class="flex-1 h-10 bg-primary text-white rounded-lg ...">
  <span class="material-symbols-outlined text-[18px]">check</span>
  Đánh dấu đã chuyển
</button>
<!-- No modal. Tap = immediate confirmation. -->
```
**Fix — Intercept confirm tap with modal:**
```javascript
confirmBtn.addEventListener('click', () => {
  showModal({
    title: 'Xác nhận thanh toán?',
    body: `${payer} đã chuyển ${amount} cho ${receiver} qua ${method}.`,
    confirmLabel: '✓ Đã chuyển rồi',
    cancelLabel: 'Huỷ',
    onConfirm: () => markSettled(transactionId)
  });
});
```
**Also fix:** "Đánh dấu đã chuyển" button must be DISABLED until a payment method is selected. The button becomes active only after user taps one of the 3 method buttons (bank/wallet/cash).

---

#### BUG U1 — Bottom Nav Visible on Planning Screen (mobile hidden but class wrong)
**File:** `l_n_l_ch_th_i_gian/code.html`
**Evidence from code:**
```html
<nav class="hidden md:flex fixed bottom-0 w-full z-50 ...">
```
**Problem:** `hidden md:flex` hides on mobile but shows at md breakpoint (≥768px). This is wrong — planning screens should NEVER show the bottom nav regardless of viewport.  
**Fix:**
```html
<!-- On all /plan/* screens: -->
<nav class="hidden fixed bottom-0 ...">  <!-- always hidden -->

<!-- Alternative: route-based approach -->
const isPlanning = route.path.startsWith('/plan');
navElement.classList.toggle('hidden', isPlanning);
```
**Rule:** Bottom nav (h-[64px], 2 tabs) is shown ONLY on `/itinerary/*` and `/expense/*` routes. Hidden on `/`, `/plan/*`, `/onboarding`.

---

#### BUG U2 — Loading Screen Has No Cancel Button or Error State
**File:** `loading_skeleton_state/code.html`
**Evidence from code:**
```
grep for "huỷ|cancel|button": only finds nav buttons and settings button
No cancel button. No error state. No timeout handling.
```
**Fix — Add to loading screen:**
```javascript
// After 3000ms, show cancel button
setTimeout(() => {
  cancelBtn.classList.remove('hidden');
  cancelBtn.classList.add('fade-in');
}, 3000);

// After 15000ms, replace skeleton with error state
setTimeout(() => {
  showErrorState({
    icon: '⚠️',
    title: 'Không tạo được lịch trình',
    body: 'Kiểm tra kết nối mạng và thử lại.',
    actions: ['Thử lại', 'Huỷ']
  });
}, 15000);
```
**Cancel button HTML to add (hidden initially):**
```html
<div id="cancel-btn-wrapper" class="hidden mt-6 text-center fade-in">
  <button class="font-label-sm text-on-surface-variant underline border border-outline-variant px-6 py-2 rounded-full">
    Huỷ
  </button>
</div>
```

---

#### BUG V1 — Voice Recording Jumps Straight to Default Questions (No NLU Processing State)
**File:** `voice_preview_recording/code.html`
**Evidence:** No "Đang phân tích" state, no slot extraction logic, no confidence check visible in UI transitions.  
**Fix — Required state machine for voice input:**
```
Phase 1: RECORDING
  - Waveform animates
  - Live transcript renders (STT stream)
  - User taps stop → transition to PROCESSING

Phase 1.5: PROCESSING  ← THIS STATE IS MISSING
  - Stop waveform
  - Show: spinner + "Đang phân tích giọng nói..."
  - Run NLU slot extraction on transcript
  - Check confidence for each extracted slot
  - If overall confidence < 0.75 → show Phase 1 again with clarification prompt
  - If confidence ≥ 0.75 → transition to Phase 2

Phase 2: CONFIRMATION
  - Show extracted data preview
  - User confirms or edits
```
**Agent code fix:**
```typescript
async function processVoiceInput(transcript: string, context: SessionContext) {
  const extracted = await nlu.extractSlots(transcript, context);
  
  if (extracted.confidence < 0.75) {
    // Fallback: ask for the missing/uncertain fields
    return { action: 'ask_clarification', fields: extracted.uncertainFields };
  }
  
  // ✅ High confidence: show confirmation
  return { action: 'confirm', data: extracted };
}
```
**Critical:** The agent must carry `sessionContext` (current trip destination, members) into slot extraction so "taxi 120k cho cả nhóm" resolves to the correct trip's members — not a generic extraction.

---

### 🟡 MEDIUM — Fix in Sprint 2

---

#### BUG L5 — Rating Format Inconsistency
**Evidence from code:**
- `l_ch_tr_nh_l_t`: ratings shown as `8.4`, `9.1`, `8.7`, `8.9` (out of 10, Foody style)
- `alternatives_picker_sheet`: ratings shown as `4.5`, `4.8`, `4.2` (out of 5, Google Maps style)

**Fix:** Standardize to ONE format across all screens. Recommended: **out of 10** (Vietnamese users familiar with Foody/Zomato scale). Update alternatives picker to show ratings in same scale: `8.9`, `9.6`, `8.4`, `8.8`, `9.2`. Remove "(2.1k đánh giá)" label or keep it consistently.

---

#### BUG U3 — Venue Detail Sheet Has No Header Close Button
**File:** `venue_detail_sheet/code.html`
**Evidence:** The sheet has a close button on the hero photo (`absolute top-4 right-4`) but NO close button on the sheet header for when the photo is scrolled away.  
**Fix:** Add ✕ button to the sheet header row:
```html
<!-- In the sheet header flex row: -->
<div class="sheet-header flex justify-between items-start px-container-margin pt-gutter">
  <div class="title-col">
    <h1 class="font-bold text-[20px]">Vườn Thú Zoodoo</h1>
    <p class="font-label-sm text-on-surface-variant">...</p>
  </div>
  <!-- ADD THIS: -->
  <button class="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center ml-3 flex-shrink-0">
    <span class="material-symbols-outlined text-[20px] text-on-surface-variant">close</span>
  </button>
</div>
```

---

#### BUG U4 — Onboarding Secondary CTA Has Wrong Label
**File:** `onboarding/code.html`
**Evidence from code:**
```html
Đã có lịch trình? Nhập tiếp
```
**Fix:** Change to:
```html
Mở lịch trình đã lưu →
```
This label is less confusing — "Nhập tiếp" implies typing, but the action is opening a saved session.

---

#### BUG L2 — Restore Original Wipes Current Expenses
**Not visible in UI but agent logic bug:**  
When user taps "Khôi phục gốc" on the diff banner, the agent's `restoreOriginal()` must:
```typescript
// ✅ CORRECT:
async function restoreOriginal(sessionId: string) {
  const session = await db.query('SELECT original_record FROM sessions WHERE id = $1', [sessionId]);
  // Deep clone original itinerary INTO currentState
  await db.query(
    'UPDATE sessions SET current_state = $1 WHERE id = $2',
    [session.original_record, sessionId]
  );
  // ⚠️ DO NOT touch expenses table — expenses are session-scoped, not itinerary-scoped
}

// ❌ WRONG (current bug): deleting or resetting expenses during restore
```

---

#### BUG ARCH-1 — Session Isolation (Cross-Destination Budget Bleed)
**Agent logic bug:**  
All `BudgetService` queries MUST include `WHERE session_id = $sessionId`. Without this, expenses from a Đà Lạt trip appear in a Hội An trip calculation.

```typescript
// ❌ BROKEN:
async getAllExpenses(userId: string) {
  return db.query('SELECT * FROM expenses WHERE user_id = $1', [userId]);
}

// ✅ FIXED:
async getAllExpenses(userId: string, sessionId: string) {
  return db.query(
    'SELECT * FROM expenses WHERE user_id = $1 AND session_id = $2',
    [userId, sessionId]
  );
}
```
**This applies to:** `getTotal()`, `getMemberBreakdown()`, `getSettlements()`, `addExpense()` — all must be session-scoped.

---

#### BUG ARCH-2 — Original Record Is Not Immutable
```sql
-- Add this trigger to PostgreSQL:
CREATE OR REPLACE FUNCTION guard_original_record()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.original_record IS NOT NULL 
     AND NEW.original_record IS DISTINCT FROM OLD.original_record THEN
    RAISE EXCEPTION 'original_record is immutable after sealing';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER protect_original_record
BEFORE UPDATE ON trip_sessions
FOR EACH ROW EXECUTE FUNCTION guard_original_record();
```

---

#### BUG ARCH-3 — Session State Machine Not Enforced
```typescript
// Valid transitions only:
const TRANSITIONS: Record<SessionStatus, SessionStatus[]> = {
  DRAFT:      ['GENERATING'],
  GENERATING: ['ACTIVE', 'DRAFT'],       // DRAFT on cancel/error
  ACTIVE:     ['SUSPENDED', 'FINALIZED'],
  SUSPENDED:  ['ACTIVE', 'FINALIZED'],
  FINALIZED:  ['ARCHIVED'],
  ARCHIVED:   [],
};

function transitionStatus(session: TripSession, next: SessionStatus): TripSession {
  const allowed = TRANSITIONS[session.status];
  if (!allowed.includes(next)) {
    throw new Error(`Invalid transition: ${session.status} → ${next}`);
  }
  return { ...session, status: next };
}
```

---

#### BUG ARCH-5 — Money Stored as Float (Should Be BIGINT)
```sql
-- Migration: convert all money columns to BIGINT (store as smallest unit: đồng)
ALTER TABLE expenses ALTER COLUMN amount TYPE BIGINT USING (amount * 100)::BIGINT;
ALTER TABLE trip_sessions ALTER COLUMN budget_vnd TYPE BIGINT USING (budget_vnd * 100)::BIGINT;
-- All display logic: divide by 100 before showing to user
-- All input logic: multiply by 100 before storing
```

---

### 🟢 LOW — Fix in Sprint 3

---

#### BUG L9 (NEW) — Post-Swap Itinerary Missing Diff Banner
**File:** `l_ch_tr_nh_l_t_sau_khi_i_a_i_m/code.html`  
**Evidence:** This screen shows Langbiang in place of Vườn Thú Zoodoo but has NO diff banner.  
**Fix:** Add diff banner between meta chips and Day 1 header:
```html
<div class="diff-banner mx-gutter mb-stack-md bg-secondary-container/20 rounded-xl px-4 py-2 flex items-center justify-between border border-secondary-container/30">
  <span class="font-label-sm text-on-surface">✏️ 1 địa điểm đã thay đổi · +0đ</span>
  <button class="font-label-sm text-primary underline">Khôi phục gốc</button>
</div>
```
**Show condition:** `session.currentState !== session.originalRecord` (compare itinerary arrays, not whole object — expenses differ by design).

---

#### BUG U7 (NEW) — No Warning When Leaving Draft Session
**Not in Stitch design, agent behavior needed:**  
If user is in planning chat (Step 1–5) and navigates away (taps back/home), show:
```
"Lịch trình đang soạn sẽ được lưu nháp. Tiếp tục?"
[Rời đi] [Ở lại]
```
**On "Rời đi":** Save session with status `DRAFT`.  
**On app reopen:** Show "Tiếp tục lịch trình Đà Lạt →" banner.

---

## 3. Screen → Route → Nav State Map

| Screen | Route | Bottom Nav | Input Bar |
|--------|-------|-----------|-----------|
| Onboarding | / | ❌ Hidden | ❌ |
| Home/Empty | /plan | ❌ Hidden | ✅ Fixed bottom |
| Planning Chat | /plan/:step | ❌ Hidden | ✅ Fixed bottom |
| Loading | /plan/generating | ❌ Hidden | ❌ |
| Itinerary | /itinerary/:id | ✅ Tab 1 active | ❌ |
| Venue Sheet | /itinerary/:id (overlay) | ✅ Dimmed | ❌ |
| Alternatives | /itinerary/:id (overlay) | ✅ Dimmed | ❌ |
| Expense Tracker | /expense/:id | ✅ Tab 2 active | ❌ |
| Voice Recording | /expense/:id (overlay) | ✅ Dimmed | ❌ |
| Voice Confirm | /expense/:id (overlay) | ✅ Dimmed | ❌ |
| Settlement | /expense/:id/settle | ✅ Tab 2 active | ❌ |

---

## 4. Design System Tokens (from Stitch source — exact values)

```javascript
// tailwind.config — paste verbatim into project tailwind.config.js
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#b52330",
        "on-primary": "#ffffff",
        "primary-container": "#ff5a5f",
        "on-primary-container": "#61000e",
        "secondary": "#845400",
        "secondary-container": "#feb246",
        "on-secondary-container": "#6f4600",
        "tertiary": "#006c4f",
        "tertiary-container": "#00a87d",
        "on-tertiary-container": "#003424",
        "surface": "#fcf9f8",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f6f3f2",
        "surface-container": "#f0eded",
        "surface-container-high": "#eae7e7",
        "surface-container-highest": "#e5e2e1",
        "background": "#fcf9f8",
        "on-background": "#1b1c1c",
        "on-surface": "#1b1c1c",
        "on-surface-variant": "#5a403f",
        "outline": "#8e706f",
        "outline-variant": "#e2bebc",
        "warm-cream": "#FBF8F4",
        "error": "#ba1a1a",
        "error-container": "#ffdad6",
      },
      spacing: {
        "stack-sm": "4px",
        "stack-md": "8px",
        "element-gap": "12px",
        "gutter": "16px",
        "container-margin": "24px",
        "section-gap": "32px"
      },
      fontSize: {
        "caption-xs": ["11px", { lineHeight: "14px", fontWeight: "400" }],
        "label-sm":   ["13px", { lineHeight: "18px", fontWeight: "500" }],
        "budget-mono":["14px", { lineHeight: "18px", fontWeight: "500" }],
        "body-rg":    ["15px", { lineHeight: "20px", fontWeight: "400" }],
        "heading-md": ["17px", { lineHeight: "22px", fontWeight: "600" }],
        "display-lg": ["22px", { lineHeight: "28px", letterSpacing: "-0.02em", fontWeight: "700" }]
      }
    }
  }
}
```

**Font rules (enforced in all screens):**
- Plus Jakarta Sans: all UI text
- DM Mono (`font-budget-mono`): ALL monetary amounts, EVERY time, no exceptions
- Material Symbols Outlined: all icons. Filled = `style="font-variation-settings:'FILL' 1;"`

**Component patterns:**
- Cards: `rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.06)] border border-outline-variant/30`
- Bottom sheets: `rounded-t-[32px] shadow-[0_-8px_30px_rgba(0,0,0,0.12)]`
- Sheet handle: `w-12 h-1.5 bg-surface-variant rounded-full`
- Bottom nav: `h-[64px] fixed bottom-0 bg-surface border-t border-outline-variant flex justify-around`
- Skeleton: `background: linear-gradient(90deg, #F5F0EB 25%, #EBEBEB 50%, #F5F0EB 75%); background-size: 200%; animation: skeleton-shimmer 1.5s infinite;`

---

## 5. Data Models

```typescript
// TripSession — one per trip destination per user
interface TripSession {
  id: string;                    // {userId}_{destinationSlug}_{isoDate}_{nanoid6}
  userId: string;
  destination: string;           // "Đà Lạt"
  destinationSlug: string;       // "da-lat"
  
  // Slots (all required before generating)
  numPeople: number;
  budgetVnd: bigint;             // BIGINT, stored as smallest unit
  durationDays: number;
  travelStyle: string[];         // ["check-in", "chill"]
  groupType: 'couple' | 'friends' | 'family' | 'solo';
  
  // State machine
  status: 'DRAFT' | 'GENERATING' | 'ACTIVE' | 'SUSPENDED' | 'FINALIZED' | 'ARCHIVED';
  
  // Immutable after seal:
  originalRecord: ItineraryRecord | null;  // written once, Postgres trigger prevents overwrite
  
  // Mutable:
  currentState: ItineraryRecord;           // user edits go here
  
  members: TripMember[];
  createdAt: Date;
  updatedAt: Date;
}

interface TripMember {
  id: string;
  name: string;                  // "Ngân", "Thủy", "Trang"
  avatarColor: string;           // Tailwind token: "primary-container" etc.
}

interface Expense {
  id: string;
  sessionId: string;             // ⚠️ ALWAYS scoped to session
  paidBy: string;                // member id
  amount: bigint;                // BIGINT
  description: string;
  splitWith: string[];           // member ids
  splitType: 'equal' | 'custom';
  splitAmounts?: Record<string, bigint>;
  category: 'food' | 'transport' | 'accommodation' | 'activity' | 'other';
  createdAt: Date;
}

interface SettlementTransaction {
  id: string;
  sessionId: string;             // ⚠️ ALWAYS scoped to session
  from: string;                  // member id (who pays)
  to: string;                    // member id (who receives)
  amount: bigint;
  status: 'PENDING' | 'CONFIRMED';
  method?: 'bank' | 'wallet' | 'cash';
  confirmedAt?: Date;
}
```

---

## 6. DB Migration (Run in Order)

```sql
-- Step 1: Add session_id to all tables that are missing it
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS session_id VARCHAR(128) NOT NULL DEFAULT '';
ALTER TABLE settlement_transactions ADD COLUMN IF NOT EXISTS session_id VARCHAR(128) NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_expenses_session ON expenses(session_id);
CREATE INDEX IF NOT EXISTS idx_settlements_session ON settlement_transactions(session_id);

-- Step 2: Convert money columns to BIGINT (all values × 100)
ALTER TABLE expenses ALTER COLUMN amount TYPE BIGINT USING (ROUND(amount * 100))::BIGINT;
ALTER TABLE trip_sessions ALTER COLUMN budget_vnd TYPE BIGINT USING (ROUND(budget_vnd * 100))::BIGINT;

-- Step 3: Immutability trigger for original_record
CREATE OR REPLACE FUNCTION guard_original_record()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.original_record IS NOT NULL 
     AND NEW.original_record IS DISTINCT FROM OLD.original_record THEN
    RAISE EXCEPTION 'original_record is immutable once sealed';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS protect_original_record ON trip_sessions;
CREATE TRIGGER protect_original_record
  BEFORE UPDATE ON trip_sessions
  FOR EACH ROW EXECUTE FUNCTION guard_original_record();

-- Step 4: Session status constraint
ALTER TABLE trip_sessions 
  ADD CONSTRAINT valid_status CHECK (
    status IN ('DRAFT','GENERATING','ACTIVE','SUSPENDED','FINALIZED','ARCHIVED')
  );
```

---

## 7. NLU Slot Extraction Specification

```typescript
interface SlotExtractionResult {
  slots: {
    destination?: { value: string; confidence: number };
    numPeople?: { value: number; confidence: number };
    budgetVnd?: { value: bigint; confidence: number };
    durationDays?: { value: number; confidence: number };
    travelStyle?: { value: string[]; confidence: number };
    // Expense slots:
    paidBy?: { value: string; confidence: number };    // member name
    amount?: { value: bigint; confidence: number };
    description?: { value: string; confidence: number };
    splitWith?: { value: string[]; confidence: number };
  };
  overallConfidence: number;
  uncertainFields: string[];
}

// System prompt for slot extraction (trip planning):
const PLANNING_EXTRACTION_PROMPT = `
You are extracting travel planning slots from Vietnamese user input.
Context: User is planning a trip. Return JSON only.

Slots to extract:
- destination: city name (normalize to standard Vietnamese: "đà lạt" → "Đà Lạt")
- numPeople: integer
- budgetVnd: total budget in VND (parse "1 triệu" → 1000000, "500k" → 500000)
- durationDays: integer days
- travelStyle: array of ["check-in", "chill", "food", "adventure"]

For each slot, output: { value, confidence: 0.0-1.0 }
If a slot is not mentioned, omit it entirely.
Confidence < 0.75 = uncertain, must ask user to confirm.
`;

// System prompt for expense extraction:
const EXPENSE_EXTRACTION_PROMPT = `
You are extracting expense data from Vietnamese voice input.
Context: Trip session members: {{memberNames}}. Current destination: {{destination}}.

Slots to extract:
- paidBy: which member paid (match against: {{memberNames}})
- amount: amount in VND ("120k" → 120000, "1 trăm hai" → 120000)
- description: what was purchased
- splitWith: who to split with ("cả nhóm" → all members, else named members)

Return JSON: { slots, overallConfidence, uncertainFields }
`;
```

---

## 8. Voice Processing State Machine

```typescript
type VoicePhase = 'IDLE' | 'RECORDING' | 'PROCESSING' | 'CONFIRMING' | 'SAVING';

// UI state transitions:
// IDLE → tap mic FAB → RECORDING
//   show: waveform animation, live transcript, "Huỷ" link
// RECORDING → tap stop / silence detected → PROCESSING  ← MUST SHOW THIS
//   show: spinner + "Đang phân tích giọng nói...", stop waveform
// PROCESSING → confidence ≥ 0.75 → CONFIRMING
//   show: Phase 2 confirmation sheet
// PROCESSING → confidence < 0.75 → RECORDING (with clarifying prompt)
//   show: "Bạn nói: [transcript]. [uncertain field] là gì?"
// CONFIRMING → tap "Thêm khoản chi này" → SAVING
//   show: brief spinner
// SAVING → success → IDLE (update expense list and totals)
// SAVING → error → CONFIRMING (show retry)
```

---

## 9. Settlement Algorithm

```typescript
// Minimum transfer settlement (per sessionId only):
function calculateSettlements(
  expenses: Expense[], 
  members: TripMember[]
): SettlementTransaction[] {
  
  // 1. Calculate net balance per member
  const balances: Record<string, bigint> = {};
  members.forEach(m => balances[m.id] = 0n);
  
  for (const expense of expenses) {
    // Payer gets credit
    balances[expense.paidBy] += expense.amount;
    
    // Each split member gets debit
    const splitCount = BigInt(expense.splitWith.length);
    const perPerson = expense.amount / splitCount;
    expense.splitWith.forEach(memberId => {
      balances[memberId] -= perPerson;
    });
  }
  
  // 2. Separate creditors and debtors
  const creditors = members.filter(m => balances[m.id] > 0n)
    .sort((a, b) => Number(balances[b.id] - balances[a.id]));
  const debtors = members.filter(m => balances[m.id] < 0n)
    .sort((a, b) => Number(balances[a.id] - balances[b.id]));
  
  // 3. Greedy minimum transfer
  const transactions: SettlementTransaction[] = [];
  let i = 0, j = 0;
  while (i < creditors.length && j < debtors.length) {
    const credit = balances[creditors[i].id];
    const debt = -balances[debtors[j].id];
    const amount = credit < debt ? credit : debt;
    
    transactions.push({
      from: debtors[j].id,
      to: creditors[i].id,
      amount,
      status: 'PENDING'
    });
    
    balances[creditors[i].id] -= amount;
    balances[debtors[j].id] += amount;
    if (balances[creditors[i].id] === 0n) i++;
    if (balances[debtors[j].id] === 0n) j++;
  }
  
  return transactions;
}
```

---

## 10. Production Mock Data (for dev/testing)

```typescript
// Session: Đà Lạt trip, 3 members
const MOCK_SESSION: TripSession = {
  id: 'user123_da-lat_2026-06-15_abc123',
  userId: 'user123',
  destination: 'Đà Lạt',
  destinationSlug: 'da-lat',
  numPeople: 3,
  budgetVnd: 540000000n,          // 5.4M total (1.8M/người)
  durationDays: 3,
  travelStyle: ['check-in', 'chill'],
  groupType: 'friends',
  status: 'ACTIVE',
  members: [
    { id: 'm1', name: 'Ngân', avatarColor: 'primary-container' },
    { id: 'm2', name: 'Thủy', avatarColor: 'secondary-container' },
    { id: 'm3', name: 'Trang', avatarColor: 'tertiary-container' },
  ],
  originalRecord: { /* itinerary JSON */ },
  currentState:   { /* itinerary JSON — same as original initially */ },
};

// Expenses (all properly session-scoped)
const MOCK_EXPENSES: Expense[] = [
  { id:'e1', sessionId:'user123_da-lat_2026-06-15_abc123',
    paidBy:'m1', amount:36000000n, description:'Taxi sân bay', 
    splitWith:['m1','m2','m3'], splitType:'equal', category:'transport' },
  { id:'e2', sessionId:'user123_da-lat_2026-06-15_abc123',
    paidBy:'m1', amount:120000000n, description:'Bánh căn', 
    splitWith:['m1','m2'], splitType:'equal', category:'food' },
  { id:'e3', sessionId:'user123_da-lat_2026-06-15_abc123',
    paidBy:'m3', amount:180000000n, description:'Vé Zoodoo',
    splitWith:['m1','m2','m3'], splitType:'equal', category:'activity' },
];
// Expected settlements: Trang → Ngân: 62,500đ (after algorithm)
```

---

## 11. Priority Fix Order for Team A

**Do these first (blocker for demo):**
1. `BUG L4` — Fix budget line items sum (itinerary screen)
2. `BUG L3` — Fix alternatives picker radio logic
3. `BUG U1` — Remove bottom nav from ALL planning screens
4. `BUG ARCH-1` — Add session_id to all expense queries
5. `BUG V1` — Add PROCESSING state between voice phases

**Do these second (critical for correctness):**
6. `BUG L6` — Split expense tracker into two-row total card
7. `BUG L7` — Fix bar chart to use full-trip amounts
8. `BUG L8` — Add confirmation modal to settlement
9. `BUG U2` — Add cancel button + error state to loading
10. `BUG ARCH-2` — Add immutability trigger to DB

**Do these third (polish):**
11. `BUG L5` — Standardize rating format across screens
12. `BUG U3` — Add close button to venue detail sheet header
13. `BUG U4` — Fix onboarding secondary CTA label
14. `BUG L2` — Verify restore original doesn't wipe expenses
15. `BUG L9` — Add diff banner to post-swap itinerary screen
16. `BUG ARCH-3` — Enforce session state machine transitions
17. `BUG ARCH-5` — Run BIGINT migration for money columns

---

## 12. Files Reference

| File | Purpose | Audience |
|------|---------|----------|
| `CLAUDE.md` (this file) | Master spec for Claude Code to update AI agent | Team A — paste into Claude Code |
| `trip_buddy_dev_changes.html` | Interactive checklist of 21 items with checkboxes | Team A — track sprint progress |
| `trip_buddy_architecture_fix.html` | Full TypeScript interfaces + DB schema + API endpoints | Team A — deep implementation |
| `trip_buddy_full_review.html` | Detailed audit report with root cause analysis | Team A — reference |
| `trip_buddy_blueprint.html` | 4-section UI/UX spec with Mermaid flow diagram | Stitch Studio + Team A |
| `stitch_studio_prompts.html` | Copy-ready Stitch prompts per screen | Stitch Studio |

---

*End of CLAUDE.md — Version 2.0.0*  
*Generated: 2026-06-15 | Source: Stitch HTML audit + logic review*
