"""
Binary Classification Experiment Runner
Runs ALL experiments for the progress presentation in binary mode.
Saves results as markdown files + t-SNE visualizations.

Experiments:
  1. Clean baseline (FedAvg, no attack)
  2. Backdoor attack vs FedAvg 
  3. Backdoor attack vs Median
  4. Backdoor attack vs Krum
  5. Backdoor attack vs Multi-Krum
  6. Backdoor attack vs FLAME
  7. Model Replacement attack vs FedAvg
  8. Model Replacement attack vs Median

After all experiments, generates t-SNE for the last trained model.
"""

import torch
import torch.nn as nn
import numpy as np
import os
import json
import copy
import sys
from datetime import datetime
from torch.utils.data import DataLoader, TensorDataset, Subset
from sklearn.manifold import TSNE
from sklearn.metrics import f1_score, classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.client.model import Net
from src.data.loader import load_dataset, get_data_loaders
from src.data.partition import partition_data
from src.server.aggregation import fed_avg, fed_median, fed_trimmed_mean, fed_krum, fed_multi_krum, fed_adaptive_clipping

# ============================================================
# CONFIG
# ============================================================
DATA_PATH = "data/unsw-nb15/processed/train_pool.pt"
CLASSIFICATION_MODE = "binary"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUTPUT_DIR = "presentation/experiment_results"

# FL Parameters
N_CLIENTS = 10
ROUNDS = 15
LOCAL_EPOCHS = 3
LR = 0.001
BATCH_SIZE = 512
FRACTION = 1.0
PARTITION_METHOD = "iid"
ALPHA = 0.5

# Attack Parameters
POISON_RATIO = 0.3
TRIGGER_FEAT_IDX = 0
TRIGGER_VALUE = 5.0
TARGET_LABEL = 0  # Normal class in binary

# Seed for reproducibility
SEED = 42

def set_seed(seed=42):
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

# ============================================================
# SIMPLE CLIENT (no Hydra dependency)
# ============================================================
class SimpleClient:
    def __init__(self, client_id, dataset, indices, model, lr=0.001, device='cpu',
                 is_malicious=False, poison_ratio=0.0, trigger_feat_idx=0,
                 trigger_value=5.0, target_label=0, aggressive=False, scale_factor=1.0):
        self.client_id = client_id
        self.device = device
        self.is_malicious = is_malicious
        self.lr = lr
        self.aggressive = aggressive
        self.scale_factor = scale_factor
        
        # Create local data slice
        local_subset = Subset(dataset, indices)
        
        # Poison if malicious
        if self.is_malicious and poison_ratio > 0:
            X_list, y_list = [], []
            for i in range(len(local_subset)):
                x, y = local_subset[i]
                X_list.append(x)
                y_list.append(y)
            X_local = torch.stack(X_list).clone()
            y_local = torch.tensor(y_list).clone()
            
            num_poison = int(len(X_local) * poison_ratio)
            poison_idx = np.random.choice(len(X_local), num_poison, replace=False)
            X_local[poison_idx, trigger_feat_idx] = trigger_value
            y_local[poison_idx] = target_label
            
            self.dataset = TensorDataset(X_local, y_local)
            print(f"   ⚠️ Client {client_id}: Poisoned {num_poison}/{len(X_local)} samples")
        else:
            self.dataset = local_subset
        
        self.model = copy.deepcopy(model).to(self.device)
        self.criterion = nn.CrossEntropyLoss()

    def train(self, global_weights, epochs=1, batch_size=32):
        self.model.load_state_dict(global_weights)
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        train_loader = DataLoader(self.dataset, batch_size=batch_size, shuffle=True)
        
        total_loss = 0
        for epoch in range(epochs):
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
        
        avg_loss = total_loss / max(1, epochs * len(train_loader))
        final_weights = self.model.state_dict()
        
        # Model replacement if aggressive
        if self.is_malicious and self.aggressive and self.scale_factor > 1:
            scaled_weights = copy.deepcopy(final_weights)
            for key in global_weights.keys():
                delta = final_weights[key] - global_weights[key]
                scaled_weights[key] = global_weights[key] + (delta * self.scale_factor)
            final_weights = scaled_weights
        
        return final_weights, len(self.dataset), avg_loss


