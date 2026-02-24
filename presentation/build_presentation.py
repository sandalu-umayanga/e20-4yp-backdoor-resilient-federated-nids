#!/usr/bin/env python3
"""Build the progress presentation HTML with embedded t-SNE images."""
import base64, os, json

# ── Load images ──────────────────────────────────────────────────────────
TSNE_DIR = os.path.join(os.path.dirname(__file__), "experiment_results", "tsne")
def img(name):
    path = os.path.join(TSNE_DIR, name)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"

IMG_CLEAN    = img("tsne_clean_baseline.png")
IMG_BD_AVG   = img("tsne_backdoor_fedavg.png")
IMG_BD_MED   = img("tsne_backdoor_median.png")
IMG_BD_FLAME = img("tsne_backdoor_flame.png")
IMG_MR_AVG   = img("tsne_model_replace_fedavg.png")

# ── HTML template ────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FYP Progress – Backdoor-Resilient Federated NIDS</title>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --card: #334155;
  --accent: #38bdf8; --accent2: #818cf8; --green: #4ade80;
  --red: #f87171; --yellow: #fbbf24; --text: #f1f5f9; --muted: #94a3b8;
  --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
}}
* {{ margin:0; padding:0; box-sizing: border-box; }}
body {{ font-family: var(--font); background: var(--bg); color: var(--text);
        overflow: hidden; height: 100vh; }}

/* ── slide system ─────────────────────────────────── */
.slide {{ display:none; flex-direction:column; justify-content:center;
          align-items:center; height:100vh; padding: 40px 60px;
          animation: fadeIn .35s ease; }}
.slide.active {{ display:flex; }}
@keyframes fadeIn {{ from{{opacity:0;transform:translateY(12px)}} to{{opacity:1;transform:translateY(0)}} }}

/* ── nav bar ──────────────────────────────────────── */
.nav {{ position:fixed; bottom:0; left:0; right:0; height:48px;
        background: rgba(15,23,42,.92); backdrop-filter:blur(8px);
        display:flex; align-items:center; justify-content:center; gap:12px;
        z-index:100; border-top:1px solid rgba(56,189,248,.15); }}
.nav button {{ background:none; border:none; color:var(--muted); font-size:22px;
               cursor:pointer; padding:4px 12px; transition:.15s; }}
.nav button:hover {{ color:var(--accent); }}
.nav .counter {{ font-size:13px; color:var(--muted); min-width:60px; text-align:center; }}

/* ── typography ───────────────────────────────────── */
h1 {{ font-size:2.6rem; font-weight:800; margin-bottom:12px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
h2 {{ font-size:1.9rem; font-weight:700; margin-bottom:18px; color:var(--accent); }}
h3 {{ font-size:1.35rem; color:var(--accent2); margin-bottom:10px; }}
p, li {{ font-size:1.05rem; line-height:1.7; color:var(--text); }}
.subtitle {{ font-size:1.2rem; color:var(--muted); margin-bottom:24px; }}
ul {{ list-style:none; padding:0; }}
ul li::before {{ content:'▸ '; color:var(--accent); font-weight:700; }}
ul li {{ margin-bottom:8px; }}

/* ── cards / grid ─────────────────────────────────── */
.card {{ background:var(--surface); border:1px solid rgba(56,189,248,.12);
         border-radius:14px; padding:24px 30px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; width:100%; max-width:1100px; }}
.grid3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; width:100%; max-width:1150px; }}
.wide {{ width:100%; max-width:1100px; }}

/* ── table ────────────────────────────────────────── */
table {{ border-collapse:collapse; width:100%; font-size:.92rem; }}
th {{ background:var(--card); color:var(--accent); padding:10px 14px;
      text-align:left; font-weight:600; white-space:nowrap; }}
td {{ padding:9px 14px; border-bottom:1px solid rgba(148,163,184,.12); }}
tr:hover td {{ background:rgba(56,189,248,.04); }}

/* ── stat boxes ───────────────────────────────────── */
.stat {{ text-align:center; }}
.stat .num {{ font-size:2.4rem; font-weight:800; }}
.stat .label {{ font-size:.85rem; color:var(--muted); margin-top:4px; }}
.green {{ color:var(--green); }} .red {{ color:var(--red); }}
.yellow {{ color:var(--yellow); }} .blue {{ color:var(--accent); }}

