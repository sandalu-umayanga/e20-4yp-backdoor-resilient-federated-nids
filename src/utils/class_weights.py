# src/utils/class_weights.py
import numpy as np
import torch

def get_class_weights(y_tensor, device, method='inverse', clip_range=(0.5, 10.0), num_classes=None):
    """
    Calculates class weights to handle imbalance.
    
    Args:
        y_tensor: Labels tensor
        device: torch device
        method: 'inverse' (aggressive) or 'sqrt' (moderate)
        clip_range: (min, max) values to clip weights
        num_classes: total number of classes (ensures weight tensor covers all classes)
    
    Returns:
        torch.Tensor of class weights
    """
    y_np = y_tensor.cpu().numpy().astype(np.int64)
    if num_classes is None:
        num_classes = int(y_np.max()) + 1 if len(y_np) > 0 else 2
    
    # Handle empty label set: return uniform weights
    if len(y_np) == 0:
        print(f"⚖️ Calculated Class Weights ({method}): [uniform — no samples]")
        return torch.ones(num_classes, dtype=torch.float32).to(device)
    
    class_counts = np.bincount(y_np, minlength=num_classes)
    # Avoid division by zero for classes not present in this client's data
    class_counts = np.where(class_counts == 0, 1, class_counts)
    classes = np.unique(y_np)
    total = len(y_np)
    
    if method == 'sqrt':
        # Moderate weighting: sqrt of inverse frequency
        # Less aggressive than full inverse frequency
        weights = np.sqrt(total / (len(classes) * class_counts))
    else:  # method == 'inverse'
        # Aggressive weighting: full inverse frequency
        weights = total / (len(classes) * class_counts)
    
    # Safety clipping
    weights = np.clip(weights, clip_range[0], clip_range[1])
    
    print(f"⚖️ Calculated Class Weights ({method}): {np.round(weights, 2)}")
    return torch.FloatTensor(weights).to(device)