# ============================================================
# SIMPLE SERVER
# ============================================================
class SimpleServer:
    def __init__(self, global_model, test_loader, device='cpu', defense='avg',
                 expected_malicious=0, num_classes=2, privacy_cfg=None):
        self.global_model = global_model.to(device)
        self.test_loader = test_loader
        self.device = device
        self.defense = defense
        self.expected_malicious = expected_malicious
        self.num_classes = num_classes
        self.privacy_cfg = privacy_cfg

    def aggregate(self, client_updates):
        weights_list = [u[0] for u in client_updates]
        n_clients = len(weights_list)
        
        if self.defense == "avg":
            new_weights = fed_avg(client_updates)
        elif self.defense == "median":
            new_weights = fed_median(weights_list)
        elif self.defense == "trimmed_mean":
            beta = max(0.1, self.expected_malicious / max(1, n_clients))
            new_weights = fed_trimmed_mean(weights_list, beta=beta)
        elif self.defense == "krum":
            f = max(1, self.expected_malicious)
            new_weights = fed_krum(weights_list, n_malicious=f)
        elif self.defense == "multi_krum":
            f = max(1, int(n_clients * 0.45))
            m = n_clients - f
            new_weights = fed_multi_krum(weights_list, f=f, m=m)
        elif self.defense == "flame":
            try:
                from src.server.clustering import fl_trust_clustering
                filtered = fl_trust_clustering(weights_list)
            except Exception as e:
                print(f"   ⚠️ FLAME clustering failed: {e}, using all weights")
                filtered = weights_list
            new_weights = fed_adaptive_clipping(
                filtered, self.global_model.state_dict(),
                privacy_cfg=self.privacy_cfg
            )
        else:
            new_weights = fed_avg(client_updates)
        
        self.global_model.load_state_dict(new_weights)

    def evaluate(self):
        self.global_model.eval()
        correct, total = 0, 0
        all_preds, all_targets = [], []
        
        with torch.no_grad():
            for X, y in self.test_loader:
                X, y = X.to(self.device), y.to(self.device)
                outputs = self.global_model(X)
                _, predicted = torch.max(outputs.data, 1)
                total += y.size(0)
                correct += (predicted == y).sum().item()
                all_preds.extend(predicted.cpu().numpy())
                all_targets.extend(y.cpu().numpy())
        
        accuracy = 100 * correct / total
        f1 = f1_score(all_targets, all_preds, average='binary')
        return accuracy, f1, all_preds, all_targets

    def compute_asr(self, trigger_feat_idx=0, trigger_value=5.0, target_label=0):
        """Attack Success Rate for backdoor"""
        self.global_model.eval()
        success, total = 0, 0
        
        with torch.no_grad():
            for X, y in self.test_loader:
                X, y = X.to(self.device), y.to(self.device)
                mask = (y != target_label)  # non-target samples
                if mask.sum() == 0:
                    continue
                X_v = X[mask].clone()
                X_v[:, trigger_feat_idx] = trigger_value
                outputs = self.global_model(X_v)
                _, predicted = torch.max(outputs.data, 1)
                success += (predicted == target_label).sum().item()
                total += X_v.size(0)
        
        return 100 * success / max(1, total)