/* ── image ────────────────────────────────────────── */
.tsne-img {{ max-height:52vh; max-width:90%; border-radius:10px;
             border:1px solid rgba(56,189,248,.15); margin-top:12px; }}
.tsne-row {{ display:flex; gap:18px; justify-content:center; align-items:flex-start; }}
.tsne-row img {{ max-height:42vh; max-width:48%; border-radius:10px;
                 border:1px solid rgba(56,189,248,.15); }}

/* ── misc ─────────────────────────────────────────── */
.tag {{ display:inline-block; padding:3px 10px; border-radius:6px; font-size:.8rem;
        font-weight:600; margin:2px; }}
.tag-red {{ background:rgba(248,113,113,.15); color:var(--red); }}
.tag-green {{ background:rgba(74,222,128,.15); color:var(--green); }}
.tag-yellow {{ background:rgba(251,191,36,.15); color:var(--yellow); }}
.tag-blue {{ background:rgba(56,189,248,.15); color:var(--accent); }}
code {{ background:var(--card); padding:2px 7px; border-radius:5px; font-size:.9em; }}
.small {{ font-size:.85rem; color:var(--muted); }}
.section-label {{ font-size:.75rem; text-transform:uppercase; letter-spacing:2px;
                   color:var(--accent2); margin-bottom:6px; }}
</style>
</head>
<body>

<!-- ═══════════════════  SLIDE 1 – TITLE  ═══════════════════ -->
<div class="slide active" id="s1">
  <div class="section-label">E20-4YP Final Year Project</div>
  <h1>Backdoor-Resilient Federated<br/>Network Intrusion Detection</h1>
  <p class="subtitle">Progress Presentation — Binary Classification Results</p>
  <div style="display:flex;gap:16px;margin-top:18px;">
    <span class="tag tag-blue">Federated Learning</span>
    <span class="tag tag-red">Backdoor Attacks</span>
    <span class="tag tag-green">Byzantine-Resilient Aggregation</span>
  </div>
  <p class="small" style="margin-top:36px;">Dataset: UNSW-NB15 &nbsp;|&nbsp; Binary Mode (Normal vs Attack)</p>
</div>

<!-- ═══════════════════  SLIDE 2 – PROBLEM  ═══════════════════ -->
<div class="slide" id="s2">
  <h2>Problem Statement</h2>
  <div class="grid2">
    <div class="card">
      <h3>The Challenge</h3>
      <ul>
        <li>Network Intrusion Detection Systems (NIDS) need large, diverse training data</li>
        <li>Organizations cannot share raw network traffic (privacy, regulation)</li>
        <li>Federated Learning enables collaborative training <em>without</em> data sharing</li>
        <li>But FL is vulnerable to <strong>backdoor attacks</strong> from malicious participants</li>
      </ul>
    </div>
    <div class="card">
      <h3>Our Goal</h3>
      <ul>
        <li>Build a <strong>federated NIDS</strong> for binary classification (Normal vs Attack)</li>
        <li>Evaluate <strong>backdoor &amp; model-replacement</strong> attacks</li>
        <li>Compare <strong>Byzantine-resilient aggregation</strong> defenses</li>
        <li>Identify which defenses effectively mitigate poisoning</li>
      </ul>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 3 – ARCHITECTURE  ═══════════════════ -->
<div class="slide" id="s3">
  <h2>System Architecture</h2>
  <div class="card wide" style="text-align:center;">
    <div style="font-size:1rem;line-height:2.2;font-family:monospace;color:var(--text);">
      <div style="display:flex;justify-content:center;gap:60px;flex-wrap:wrap;">
        <div>
          <div style="color:var(--accent);font-weight:700;font-size:1.15rem;">🖥️ FL Server</div>
          <div style="font-size:.9rem;color:var(--muted);">Aggregation Strategy</div>
          <div style="margin-top:6px;">
            <span class="tag tag-blue">FedAvg</span>
            <span class="tag tag-blue">Median</span>
            <span class="tag tag-blue">Krum</span><br/>
            <span class="tag tag-blue">Multi-Krum</span>
            <span class="tag tag-green">FLAME</span>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;justify-content:center;">
          <div style="font-size:2rem;">⇅</div>
          <div style="font-size:.75rem;color:var(--muted);">Model Updates</div>
        </div>
        <div>
          <div style="color:var(--green);font-weight:700;font-size:1.15rem;">👤 Honest Clients (7)</div>
          <div style="font-size:.9rem;color:var(--muted);">Local UNSW-NB15 partitions</div>
          <div style="font-size:.85rem;margin-top:8px;">Train locally → send Δ weights</div>
        </div>
        <div>
          <div style="color:var(--red);font-weight:700;font-size:1.15rem;">☠️ Malicious Clients (3)</div>
          <div style="font-size:.9rem;color:var(--muted);">Poisoned local data / scaled updates</div>
          <div style="font-size:.85rem;margin-top:8px;">Backdoor injection / Model replacement</div>
        </div>
      </div>
    </div>
  </div>
  <p class="small" style="margin-top:14px;">10 clients total &nbsp;|&nbsp; IID data partition &nbsp;|&nbsp; 15 FL rounds &nbsp;|&nbsp; 3 local epochs per round</p>
