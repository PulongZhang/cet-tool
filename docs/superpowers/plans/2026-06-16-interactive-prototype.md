# Interactive Prototype Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the existing single-file HTML prototype into a clickable process demo with navigation, simulated workflow state, modal dialogs, and status updates.

**Architecture:** Keep the prototype as one self-contained HTML file so it can be opened directly in a browser and shared with stakeholders. Add small, focused CSS utilities, semantic `data-action` hooks on buttons, and a compact JavaScript state machine that simulates PRD workflow transitions without backend dependencies.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript, local browser only.

---

## File Structure

- Modify: `docs/prototypes/performance-review-tool-prototype.html`
  - Responsibility: static PC-side prototype for stakeholder review.
  - Changes: add flow status strip, clickable action buttons, modal dialog, toast notification, simulated state transitions, and deterministic page navigation.
- No new runtime dependencies.
- No backend, build tool, package manager, framework, or network call.

## Interaction Scope

The enhanced prototype will support these demo interactions:

| Interaction | Expected prototype behavior |
|---|---|
| 首页“进入评分” | Navigate to 直接上级评分 page |
| 首页“查看超时名单” | Navigate to 直接上级评分 page and show a toast about highlighted overdue users |
| 自评“保存草稿” | Show success toast; keep page on 我的自评 |
| 自评“提交自评” | Change self status from 草稿 to 已提交; increase self submitted count; navigate to 首页 |
| 直接上级“评分/跳过自评后评分” | Navigate to scoring detail section and show toast |
| 直接上级“保存草稿” | Show success toast |
| 直接上级“提交评分” | Increase scoring completion count; update flow stage; navigate to 审阅 page |
| 审阅“调整” | Open adjustment modal requiring reason |
| 审阅“提交审阅结果” | Update review stage and navigate to 结果 page |
| 客观数据“上传 Excel” | Simulate import success/failure summary and show toast |
| 结果“执行/重算” | Simulate calculation success and set result version to INITIAL v1 |
| 结果“生成最终版” | Set result version to FINAL v1 |
| 导出按钮 | Open export confirmation modal, then show export success toast |
| 撤回动作 | Open withdraw reason modal and show audit-style success toast |

---

### Task 1: Add reusable visual components

**Files:**
- Modify: `docs/prototypes/performance-review-tool-prototype.html`

- [ ] **Step 1: Add CSS for status strip, toast, modal, and row highlight**

Insert this CSS block before the existing `@media (max-width: 1100px)` rule:

```css
    .demo-status {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    .demo-status .status-item {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
      font-size: 12px;
    }

    .demo-status .status-item strong {
      display: block;
      font-size: 14px;
      color: var(--text);
      margin-top: 4px;
    }

    .toast {
      position: fixed;
      right: 24px;
      bottom: 24px;
      background: #111827;
      color: #fff;
      padding: 12px 14px;
      border-radius: 12px;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.22);
      opacity: 0;
      transform: translateY(10px);
      pointer-events: none;
      transition: opacity .18s ease, transform .18s ease;
      z-index: 50;
      max-width: 360px;
      font-size: 13px;
      line-height: 1.5;
    }

    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, .48);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 40;
    }

    .modal-backdrop.show { display: flex; }

    .modal {
      width: min(620px, 100%);
      background: #fff;
      border-radius: 18px;
      box-shadow: 0 24px 64px rgba(15, 23, 42, .3);
      padding: 20px;
    }

    .modal-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 14px;
    }

    .modal-header h2 {
      margin: 0;
      font-size: 20px;
    }

    .modal-body {
      color: #374151;
      font-size: 14px;
      line-height: 1.6;
    }

    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 18px;
    }

    .row-highlight {
      outline: 2px solid #f59e0b;
      background: #fffbeb;
      transition: background .2s ease;
    }
```

- [ ] **Step 2: Add global status strip markup**

Inside `<main class="main">`, immediately after the existing `.topbar` block and before the first `<section class="page active" id="dashboard">`, add:

```html
      <div class="demo-status" aria-label="当前演示状态">
        <div class="status-item">当前周期<strong id="statusCycle">2026-Q2</strong></div>
        <div class="status-item">当前阶段<strong id="statusStage">直接上级评分</strong></div>
        <div class="status-item">操作身份<strong id="statusRole">直接上级 / 部门负责人</strong></div>
        <div class="status-item">自评进度<strong id="statusSelf">182/200</strong></div>
        <div class="status-item">结果版本<strong id="statusVersion">未计算</strong></div>
      </div>
```

- [ ] **Step 3: Add toast and modal containers**