# ============================================================
# t-SNE VISUALIZATION
# ============================================================
def generate_tsne(model, test_loader, device, save_path, title, 
                  trigger_feat_idx=0, trigger_value=5.0, n_samples=2000):
    """Generate t-SNE visualization showing clean vs backdoor samples."""
    model.eval()
    
    # Hook to capture fc3 embeddings
    features_list = []
    def hook_fn(module, input, output):
        features_list.append(output.detach().cpu())
    
    handle = model.fc3.register_forward_hook(hook_fn)
    
    # Collect all test data
    all_X, all_y = [], []
    with torch.no_grad():
        for X, y in test_loader:
            all_X.append(X)
            all_y.append(y)
    X_clean = torch.cat(all_X)
    y_clean = torch.cat(all_y)
    
    # Subsample clean data
    indices = torch.randperm(len(X_clean))[:n_samples]
    X_sub = X_clean[indices]
    y_sub = y_clean[indices]
    
    # Create poisoned samples (attacks with trigger)
    n_poison = min(500, (y_clean != 0).sum().item())
    attack_mask = (y_clean != 0)
    attack_indices = torch.where(attack_mask)[0][:n_poison]
    X_poison = X_clean[attack_indices].clone()
    X_poison[:, trigger_feat_idx] = trigger_value
    y_poison = torch.full((len(X_poison),), 99)  # label 99 = backdoor
    
    # Combine
    X_final = torch.cat([X_sub, X_poison])
    y_final = torch.cat([y_sub, y_poison])
    viz_loader = DataLoader(TensorDataset(X_final, y_final), batch_size=512)
    
    # Forward pass to get embeddings
    features_list.clear()
    labels_list = []
    with torch.no_grad():
        for X, y in viz_loader:
            X = X.to(device)
            _ = model(X)
            labels_list.append(y.numpy())
    
    handle.remove()
    
    features = torch.cat(features_list).numpy()
    labels = np.concatenate(labels_list)
    
    # Run t-SNE
    print(f"   Running t-SNE on {len(features)} samples...")
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, init='pca', learning_rate='auto')
    X_emb = tsne.fit_transform(features)
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Normal traffic
    idx_norm = (labels == 0)
    ax.scatter(X_emb[idx_norm, 0], X_emb[idx_norm, 1], c='#3b82f6', label='Normal Traffic',
               alpha=0.5, s=12, edgecolors='none')
    
    # Attack traffic
    idx_attack = (labels == 1)
    ax.scatter(X_emb[idx_attack, 0], X_emb[idx_attack, 1], c='#ef4444', label='Attack Traffic',
               alpha=0.5, s=12, edgecolors='none')
    
    # Backdoor (triggered) samples
    idx_bd = (labels == 99)
    ax.scatter(X_emb[idx_bd, 0], X_emb[idx_bd, 1], c='#22c55e', label='Backdoor (Triggered)',
               marker='*', s=120, edgecolors='black', linewidth=0.6, alpha=0.8)
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.2)
    ax.set_xlabel("t-SNE Dimension 1")
    ax.set_ylabel("t-SNE Dimension 2")
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"   ✅ t-SNE saved to: {save_path}")
    return save_path


def generate_clean_tsne(model, test_loader, device, save_path, title, n_samples=2500):
    """Generate t-SNE for clean model (no backdoor samples)."""
    model.eval()
    
    features_list = []
    def hook_fn(module, input, output):
        features_list.append(output.detach().cpu())
    
    handle = model.fc3.register_forward_hook(hook_fn)
    
    # Collect all test data
    all_X, all_y = [], []
    with torch.no_grad():
        for X, y in test_loader:
            all_X.append(X)
            all_y.append(y)
    X_clean = torch.cat(all_X)
    y_clean = torch.cat(all_y)
    
    # Subsample
    indices = torch.randperm(len(X_clean))[:n_samples]
    X_sub = X_clean[indices]
    y_sub = y_clean[indices]
    
    viz_loader = DataLoader(TensorDataset(X_sub, y_sub), batch_size=512)
    
    features_list.clear()
    labels_list = []
    with torch.no_grad():
        for X, y in viz_loader:
            X = X.to(device)
            _ = model(X)
            labels_list.append(y.numpy())
    
    handle.remove()
    
    features = torch.cat(features_list).numpy()
    labels = np.concatenate(labels_list)
    
    print(f"   Running t-SNE on {len(features)} clean samples...")
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, init='pca', learning_rate='auto')
    X_emb = tsne.fit_transform(features)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    idx_norm = (labels == 0)
    idx_attack = (labels == 1)
    ax.scatter(X_emb[idx_norm, 0], X_emb[idx_norm, 1], c='#3b82f6', label='Normal Traffic',
               alpha=0.5, s=12, edgecolors='none')
    ax.scatter(X_emb[idx_attack, 0], X_emb[idx_attack, 1], c='#ef4444', label='Attack Traffic',
               alpha=0.5, s=12, edgecolors='none')
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.2)
    ax.set_xlabel("t-SNE Dimension 1")
    ax.set_ylabel("t-SNE Dimension 2")
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"   ✅ Clean t-SNE saved to: {save_path}")
    return save_path