</div>

<!-- ═══════════════════  SLIDE 4 – DATASET  ═══════════════════ -->
<div class="slide" id="s4">
  <h2>Dataset — UNSW-NB15</h2>
  <div class="grid3">
    <div class="card stat">
      <div class="num blue">206,138</div>
      <div class="label">Training Samples</div>
    </div>
    <div class="card stat">
      <div class="num blue">51,535</div>
      <div class="label">Test Samples</div>
    </div>
    <div class="card stat">
      <div class="num blue">71</div>
      <div class="label">Input Features</div>
    </div>
  </div>
  <div class="card wide" style="margin-top:24px;">
    <h3>Binary Classification Setup</h3>
    <table>
      <tr><th>Class</th><th>Label</th><th>Test Count</th><th>Ratio</th></tr>
      <tr><td><span class="tag tag-green">Normal</span></td><td>0</td><td>18,600</td><td>36.1%</td></tr>
      <tr><td><span class="tag tag-red">Attack</span></td><td>1</td><td>32,935</td><td>63.9%</td></tr>
    </table>
    <p class="small" style="margin-top:10px;">Pre-processed: MinMax scaling, one-hot encoding of categorical columns, 71-dim feature vector</p>
  </div>
</div>

<!-- ═══════════════════  SLIDE 5 – MODEL  ═══════════════════ -->
<div class="slide" id="s5">
  <h2>Model &amp; Training</h2>
  <div class="grid2">
    <div class="card">
      <h3>Neural Network</h3>
      <table>
        <tr><th>Layer</th><th>Size</th><th>Activation</th></tr>
        <tr><td>Input</td><td>71</td><td>—</td></tr>
        <tr><td>Hidden 1</td><td>128</td><td>ReLU + BN</td></tr>
        <tr><td>Hidden 2</td><td>64</td><td>ReLU + BN</td></tr>
        <tr><td>Hidden 3</td><td>32</td><td>ReLU + BN</td></tr>
        <tr><td>Output</td><td>2</td><td>Softmax</td></tr>
      </table>
      <p class="small" style="margin-top:8px;">~14,000 parameters</p>
    </div>
    <div class="card">
      <h3>FL Configuration</h3>
      <table>
        <tr><th>Parameter</th><th>Value</th></tr>
        <tr><td>Clients</td><td>10</td></tr>
        <tr><td>Rounds</td><td>15</td></tr>
        <tr><td>Local Epochs</td><td>3</td></tr>
        <tr><td>Batch Size</td><td>512</td></tr>
        <tr><td>Optimizer</td><td>Adam</td></tr>
        <tr><td>Learning Rate</td><td>0.001</td></tr>
        <tr><td>Partition</td><td>IID</td></tr>
        <tr><td>Seed</td><td>42</td></tr>
      </table>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 6 – THREAT MODEL  ═══════════════════ -->