Insert these elements immediately before the closing `</body>` tag, above the existing `<script>` tag if the script is still before `</body>`; otherwise insert above `</body>` and keep the script below these elements:

```html
  <div class="toast" id="toast" role="status" aria-live="polite"></div>

  <div class="modal-backdrop" id="modalBackdrop" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
    <div class="modal">
      <div class="modal-header">
        <h2 id="modalTitle">操作确认</h2>
        <button class="btn" data-action="modal-close">关闭</button>
      </div>
      <div class="modal-body" id="modalBody"></div>
      <div class="modal-actions" id="modalActions"></div>
    </div>
  </div>
```

- [ ] **Step 4: Verify structural markers**

Run:

```bash
python - <<'PY'
from pathlib import Path
p = Path('docs/prototypes/performance-review-tool-prototype.html')
text = p.read_text(encoding='utf-8')
markers = [
    'class="demo-status"',
    'id="statusStage"',
    'class="toast" id="toast"',
    'class="modal-backdrop" id="modalBackdrop"',
    '.row-highlight',
]
for marker in markers:
    print(marker, marker in text)
if not all(marker in text for marker in markers):
    raise SystemExit(1)
PY
```

Expected: all marker checks print `True`.

---

### Task 2: Add action hooks to existing buttons

**Files:**
- Modify: `docs/prototypes/performance-review-tool-prototype.html`

- [ ] **Step 1: Add dashboard action hooks**

Update the dashboard table buttons:

```html
<button class="btn" data-action="go-manager">进入评分</button>
<button class="btn" data-action="go-overdue">查看名单</button>
<button class="btn" disabled>暂不可处理</button>
```

- [ ] **Step 2: Add self-review action hooks and dynamic status marker**

In the 我的自评 page, change the current status display to:

```html
<div class="label">当前状态</div><div><span class="tag orange" id="selfStatusTag">草稿</span></div>
```

Change the self-review buttons to:

```html
<div></div><div class="btnrow"><button class="btn" data-action="save-self-draft">保存草稿</button><button class="btn primary" data-action="submit-self">提交自评</button></div>
```

- [ ] **Step 3: Add manager page action hooks and overdue row marker**

Update the direct manager list rows so the overdue row has an ID:

```html
<tr id="overdueRow"><td>E002</td><td>王五</td><td>P1-3</td><td><span class="tag red">超时</span></td><td>待直接上级评分</td><td><button class="btn" data-action="score-overdue">跳过自评后评分</button></td></tr>
```

Update the first row scoring button:

```html
<button class="btn primary" data-action="open-score-detail">评分</button>
```

Update the scoring detail buttons:

```html
<div></div><div class="btnrow"><button class="btn" data-action="save-manager-draft">保存草稿</button><button class="btn primary" data-action="submit-manager-score">提交评分</button></div>
```

- [ ] **Step 4: Add review page action hooks**

Update every review table adjustment button to use:

```html
<button class="btn" data-action="open-adjustment">调整</button>
```

Update the review submit button:

```html
<button class="btn primary" data-action="submit-review">提交审阅结果</button>
```

Update the export current range button:

```html
<button class="btn" data-action="export-range">导出当前范围</button>
```

- [ ] **Step 5: Add objective and result action hooks**

Update 客观数据导入 buttons:

```html
<button class="btn" data-action="download-objective-template">下载预填模板</button>
<button class="btn primary" data-action="upload-objective">上传 Excel</button>
<button class="btn" data-action="download-error-report">下载错误报告</button>
```

Update result page buttons:

```html
<button class="btn primary" data-action="run-calculation">执行/重算</button>
<button class="btn" data-action="export-initial">导出初评结果</button>
<button class="btn green" data-action="finalize-result">生成最终版</button>
<button class="btn" data-action="export-final">导出最终结果</button>
```

- [ ] **Step 6: Add admin action hooks**

Update admin buttons:

```html
<button class="btn" data-action="edit-cycle">编辑周期</button>
<button class="btn red" data-action="close-cycle">关闭周期</button>
<button class="btn" data-action="download-employee-template">下载人员模板</button>
<button class="btn primary" data-action="import-employees">导入人员</button>
<button class="btn" data-action="init-accounts">初始化账号</button>
```

- [ ] **Step 7: Verify action markers**

Run:

```bash
python - <<'PY'
from pathlib import Path
p = Path('docs/prototypes/performance-review-tool-prototype.html')
text = p.read_text(encoding='utf-8')
actions = [
    'data-action="go-manager"',
    'data-action="submit-self"',
    'data-action="submit-manager-score"',
    'data-action="open-adjustment"',
    'data-action="upload-objective"',
    'data-action="run-calculation"',
    'data-action="finalize-result"',
    'data-action="close-cycle"',
]
for action in actions:
    print(action, action in text)
if not all(action in text for action in actions):
    raise SystemExit(1)
PY
```