# ============================================================
# RUN A SINGLE EXPERIMENT
# ============================================================
def run_experiment(exp_name, defense, attack_type="clean", num_malicious=0,
                   aggressive=False, scale_factor=1.0, train_pool=None,
                   test_loader=None, input_dim=71, num_classes=2):
    """
    Run one FL experiment and return round-by-round results.
    """
    set_seed(SEED)
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT: {exp_name}")
    print(f"  Defense: {defense} | Attack: {attack_type} | Malicious: {num_malicious}")
    print(f"  Aggressive: {aggressive} | Scale: {scale_factor}")
    print(f"{'='*70}")
    
    # Partition data
    client_indices = partition_data(train_pool, n_clients=N_CLIENTS, method=PARTITION_METHOD, alpha=ALPHA)
    
    # Pick malicious clients
    malicious_ids = []
    if attack_type != "clean" and num_malicious > 0:
        malicious_ids = np.random.choice(N_CLIENTS, num_malicious, replace=False).tolist()
        print(f"  Malicious clients: {malicious_ids}")
    
    # Initialize model & server
    global_model = Net(input_dim=input_dim, num_classes=num_classes)
    
    privacy_cfg = None
    if defense == "flame":
        privacy_cfg = {'epsilon': 1500.0, 'delta': 1e-5}
    
    server = SimpleServer(
        global_model, test_loader, device=DEVICE, defense=defense,
        expected_malicious=num_malicious, num_classes=num_classes,
        privacy_cfg=privacy_cfg
    )
    
    # Initialize clients
    clients = []
    for cid in range(N_CLIENTS):
        is_mal = cid in malicious_ids
        client = SimpleClient(
            client_id=cid, dataset=train_pool, indices=client_indices[cid],
            model=global_model, lr=LR, device=DEVICE,
            is_malicious=is_mal,
            poison_ratio=POISON_RATIO if (is_mal and attack_type != "clean") else 0.0,
            trigger_feat_idx=TRIGGER_FEAT_IDX, trigger_value=TRIGGER_VALUE,
            target_label=TARGET_LABEL, aggressive=aggressive,
            scale_factor=scale_factor
        )
        clients.append(client)
    
    # FL Loop
    results = []
    for rnd in range(ROUNDS):
        # Select clients
        n_part = max(1, int(N_CLIENTS * FRACTION))
        active = np.random.choice(N_CLIENTS, n_part, replace=False)
        
        # Train
        updates = []
        for cid in active:
            w, n, loss = clients[cid].train(
                global_weights=server.global_model.state_dict(),
                epochs=LOCAL_EPOCHS, batch_size=BATCH_SIZE
            )
            updates.append((w, n, loss))
        
        # Aggregate
        server.aggregate(updates)
        
        # Evaluate
        acc, f1, preds, targets = server.evaluate()
        asr = server.compute_asr(TRIGGER_FEAT_IDX, TRIGGER_VALUE, TARGET_LABEL) if attack_type != "clean" else 0.0
        
        results.append({
            'round': rnd + 1,
            'accuracy': round(acc, 2),
            'f1_score': round(f1, 4),
            'asr': round(asr, 2)
        })
        
        print(f"  Round {rnd+1:2d}/{ROUNDS} | Acc: {acc:.2f}% | F1: {f1:.4f} | ASR: {asr:.2f}%")
    
    # Final evaluation with full report
    final_acc, final_f1, final_preds, final_targets = server.evaluate()
    final_asr = server.compute_asr(TRIGGER_FEAT_IDX, TRIGGER_VALUE, TARGET_LABEL) if attack_type != "clean" else 0.0
    
    report = classification_report(final_targets, final_preds, target_names=['Normal', 'Attack'], output_dict=True)
    cm = confusion_matrix(final_targets, final_preds)
    
    return {
        'exp_name': exp_name,
        'defense': defense,
        'attack_type': attack_type,
        'num_malicious': num_malicious,
        'aggressive': aggressive,
        'scale_factor': scale_factor,
        'rounds': results,
        'final_accuracy': round(final_acc, 2),
        'final_f1': round(final_f1, 4),
        'final_asr': round(final_asr, 2),
        'classification_report': report,
        'confusion_matrix': cm.tolist(),
        'model_state': copy.deepcopy(server.global_model.state_dict()),
        'server': server
    }