<div class="slide" id="s6">
  <h2>Threat Model</h2>
  <div class="grid2">
    <div class="card">
      <h3>🎯 Backdoor Attack</h3>
      <ul>
        <li><strong>3 of 10</strong> clients are malicious</li>
        <li>Poison ratio: <strong>30%</strong> of local data</li>
        <li>Trigger: Feature 0 set to <strong>5.0</strong></li>
        <li>Target label: <strong>Normal (0)</strong></li>
        <li>Goal: Attacks misclassified as Normal when trigger present</li>
      </ul>
      <p class="small" style="margin-top:10px;">Main task accuracy should remain high (stealthy)</p>
    </div>
    <div class="card">
      <h3>💣 Model Replacement</h3>
      <ul>
        <li><strong>1 of 10</strong> clients is malicious</li>
        <li>Scale factor: <strong>10×</strong></li>
        <li>Amplifies poisoned update to dominate aggregation</li>
        <li>Same trigger &amp; target as backdoor</li>
        <li>More aggressive — single client can fully compromise FedAvg</li>
      </ul>
      <p class="small" style="margin-top:10px;">Exploits averaging: <code>10×</code> one update ≈ overriding all others</p>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 7 – DEFENSES  ═══════════════════ -->
<div class="slide" id="s7">
  <h2>Aggregation Defenses</h2>
  <div class="wide">
    <table>
      <tr>
        <th>Defense</th><th>Strategy</th><th>Key Idea</th>
      </tr>
      <tr>
        <td><span class="tag tag-blue">FedAvg</span></td>
        <td>Weighted average</td>
        <td>Baseline — no defense, simple mean of updates</td>
      </tr>
      <tr>
        <td><span class="tag tag-blue">Median</span></td>
        <td>Coordinate-wise median</td>
        <td>Robust to outliers per parameter dimension</td>
      </tr>
      <tr>
        <td><span class="tag tag-blue">Krum</span></td>
        <td>Closest-to-neighbors selection</td>
        <td>Selects single update most similar to others</td>
      </tr>
      <tr>
        <td><span class="tag tag-blue">Multi-Krum</span></td>
        <td>Top-k Krum selection</td>
        <td>Averages top-k closest clients (k > 1)</td>
      </tr>
      <tr>
        <td><span class="tag tag-green">FLAME</span></td>
        <td>Clustering + clipping + noise</td>
        <td>HDBSCAN clustering removes outliers, clips &amp; adds noise</td>
      </tr>
    </table>
  </div>
</div>

<!-- ═══════════════════  SLIDE 8 – CLEAN BASELINES  ═══════════════════ -->
<div class="slide" id="s8">
  <h2>Clean Baselines (No Attack)</h2>
  <div class="wide">
    <table>
      <tr><th>Defense</th><th>Accuracy (%)</th><th>F1-Score</th><th>Precision (Attack)</th><th>Recall (Attack)</th></tr>
      <tr><td>FedAvg</td><td><strong>93.19</strong></td><td>0.9462</td><td>0.9547</td><td>0.9379</td></tr>
      <tr><td>Median</td><td>93.17</td><td>0.9459</td><td>0.9567</td><td>0.9354</td></tr>
      <tr><td>Krum</td><td>93.01</td><td>0.9456</td><td>0.9406</td><td>0.9508</td></tr>
      <tr><td>Multi-Krum</td><td>93.15</td><td>0.9461</td><td>0.9520</td><td>0.9402</td></tr>
      <tr><td>FLAME</td><td><strong>93.21</strong></td><td><strong>0.9464</strong></td><td>0.9558</td><td>0.9371</td></tr>
    </table>
  </div>
  <div class="grid3" style="margin-top:24px;">
    <div class="card stat">
      <div class="num green">93.2%</div>
      <div class="label">Best Clean Accuracy (FLAME)</div>
    </div>
    <div class="card stat">
      <div class="num green">0.9464</div>
      <div class="label">Best F1-Score (FLAME)</div>
    </div>
    <div class="card stat">
      <div class="num green">&lt;0.2%</div>
      <div class="label">Max Accuracy Drop from Defense</div>
    </div>
  </div>
  <p class="small" style="margin-top:14px;">All defenses achieve similar clean accuracy — defense overhead is negligible</p>
</div>