Expected: all action marker checks print `True`.

---

### Task 3: Replace the basic script with stateful prototype logic

**Files:**
- Modify: `docs/prototypes/performance-review-tool-prototype.html`

- [ ] **Step 1: Replace the existing `<script>` contents**

Replace the current script block at the bottom of the file with this complete script:

```html
  <script>
    const titles = {
      dashboard: '首页仪表盘',
      self: '我的自评',
      manager: '直接上级评分',
      review: '间接/部门审阅',
      objective: '客观数据导入',
      result: '计算结果与导出',
      admin: '周期与人员管理'
    };

    const demoState = {
      cycle: '2026-Q2',
      stage: '直接上级评分',
      role: '直接上级 / 部门负责人',
      selfSubmitted: 182,
      total: 200,
      scored: 128,
      resultVersion: '未计算',
      selfStatus: '草稿',
      calculationDone: false,
      finalDone: false
    };

    function el(selector) {
      return document.querySelector(selector);
    }

    function all(selector) {
      return Array.from(document.querySelectorAll(selector));
    }

    function showPage(id, message) {
      all('#nav button').forEach(b => b.classList.toggle('active', b.dataset.page === id));
      all('.page').forEach(p => p.classList.toggle('active', p.id === id));
      el('#pageTitle').textContent = titles[id];
      if (message) showToast(message);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function renderStatus() {
      el('#statusCycle').textContent = demoState.cycle;
      el('#statusStage').textContent = demoState.stage;
      el('#statusRole').textContent = demoState.role;
      el('#statusSelf').textContent = `${demoState.selfSubmitted}/${demoState.total}`;
      el('#statusVersion').textContent = demoState.resultVersion;
      const selfTag = el('#selfStatusTag');
      if (selfTag) {
        selfTag.textContent = demoState.selfStatus;
        selfTag.className = demoState.selfStatus === '已提交' ? 'tag green' : 'tag orange';
      }
    }

    let toastTimer;
    function showToast(message) {
      const toast = el('#toast');
      toast.textContent = message;
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    }

    function closeModal() {
      el('#modalBackdrop').classList.remove('show');
      el('#modalBody').innerHTML = '';
      el('#modalActions').innerHTML = '';
    }

    function openModal(title, bodyHtml, actionsHtml) {
      el('#modalTitle').textContent = title;
      el('#modalBody').innerHTML = bodyHtml;
      el('#modalActions').innerHTML = actionsHtml;
      el('#modalBackdrop').classList.add('show');
    }

    function requireReasonModal(title, intro, confirmAction, confirmLabel) {
      openModal(
        title,
        `${intro}<textarea id="modalReason" placeholder="请输入原因，保存后会进入调整/审计记录" style="margin-top:12px"></textarea>`,
        `<button class="btn" data-action="modal-close">取消</button><button class="btn primary" data-action="${confirmAction}">${confirmLabel}</button>`
      );
    }

    function flashOverdueRow() {
      const row = el('#overdueRow');
      if (!row) return;
      row.classList.add('row-highlight');
      setTimeout(() => row.classList.remove('row-highlight'), 2200);
    }

    function updateProgressText() {
      const cards = all('.metric');
      if (cards.length >= 3) {
        cards[1].textContent = `${Math.round(demoState.selfSubmitted / demoState.total * 100)}%`;
        cards[2].textContent = `${Math.round(demoState.scored / demoState.total * 100)}%`;
      }
    }

    function handleAction(action) {
      switch (action) {
        case 'go-manager':
          showPage('manager', '已进入直接上级评分页。');
          break;
        case 'go-overdue':
          showPage('manager', '已定位超时未自评人员。');
          setTimeout(flashOverdueRow, 250);
          break;
        case 'save-self-draft':
          showToast('自评草稿已保存，当前仍可继续编辑。');
          break;
        case 'submit-self':
          demoState.selfStatus = '已提交';
          demoState.selfSubmitted = Math.min(demoState.total, demoState.selfSubmitted + 1);
          demoState.stage = '直接上级评分';
          renderStatus();
          updateProgressText();
          showPage('dashboard', '自评已提交，系统已生成直接上级待办。');
          break;
        case 'open-score-detail':
          showToast('已打开李四的评分详情，可在右侧填写上级评分。');
          break;
        case 'score-overdue':
          showToast('王五自评已超时，原型演示允许直接上级跳过自评后评分。');
          break;
        case 'save-manager-draft':
          showToast('上级评分草稿已保存。');
          break;
        case 'submit-manager-score':
          demoState.scored = Math.min(demoState.total, demoState.scored + 1);
          demoState.stage = '间接上级审阅';
          renderStatus();
          updateProgressText();
          showPage('review', '评分已提交，记录进入间接上级审阅。');
          break;
        case 'open-adjustment':
          requireReasonModal('调整等级', '请选择调整后等级并填写原因。<select style="margin-top:12px"><option>B+</option><option>A</option><option>A+</option><option>B</option></select>', 'confirm-adjustment', '保存调整');
          break;
        case 'confirm-adjustment':
          closeModal();
          showToast('调整已保存：A → B+，原因已进入调整历史。');
          break;
        case 'submit-review':
          demoState.stage = 'HR 计算与结果输出';
          renderStatus();
          showPage('result', '审阅结果已提交，HR 可执行加权计算。');
          break;
        case 'export-range':
          openModal('导出当前范围', '将导出当前审阅范围内人员评分结果，包含调整历史。', '<button class="btn" data-action="modal-close">取消</button><button class="btn primary" data-action="confirm-export-range">确认导出</button>');
          break;
        case 'confirm-export-range':
          closeModal();
          showToast('当前范围导出任务已创建。');
          break;
        case 'download-objective-template':
          showToast('已模拟下载预填人员名单的客观数据模板。');
          break;
        case 'upload-objective':
          showToast('客观数据导入完成：成功 196 条，失败 4 条，可下载错误报告。');
          break;
        case 'download-error-report':
          showToast('已模拟下载错误报告 Excel。');
          break;
        case 'run-calculation':
          demoState.resultVersion = 'INITIAL v1';
          demoState.calculationDone = true;
          demoState.stage = '初评结果已生成';
          renderStatus();
          showToast('加权计算完成，已生成初评结果版本 INITIAL v1。');
          break;
        case 'export-initial':
          openModal('导出初评结果', '将导出 INITIAL v1 初评结果，供部门经理线下沟通反馈。', '<button class="btn" data-action="modal-close">取消</button><button class="btn primary" data-action="confirm-export-initial">确认导出</button>');
          break;
        case 'confirm-export-initial':
          closeModal();
          showToast('初评结果导出任务已创建。');
          break;
        case 'finalize-result':
          demoState.resultVersion = 'FINAL v1';
          demoState.finalDone = true;
          demoState.stage = '最终结果已确认';
          renderStatus();
          showToast('最终结果版本 FINAL v1 已生成。');
          break;
        case 'export-final':
          openModal('导出最终结果', '将导出 FINAL v1 正式结果，包含人员信息、自评、上级评分、客观数据、加权明细、最终等级和调整历史。', '<button class="btn" data-action="modal-close">取消</button><button class="btn green" data-action="confirm-export-final">确认导出</button>');
          break;
        case 'confirm-export-final':
          closeModal();
          showToast('最终结果导出任务已创建。');
          break;
        case 'edit-cycle':
          openModal('编辑周期', '演示字段：周期名称、起止日期、自评截止日期、评分截止日期。', '<button class="btn primary" data-action="modal-close">知道了</button>');
          break;
        case 'close-cycle':
          requireReasonModal('关闭周期', '关闭后所有业务页面只读。请填写关闭说明。', 'confirm-close-cycle', '确认关闭');
          break;
        case 'confirm-close-cycle':
          closeModal();
          demoState.stage = '周期已关闭';
          renderStatus();
          showToast('周期已关闭，原型进入只读演示状态。');
          break;
        case 'download-employee-template':
          showToast('已模拟下载人员名单导入模板。');
          break;
        case 'import-employees':
          showToast('人员名单导入校验通过，已生成周期人员快照和考核记录。');
          break;
        case 'init-accounts':
          showToast('账号初始化完成：普通员工自动创建，HRBP/ADMIN 由后台维护。');
          break;
        case 'modal-close':
          closeModal();
          break;
      }
    }

    all('#nav button').forEach(btn => {
      btn.addEventListener('click', () => showPage(btn.dataset.page));
    });

    document.addEventListener('click', event => {
      const actionTarget = event.target.closest('[data-action]');
      if (!actionTarget) return;
      event.preventDefault();
      handleAction(actionTarget.dataset.action);
    });

    el('#modalBackdrop').addEventListener('click', event => {
      if (event.target.id === 'modalBackdrop') closeModal();
    });

    renderStatus();
  </script>
```