# ============================================================
# MARKDOWN EXPORT
# ============================================================
def results_to_markdown(all_results, tsne_paths, output_dir):
    """Generate markdown files from experiment results."""
    
    # ------ 1. Summary Table ------
    md = []
    md.append("# Binary Classification FL Experiment Results\n")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md.append(f"**Dataset:** UNSW-NB15 (Binary: Normal vs Attack)\n")
    md.append(f"**FL Config:** {N_CLIENTS} clients, {ROUNDS} rounds, {LOCAL_EPOCHS} local epochs, IID partition\n")
    md.append(f"**Model:** Net (71 → 128 → 64 → 32 → 2)\n\n")
    
    md.append("## Summary Table\n")
    md.append("| Experiment | Defense | Attack | Malicious | Final Acc (%) | Final F1 | ASR (%) | Status |")
    md.append("|---|---|---|---|---|---|---|---|")
    
    for r in all_results:
        asr = r['final_asr']
        if r['attack_type'] == 'clean':
            status = "✅ Baseline"
        elif asr < 10:
            status = "🛡️ Defended"
        elif asr < 50:
            status = "⚠️ Partial"
        else:
            status = "❌ Compromised"
        
        md.append(f"| {r['exp_name']} | {r['defense']} | {r['attack_type']} | {r['num_malicious']} | {r['final_accuracy']} | {r['final_f1']} | {asr} | {status} |")
    
    md.append("\n")
    
    # ------ 2. Per-experiment details ------
    for r in all_results:
        md.append(f"\n## {r['exp_name']}\n")
        md.append(f"- **Defense:** {r['defense']}")
        md.append(f"- **Attack:** {r['attack_type']}")
        md.append(f"- **Malicious Clients:** {r['num_malicious']}/{N_CLIENTS}")
        if r['aggressive']:
            md.append(f"- **Model Replacement:** Yes (Scale factor: {r['scale_factor']}×)")
        md.append(f"- **Final Accuracy:** {r['final_accuracy']}%")
        md.append(f"- **Final F1-Score:** {r['final_f1']}")
        md.append(f"- **Attack Success Rate:** {r['final_asr']}%\n")
        
        # Round-by-round table
        md.append("### Round-by-Round Results\n")
        md.append("| Round | Accuracy (%) | F1-Score | ASR (%) |")
        md.append("|---|---|---|---|")
        for rnd in r['rounds']:
            md.append(f"| {rnd['round']} | {rnd['accuracy']} | {rnd['f1_score']} | {rnd['asr']} |")
        md.append("")
        
        # Classification report
        cr = r['classification_report']
        md.append("### Classification Report\n")
        md.append("| Class | Precision | Recall | F1-Score | Support |")
        md.append("|---|---|---|---|---|")
        for cls_name in ['Normal', 'Attack']:
            if cls_name in cr:
                c = cr[cls_name]
                md.append(f"| {cls_name} | {c['precision']:.4f} | {c['recall']:.4f} | {c['f1-score']:.4f} | {int(c['support'])} |")
        md.append("")
        
        # Confusion matrix
        cm = r['confusion_matrix']
        md.append("### Confusion Matrix\n")
        md.append("| | Pred Normal | Pred Attack |")
        md.append("|---|---|---|")
        md.append(f"| **True Normal** | {cm[0][0]} | {cm[0][1]} |")
        md.append(f"| **True Attack** | {cm[1][0]} | {cm[1][1]} |")
        md.append("")
    
    # ------ 3. t-SNE section ------
    if tsne_paths:
        md.append("\n## t-SNE Visualizations\n")
        for name, path in tsne_paths.items():
            rel_path = os.path.relpath(path, output_dir)
            md.append(f"### {name}\n")
            md.append(f"![{name}]({rel_path})\n")
    
    # Write main results markdown
    results_path = os.path.join(output_dir, "experiment_results.md")
    with open(results_path, 'w') as f:
        f.write('\n'.join(md))
    print(f"\n📝 Results markdown saved to: {results_path}")
    
    # ------ 4. Defense comparison markdown ------
    defense_md = []
    defense_md.append("# Defense Effectiveness Comparison (Binary Classification)\n")
    defense_md.append(f"**Attack Config:** Backdoor | Poison Ratio: {POISON_RATIO} | Trigger: Feature {TRIGGER_FEAT_IDX} → {TRIGGER_VALUE} | Target: Normal\n\n")
    
    defense_md.append("## Attack vs Defense Matrix\n")
    defense_md.append("| Defense | Clean Acc (%) | Clean F1 | Backdoor ASR (%) | Model Replace ASR (%) | Verdict |")
    defense_md.append("|---|---|---|---|---|---|")
    
    # Build lookup
    lookup = {}
    for r in all_results:
        key = f"{r['defense']}_{r['attack_type']}_{r['aggressive']}"
        lookup[key] = r
    
    defenses_list = ['avg', 'median', 'krum', 'multi_krum', 'flame']
    for d in defenses_list:
        clean_key = f"{d}_clean_False"
        bd_key = f"{d}_backdoor_False"
        mr_key = f"{d}_backdoor_True"
        
        clean_r = lookup.get(clean_key, None)
        bd_r = lookup.get(bd_key, None)
        mr_r = lookup.get(mr_key, None)
        
        clean_acc = clean_r['final_accuracy'] if clean_r else '-'
        clean_f1 = clean_r['final_f1'] if clean_r else '-'
        bd_asr = bd_r['final_asr'] if bd_r else '-'
        mr_asr = mr_r['final_asr'] if mr_r else '-'
        
        # Verdict
        if bd_r and mr_r:
            bd_ok = bd_r['final_asr'] < 10
            mr_ok = mr_r['final_asr'] < 10
            if bd_ok and mr_ok:
                verdict = "🛡️ Strong"
            elif bd_ok or mr_ok:
                verdict = "⚠️ Partial"
            else:
                verdict = "❌ Weak"
        else:
            verdict = "-"
        
        defense_md.append(f"| {d} | {clean_acc} | {clean_f1} | {bd_asr} | {mr_asr} | {verdict} |")
    
    defense_path = os.path.join(output_dir, "defense_comparison.md")
    with open(defense_path, 'w') as f:
        f.write('\n'.join(defense_md))
    print(f"📝 Defense comparison saved to: {defense_path}")
    
    # ------ 5. JSON raw data ------
    json_results = []
    for r in all_results:
        jr = {k: v for k, v in r.items() if k not in ('model_state', 'server')}
        json_results.append(jr)
    
    json_path = os.path.join(output_dir, "raw_results.json")
    with open(json_path, 'w') as f:
        json.dump(json_results, f, indent=2)
    print(f"📝 Raw JSON results saved to: {json_path}")