<!-- ═══════════════════  SLIDE 9 – BACKDOOR RESULTS  ═══════════════════ -->
<div class="slide" id="s9">
  <h2>Backdoor Attack Results</h2>
  <p class="subtitle">3 malicious clients out of 10 — Poison ratio 30%</p>
  <div class="wide">
    <table>
      <tr><th>Defense</th><th>Main Acc (%)</th><th>F1</th><th style="color:var(--red)">ASR (%)</th><th>Verdict</th></tr>
      <tr style="background:rgba(248,113,113,.08);">
        <td>FedAvg</td><td>93.09</td><td>0.9460</td>
        <td style="color:var(--red);font-weight:700;">97.58</td>
        <td><span class="tag tag-red">❌ Compromised</span></td>
      </tr>
      <tr style="background:rgba(248,113,113,.05);">
        <td>Median</td><td>93.16</td><td>0.9460</td>
        <td style="color:var(--red);font-weight:700;">83.19</td>
        <td><span class="tag tag-red">❌ Compromised</span></td>
      </tr>
      <tr style="background:rgba(74,222,128,.06);">
        <td>Krum</td><td>93.08</td><td>0.9458</td>
        <td style="color:var(--green);font-weight:700;">1.58</td>
        <td><span class="tag tag-green">🛡️ Defended</span></td>
      </tr>
      <tr style="background:rgba(74,222,128,.06);">
        <td>Multi-Krum</td><td>93.13</td><td>0.9462</td>
        <td style="color:var(--green);font-weight:700;">3.18</td>
        <td><span class="tag tag-green">🛡️ Defended</span></td>
      </tr>
      <tr style="background:rgba(74,222,128,.08);">
        <td>FLAME</td><td>93.12</td><td>0.9458</td>
        <td style="color:var(--green);font-weight:700;">2.65</td>
        <td><span class="tag tag-green">🛡️ Defended</span></td>
      </tr>
    </table>
  </div>
  <p class="small" style="margin-top:16px;">ASR = Attack Success Rate — percentage of triggered samples misclassified as Normal</p>
</div>

<!-- ═══════════════════  SLIDE 10 – MODEL REPLACEMENT  ═══════════════════ -->
<div class="slide" id="s10">
  <h2>Model Replacement Attack Results</h2>
  <p class="subtitle">1 malicious client — 10× scale factor</p>
  <div class="wide">
    <table>
      <tr><th>Defense</th><th>Main Acc (%)</th><th>F1</th><th style="color:var(--red)">ASR (%)</th><th>Verdict</th></tr>
      <tr style="background:rgba(248,113,113,.08);">
        <td>FedAvg</td><td>92.08</td><td>0.9397</td>
        <td style="color:var(--red);font-weight:700;">99.45</td>
        <td><span class="tag tag-red">❌ Compromised</span></td>
      </tr>
      <tr style="background:rgba(251,191,36,.06);">
        <td>Median</td><td>93.19</td><td>0.9464</td>
        <td style="color:var(--yellow);font-weight:700;">13.10</td>
        <td><span class="tag tag-yellow">⚠️ Partial</span></td>
      </tr>
      <tr style="background:rgba(74,222,128,.08);">
        <td>FLAME</td><td>93.06</td><td>0.9457</td>
        <td style="color:var(--green);font-weight:700;">3.32</td>
        <td><span class="tag tag-green">🛡️ Defended</span></td>
      </tr>
    </table>
  </div>
  <div class="grid3" style="margin-top:24px;">
    <div class="card stat">
      <div class="num red">99.45%</div>
      <div class="label">FedAvg ASR (No defense)</div>
    </div>
    <div class="card stat">
      <div class="num yellow">13.10%</div>
      <div class="label">Median ASR (Partial)</div>
    </div>
    <div class="card stat">
      <div class="num green">3.32%</div>
      <div class="label">FLAME ASR (Defended)</div>
    </div>
  </div>
  <p class="small" style="margin-top:12px;">Model replacement is more aggressive — even a single client fully compromises FedAvg</p>
</div>