- [ ] **Step 2: Verify script functions exist**

Run:

```bash
python - <<'PY'
from pathlib import Path
p = Path('docs/prototypes/performance-review-tool-prototype.html')
text = p.read_text(encoding='utf-8')
markers = [
    'const demoState = {',
    'function showPage(id, message)',
    'function renderStatus()',
    'function showToast(message)',
    'function openModal(title, bodyHtml, actionsHtml)',
    'function handleAction(action)',
    "case 'submit-self':",
    "case 'run-calculation':",
    "case 'finalize-result':",
]
for marker in markers:
    print(marker, marker in text)
if not all(marker in text for marker in markers):
    raise SystemExit(1)
PY
```

Expected: all marker checks print `True`.

---

### Task 4: Add visible guidance for stakeholder demos

**Files:**
- Modify: `docs/prototypes/performance-review-tool-prototype.html`

- [ ] **Step 1: Add demo guide card to dashboard**

Inside the dashboard page, after the flow progress card and before the metric cards, add:

```html
        <div class="card" style="margin-bottom:16px">
          <h2>演示指引</h2>
          <p class="muted">建议按以下顺序点击，向需求方演示 V1 主流程：</p>
          <div class="btnrow">
            <button class="btn" data-action="submit-self">1. 提交自评</button>
            <button class="btn" data-action="go-manager">2. 进入评分</button>
            <button class="btn" data-action="submit-manager-score">3. 提交上级评分</button>
            <button class="btn" data-action="open-adjustment">4. 审阅调整</button>
            <button class="btn" data-action="submit-review">5. 提交审阅</button>
            <button class="btn" data-action="run-calculation">6. 执行计算</button>
            <button class="btn" data-action="finalize-result">7. 生成最终版</button>
            <button class="btn" data-action="export-final">8. 导出最终结果</button>
          </div>
        </div>
```