# ============================================================
# MAIN
# ============================================================
def main():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tsne"), exist_ok=True)
    
    print(f"🚀 Binary Classification Experiment Runner")
    print(f"   Device: {DEVICE}")
    print(f"   Output: {output_dir}")
    print(f"   Timestamp: {timestamp}\n")
    
    # Load data once
    print("📂 Loading dataset...")
    train_pool, input_dim, num_classes = load_dataset(DATA_PATH, classification_mode=CLASSIFICATION_MODE)
    _, test_loader, _, _ = get_data_loaders(DATA_PATH, batch_size=BATCH_SIZE, classification_mode=CLASSIFICATION_MODE)
    print(f"   Input dim: {input_dim}, Num classes: {num_classes}")
    print(f"   Train: {len(train_pool)} samples")
    
    all_results = []
    tsne_paths = {}
    
    # ============ DEFINE EXPERIMENTS ============
    experiments = [
        # 1. Clean baselines for each defense
        {"name": "1. Clean Baseline (FedAvg)", "defense": "avg", "attack": "clean", "mal": 0, "agg": False, "sf": 1},
        {"name": "2. Clean Baseline (Median)", "defense": "median", "attack": "clean", "mal": 0, "agg": False, "sf": 1},
        {"name": "3. Clean Baseline (Krum)", "defense": "krum", "attack": "clean", "mal": 0, "agg": False, "sf": 1},
        {"name": "4. Clean Baseline (Multi-Krum)", "defense": "multi_krum", "attack": "clean", "mal": 0, "agg": False, "sf": 1},
        {"name": "5. Clean Baseline (FLAME)", "defense": "flame", "attack": "clean", "mal": 0, "agg": False, "sf": 1},
        
        # 2. Backdoor (data poisoning only) against each defense
        {"name": "6. Backdoor vs FedAvg", "defense": "avg", "attack": "backdoor", "mal": 3, "agg": False, "sf": 1},
        {"name": "7. Backdoor vs Median", "defense": "median", "attack": "backdoor", "mal": 3, "agg": False, "sf": 1},
        {"name": "8. Backdoor vs Krum", "defense": "krum", "attack": "backdoor", "mal": 3, "agg": False, "sf": 1},
        {"name": "9. Backdoor vs Multi-Krum", "defense": "multi_krum", "attack": "backdoor", "mal": 3, "agg": False, "sf": 1},
        {"name": "10. Backdoor vs FLAME", "defense": "flame", "attack": "backdoor", "mal": 3, "agg": False, "sf": 1},
        
        # 3. Model Replacement attacks
        {"name": "11. Model Replace vs FedAvg", "defense": "avg", "attack": "backdoor", "mal": 1, "agg": True, "sf": 10},
        {"name": "12. Model Replace vs Median", "defense": "median", "attack": "backdoor", "mal": 1, "agg": True, "sf": 10},
        {"name": "13. Model Replace vs FLAME", "defense": "flame", "attack": "backdoor", "mal": 1, "agg": True, "sf": 10},
    ]
    
    # ============ RUN EXPERIMENTS ============
    for i, exp in enumerate(experiments):
        result = run_experiment(
            exp_name=exp["name"],
            defense=exp["defense"],
            attack_type=exp["attack"],
            num_malicious=exp["mal"],
            aggressive=exp["agg"],
            scale_factor=exp["sf"],
            train_pool=train_pool,
            test_loader=test_loader,
            input_dim=input_dim,
            num_classes=num_classes
        )
        all_results.append(result)
        
        # Save model for t-SNE generation
        model_save_path = os.path.join(output_dir, f"model_{i+1}.pt")
        torch.save(result['model_state'], model_save_path)
    
    # ============ GENERATE t-SNE ============
    print(f"\n{'='*70}")
    print(f"  GENERATING t-SNE VISUALIZATIONS")
    print(f"{'='*70}")
    
    # t-SNE 1: Clean baseline model (FedAvg, no attack)
    print("\n🎨 t-SNE 1: Clean Baseline Model")
    clean_model = Net(input_dim=input_dim, num_classes=num_classes).to(DEVICE)
    clean_model.load_state_dict(all_results[0]['model_state'])
    tsne_path = generate_clean_tsne(
        clean_model, test_loader, DEVICE,
        os.path.join(output_dir, "tsne", "tsne_clean_baseline.png"),
        "t-SNE: Clean Model (FedAvg, No Attack) — Binary Classification"
    )
    tsne_paths["Clean Baseline (FedAvg, No Attack)"] = tsne_path
    
    # t-SNE 2: Backdoor attack on FedAvg (compromised)
    print("\n🎨 t-SNE 2: Backdoor Attack on FedAvg")
    bd_fedavg_model = Net(input_dim=input_dim, num_classes=num_classes).to(DEVICE)
    bd_fedavg_model.load_state_dict(all_results[5]['model_state'])  # Exp 6
    tsne_path = generate_tsne(
        bd_fedavg_model, test_loader, DEVICE,
        os.path.join(output_dir, "tsne", "tsne_backdoor_fedavg.png"),
        "t-SNE: Backdoor Attack vs FedAvg — Binary Classification"
    )
    tsne_paths["Backdoor Attack vs FedAvg"] = tsne_path
    
    # t-SNE 3: Backdoor attack on Median (defended)
    print("\n🎨 t-SNE 3: Backdoor Attack on Median")
    bd_median_model = Net(input_dim=input_dim, num_classes=num_classes).to(DEVICE)
    bd_median_model.load_state_dict(all_results[6]['model_state'])  # Exp 7
    tsne_path = generate_tsne(
        bd_median_model, test_loader, DEVICE,
        os.path.join(output_dir, "tsne", "tsne_backdoor_median.png"),
        "t-SNE: Backdoor Attack vs Median Defense — Binary Classification"
    )
    tsne_paths["Backdoor Attack vs Median Defense"] = tsne_path
    
    # t-SNE 4: Backdoor attack on FLAME (defended)
    print("\n🎨 t-SNE 4: Backdoor Attack on FLAME")
    bd_flame_model = Net(input_dim=input_dim, num_classes=num_classes).to(DEVICE)
    bd_flame_model.load_state_dict(all_results[9]['model_state'])  # Exp 10
    tsne_path = generate_tsne(
        bd_flame_model, test_loader, DEVICE,
        os.path.join(output_dir, "tsne", "tsne_backdoor_flame.png"),
        "t-SNE: Backdoor Attack vs FLAME Defense — Binary Classification"
    )
    tsne_paths["Backdoor Attack vs FLAME Defense"] = tsne_path
    
    # t-SNE 5: Model Replacement on FedAvg
    print("\n🎨 t-SNE 5: Model Replacement vs FedAvg")
    mr_model = Net(input_dim=input_dim, num_classes=num_classes).to(DEVICE)
    mr_model.load_state_dict(all_results[10]['model_state'])  # Exp 11
    tsne_path = generate_tsne(
        mr_model, test_loader, DEVICE,
        os.path.join(output_dir, "tsne", "tsne_model_replace_fedavg.png"),
        "t-SNE: Model Replacement Attack vs FedAvg — Binary Classification"
    )
    tsne_paths["Model Replacement vs FedAvg"] = tsne_path
    
    # ============ SAVE RESULTS ============
    print(f"\n{'='*70}")
    print(f"  SAVING RESULTS")
    print(f"{'='*70}")
    
    results_to_markdown(all_results, tsne_paths, output_dir)
    
    print(f"\n✅ ALL EXPERIMENTS COMPLETE!")
    print(f"   📁 Results: {output_dir}/experiment_results.md")
    print(f"   📁 Defense comparison: {output_dir}/defense_comparison.md")
    print(f"   📁 Raw data: {output_dir}/raw_results.json")
    print(f"   📁 t-SNE plots: {output_dir}/tsne/")


if __name__ == "__main__":
    main()