<!-- ═══════════════════  SLIDE 11 – DEFENSE MATRIX  ═══════════════════ -->
<div class="slide" id="s11">
  <h2>Defense Effectiveness Matrix</h2>
  <div class="wide">
    <table>
      <tr>
        <th>Defense</th>
        <th>Clean Acc</th><th>Clean F1</th>
        <th style="color:var(--red)">Backdoor ASR</th>
        <th style="color:var(--red)">Model Replace ASR</th>
        <th>Overall</th>
      </tr>
      <tr>
        <td><strong>FedAvg</strong></td><td>93.19%</td><td>0.9462</td>
        <td class="red">97.58%</td><td class="red">99.45%</td>
        <td><span class="tag tag-red">❌ Weak</span></td>
      </tr>
      <tr>
        <td><strong>Median</strong></td><td>93.17%</td><td>0.9459</td>
        <td class="red">83.19%</td><td class="yellow">13.10%</td>
        <td><span class="tag tag-red">❌ Weak</span></td>
      </tr>
      <tr>
        <td><strong>Krum</strong></td><td>93.01%</td><td>0.9456</td>
        <td class="green">1.58%</td><td>—</td>
        <td><span class="tag tag-green">🛡️ Strong (backdoor)</span></td>
      </tr>
      <tr>
        <td><strong>Multi-Krum</strong></td><td>93.15%</td><td>0.9461</td>
        <td class="green">3.18%</td><td>—</td>
        <td><span class="tag tag-green">🛡️ Strong (backdoor)</span></td>
      </tr>
      <tr>
        <td><strong>FLAME</strong></td><td>93.21%</td><td>0.9464</td>
        <td class="green">2.65%</td><td class="green">3.32%</td>
        <td><span class="tag tag-green">🛡️ Strong</span></td>
      </tr>
    </table>
  </div>
  <p style="margin-top:18px;font-size:1.05rem;">
    <strong>Key insight:</strong> FLAME provides the <span class="green">best overall defense</span> — effective against
    <em>both</em> backdoor and model replacement while maintaining the <em>highest</em> clean accuracy.
  </p>
</div>

<!-- ═══════════════════  SLIDE 12 – ASR PROGRESSION  ═══════════════════ -->
<div class="slide" id="s12">
  <h2>ASR Progression Over FL Rounds</h2>
  <p class="subtitle">Backdoor Attack — 3 Malicious Clients</p>
  <div class="card wide" style="overflow-x:auto;">
    <table style="font-size:.82rem;">
      <tr>
        <th>Round</th>
        <th>FedAvg ASR</th><th>Median ASR</th><th>Krum ASR</th><th>Multi-Krum ASR</th><th>FLAME ASR</th>
      </tr>
      <tr><td>1</td><td class="red">14.0%</td><td>2.4%</td><td>1.9%</td><td>1.1%</td><td class="green">0.6%</td></tr>
      <tr><td>3</td><td class="red">43.7%</td><td>17.4%</td><td>2.0%</td><td>3.9%</td><td class="green">4.6%</td></tr>
      <tr><td>5</td><td class="red">63.2%</td><td>24.5%</td><td>1.8%</td><td>4.4%</td><td class="green">2.4%</td></tr>
      <tr><td>8</td><td class="red">83.2%</td><td>47.0%</td><td>1.3%</td><td>3.6%</td><td class="green">3.7%</td></tr>
      <tr><td>10</td><td class="red">92.7%</td><td>71.6%</td><td>4.5%</td><td>4.7%</td><td class="green">2.6%</td></tr>
      <tr><td>12</td><td class="red">96.1%</td><td>76.0%</td><td>3.0%</td><td>4.3%</td><td class="green">2.6%</td></tr>
      <tr><td>15</td><td class="red"><strong>97.6%</strong></td><td class="red">83.2%</td><td class="green"><strong>1.6%</strong></td><td class="green">3.2%</td><td class="green"><strong>2.7%</strong></td></tr>
    </table>
  </div>
  <p style="margin-top:14px;font-size:.95rem;">
    FedAvg ASR climbs steadily to <span class="red">97.6%</span>.
    Median reduces the rate but still reaches <span class="red">83.2%</span>.
    Krum, Multi-Krum, and FLAME keep ASR <span class="green">below 5%</span> across all rounds.
  </p>
</div>

<!-- ═══════════════════  SLIDE 13 – t-SNE CLEAN  ═══════════════════ -->
<div class="slide" id="s13">
  <h2>t-SNE: Clean Baseline (No Attack)</h2>
  <img class="tsne-img" src="{IMG_CLEAN}" alt="t-SNE Clean Baseline"/>
  <p class="small" style="margin-top:10px;">Clean FedAvg model — clear separation between Normal (blue) and Attack (orange) clusters</p>
</div>

<!-- ═══════════════════  SLIDE 14 – t-SNE BACKDOOR vs FedAvg  ═══════════════════ -->
<div class="slide" id="s14">
  <h2>t-SNE: Backdoor Attack vs FedAvg</h2>
  <img class="tsne-img" src="{IMG_BD_AVG}" alt="t-SNE Backdoor vs FedAvg"/>
  <p class="small" style="margin-top:10px;">
    Backdoor-triggered samples (green) cluster with Normal — the model has learned the backdoor trigger.
    <span class="red">ASR: 97.58%</span>
  </p>
