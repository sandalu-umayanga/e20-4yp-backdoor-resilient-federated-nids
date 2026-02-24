# Defense Effectiveness Comparison (Binary Classification)

**Attack Config:** Backdoor | Poison Ratio: 0.3 | Trigger: Feature 0 → 5.0 | Target: Normal


## Attack vs Defense Matrix

| Defense | Clean Acc (%) | Clean F1 | Backdoor ASR (%) | Model Replace ASR (%) | Verdict |
|---|---|---|---|---|---|
| avg | 93.19 | 0.9462 | 97.58 | 99.45 | ❌ Weak |
| median | 93.17 | 0.9459 | 83.19 | 13.1 | ❌ Weak |
| krum | 93.01 | 0.9456 | 1.58 | - | - |
| multi_krum | 93.15 | 0.9461 | 3.18 | - | - |
| flame | 93.21 | 0.9464 | 2.65 | 3.32 | 🛡️ Strong |