- [ ] **Step 2: Add note that this is a simulation**

Add this note below the demo guide card:

```html
        <div class="hint" style="margin-bottom:16px">
          当前原型为本地静态流程演示：按钮会模拟状态变化、弹窗确认和页面跳转，不连接真实后端，也不解析真实 Excel。
        </div>
```

- [ ] **Step 3: Verify demo guide markers**

Run:

```bash
python - <<'PY'
from pathlib import Path
p = Path('docs/prototypes/performance-review-tool-prototype.html')
text = p.read_text(encoding='utf-8')
markers = ['演示指引', '1. 提交自评', '8. 导出最终结果', '本地静态流程演示']
for marker in markers:
    print(marker, marker in text)
if not all(marker in text for marker in markers):
    raise SystemExit(1)
PY
```

Expected: all marker checks print `True`.

---

### Task 5: Final verification

**Files:**
- Verify: `docs/prototypes/performance-review-tool-prototype.html`

- [ ] **Step 1: Run static smoke verification**

Run:

```bash
python - <<'PY'
from pathlib import Path
p = Path('docs/prototypes/performance-review-tool-prototype.html')
text = p.read_text(encoding='utf-8')
checks = {
    'exists': p.exists(),
    'has_doctype': text.startswith('<!doctype html>'),
    'has_status_strip': 'class="demo-status"' in text,
    'has_modal': 'id="modalBackdrop"' in text,
    'has_toast': 'id="toast"' in text,
    'has_actions': text.count('data-action=') >= 25,
    'has_state': 'const demoState = {' in text,
    'has_navigation': 'function showPage(id, message)' in text,
    'has_calculation_flow': "case 'run-calculation':" in text,
    'has_final_export_flow': "case 'export-final':" in text,
}
for key, value in checks.items():
    print(f'{key}: {value}')
print(f'bytes: {p.stat().st_size}')
if not all(checks.values()):
    raise SystemExit(1)
PY
```

Expected: every check prints `True` and the command exits with code 0.

- [ ] **Step 2: Manual browser smoke test**

Open this local file in a browser:

```text
D:\CETWorkSpace\cet-tool\docs\prototypes\performance-review-tool-prototype.html
```

Click this path:

```text
首页仪表盘 → 1. 提交自评 → 2. 进入评分 → 提交评分 → 调整 → 保存调整 → 提交审阅结果 → 执行/重算 → 生成最终版 → 导出最终结果 → 确认导出
```

Expected visible behavior:

- Left navigation changes active page.
- Top status strip updates current stage and result version.
- Toast appears after simulated actions.
- Adjustment and export actions open modal dialogs.
- Final export confirmation shows success toast.

- [ ] **Step 3: Check Git status**

Run:

```bash
git status --short --branch
```

Expected: `docs/` remains uncommitted unless the user explicitly asks to commit.