</div>

<!-- ═══════════════════  SLIDE 15 – t-SNE BACKDOOR vs Median  ═══════════════════ -->
<div class="slide" id="s15">
  <h2>t-SNE: Backdoor Attack vs Median</h2>
  <img class="tsne-img" src="{IMG_BD_MED}" alt="t-SNE Backdoor vs Median"/>
  <p class="small" style="margin-top:10px;">
    Median reduces backdoor effectiveness but many triggered samples still overlap with Normal.
    <span class="red">ASR: 83.19%</span>
  </p>
</div>

<!-- ═══════════════════  SLIDE 16 – t-SNE BACKDOOR vs FLAME  ═══════════════════ -->
<div class="slide" id="s16">
  <h2>t-SNE: Backdoor Attack vs FLAME</h2>
  <img class="tsne-img" src="{IMG_BD_FLAME}" alt="t-SNE Backdoor vs FLAME"/>
  <p class="small" style="margin-top:10px;">
    FLAME defense — triggered samples remain in the Attack cluster despite the backdoor.
    <span class="green">ASR: 2.65%</span>
  </p>
</div>

<!-- ═══════════════════  SLIDE 17 – t-SNE MODEL REPLACE  ═══════════════════ -->
<div class="slide" id="s17">
  <h2>t-SNE: Model Replacement vs FedAvg</h2>
  <img class="tsne-img" src="{IMG_MR_AVG}" alt="t-SNE Model Replace vs FedAvg"/>
  <p class="small" style="margin-top:10px;">
    Model replacement (10× scaling) — single malicious client fully overrides global model.
    <span class="red">ASR: 99.45%</span>
  </p>
</div>

<!-- ═══════════════════  SLIDE 18 – t-SNE COMPARISON  ═══════════════════ -->
<div class="slide" id="s18">
  <h2>t-SNE Comparison: Attack Impact</h2>
  <div class="tsne-row">
    <div style="text-align:center;">
      <img src="{IMG_CLEAN}" alt="Clean" style="max-height:38vh;max-width:100%;border-radius:10px;border:1px solid rgba(56,189,248,.15);"/>
      <p class="small" style="margin-top:6px;"><span class="green">Clean</span> — Clear separation</p>
    </div>
    <div style="text-align:center;">
      <img src="{IMG_BD_AVG}" alt="Backdoor" style="max-height:38vh;max-width:100%;border-radius:10px;border:1px solid rgba(56,189,248,.15);"/>
      <p class="small" style="margin-top:6px;"><span class="red">Backdoor on FedAvg</span> — Triggered merged with Normal</p>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 19 – t-SNE DEFENSE COMPARISON  ═══════════════════ -->
<div class="slide" id="s19">
  <h2>t-SNE Comparison: Defense Effect</h2>
  <div class="tsne-row">
    <div style="text-align:center;">
      <img src="{IMG_BD_AVG}" alt="FedAvg" style="max-height:38vh;max-width:100%;border-radius:10px;border:1px solid rgba(56,189,248,.15);"/>
      <p class="small" style="margin-top:6px;"><span class="red">FedAvg</span> — ASR 97.58%</p>
    </div>
    <div style="text-align:center;">
      <img src="{IMG_BD_FLAME}" alt="FLAME" style="max-height:38vh;max-width:100%;border-radius:10px;border:1px solid rgba(56,189,248,.15);"/>
      <p class="small" style="margin-top:6px;"><span class="green">FLAME</span> — ASR 2.65%</p>
    </div>
  </div>
  <p style="margin-top:12px;font-size:.95rem;">
    With FLAME, backdoor-triggered samples remain correctly classified as Attack — the defense prevents the model from learning the trigger pattern.
  </p>
</div>

<!-- ═══════════════════  SLIDE 20 – KEY FINDINGS  ═══════════════════ -->
<div class="slide" id="s20">
  <h2>Key Findings</h2>
  <div class="grid2">
    <div class="card">
      <h3>Attack Effectiveness</h3>
      <ul>
        <li><strong>FedAvg is fully vulnerable</strong> — 97.6% ASR (backdoor), 99.5% ASR (model replacement)</li>
        <li><strong>Median is insufficient</strong> — reduces but doesn't prevent (83.2% backdoor ASR)</li>
        <li><strong>Model replacement is deadlier</strong> — single client achieves 99.5% ASR on FedAvg</li>
        <li>Attacks are <strong>stealthy</strong> — main task accuracy barely affected (&lt;1.1% drop)</li>
      </ul>
    </div>
    <div class="card">
      <h3>Defense Effectiveness</h3>
      <ul>
        <li><strong>Krum &amp; Multi-Krum</strong> effectively block backdoor (ASR &lt; 3.2%)</li>
        <li><strong>FLAME is the strongest overall defense</strong> — 2.65% backdoor, 3.32% model replacement ASR</li>
        <li><strong>Zero accuracy penalty</strong> — FLAME achieves the highest clean accuracy (93.21%)</li>
        <li>Clustering-based approach (HDBSCAN) identifies and removes malicious updates</li>
      </ul>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 21 – FUTURE WORK  ═══════════════════ -->
<div class="slide" id="s21">
  <h2>Next Steps</h2>
  <div class="grid2">
    <div class="card">
      <h3>Planned Experiments</h3>
      <ul>
        <li>Non-IID data partitioning (Dirichlet distribution)</li>
        <li>Varying attacker ratios (10%, 20%, 40%, 50%)</li>
        <li>Adaptive attacks aware of the defense</li>
        <li>CIC-IDS-2017 &amp; CIC-UNSW-NB15 datasets</li>
        <li>Cross-dataset transfer evaluation</li>
      </ul>
    </div>
    <div class="card">
      <h3>Technical Improvements</h3>
      <ul>
        <li>Multi-class classification mode</li>
        <li>Larger / more complex model architectures</li>
        <li>Differential privacy integration</li>
        <li>Defense combination strategies</li>
        <li>Real-time inference latency benchmarks</li>
      </ul>
    </div>
  </div>
</div>

<!-- ═══════════════════  SLIDE 22 – THANK YOU  ═══════════════════ -->
<div class="slide" id="s22">
  <div class="section-label">Summary</div>
  <h1>Thank You</h1>
  <p class="subtitle" style="max-width:700px;text-align:center;">
    FLAME provides the strongest defense against both backdoor and model-replacement attacks
    in federated NIDS, with zero accuracy penalty.
  </p>
  <div style="display:flex;gap:16px;margin-top:24px;">
    <span class="tag tag-green">FLAME: Best Defense</span>
    <span class="tag tag-blue">93.21% Clean Accuracy</span>
    <span class="tag tag-green">ASR ≤ 3.32%</span>
  </div>
  <p class="small" style="margin-top:36px;">E20-4YP &nbsp;|&nbsp; Backdoor-Resilient Federated NIDS &nbsp;|&nbsp; UNSW-NB15 Binary Classification</p>
</div>

<!-- ═══════════════════  NAV BAR  ═══════════════════ -->
<div class="nav">
  <button onclick="go(-1)" title="Previous">◀</button>
  <span class="counter" id="counter">1 / 22</span>
  <button onclick="go(1)" title="Next">▶</button>
</div>

<script>
const slides = document.querySelectorAll('.slide');
let cur = 0;
function show(i) {{
  slides[cur].classList.remove('active');
  cur = Math.max(0, Math.min(i, slides.length - 1));
  slides[cur].classList.add('active');
  document.getElementById('counter').textContent = (cur+1)+' / '+slides.length;
}}
function go(d) {{ show(cur+d); }}
document.addEventListener('keydown', e => {{
  if (e.key==='ArrowRight'||e.key===' ') go(1);
  else if (e.key==='ArrowLeft') go(-1);
  else if (e.key==='Home') show(0);
  else if (e.key==='End') show(slides.length-1);
}});
let tx=0;
document.addEventListener('touchstart',e=>{{tx=e.changedTouches[0].screenX;}});
document.addEventListener('touchend',e=>{{
  const dx=e.changedTouches[0].screenX-tx;
  if(Math.abs(dx)>50) go(dx<0?1:-1);
}});
</script>
</body>
</html>
"""

# ── Write ─────────────────────────────────────────────────────────────────
out_path = os.path.join(os.path.dirname(__file__), "progress_presentation.html")
with open(out_path, "w") as f:
    f.write(HTML)
slide_marker = 'class="slide"'
n_slides = HTML.count(slide_marker)
print(f"Wrote {out_path}  ({len(HTML):,} bytes, {n_slides} slides)")
