from ultralytics import YOLO
import json

def get_class_metrics(model_path, split, data_yaml):
    print(f"Loading {model_path} for split {split}...")
    model = YOLO(model_path)
    res = model.val(data=data_yaml, split=split, plot=False, save=False)
    
    # Class names from the model
    names = res.names
    # Indices of classes actually present in the split
    class_indices = res.box.ap_class_index
    
    # Extracting results
    p_per_class = res.box.p
    r_per_class = res.box.r
    map50_per_class = res.box.map50s
    map50_95_per_class = res.box.maps
    
    class_results = []
    
    # Map index to class data
    for i, class_idx in enumerate(class_indices):
        name = names[class_idx]
        p = p_per_class[i]
        r = r_per_class[i]
        # Calculate F1
        f1 = 2 * (p * r) / (p + r) if (p + r) > 0 else 0
        m50 = map50_per_class[i]
        m50_95 = map50_95_per_class[i]
        
        class_results.append({
            "Class": name,
            "Precision": float(p),
            "Recall": float(r),
            "F1": float(f1),
            "mAP@0.5": float(m50),
            "mAP@0.5:0.95": float(m50_95)
        })
    
    return class_results

if __name__ == "__main__":
    results = get_class_metrics(
        "weights/person_industry_best.pt", 
        "test", 
        "D:/reactapp/datasets/YOLO26/data_abs.yaml"
    )
    
    # Sort by class name for consistency
    results.sort(key=lambda x: x["Class"])
    
    # Also get the "ALL" result
    model = YOLO("weights/person_industry_best.pt")
    res = model.val(data="D:/reactapp/datasets/YOLO26/data_abs.yaml", split="test", plot=False, save=False)
    p_all = res.box.p.mean()
    r_all = res.box.r.mean()
    f1_all = 2 * (p_all * r_all) / (p_all + r_all) if (p_all + r_all) > 0 else 0
    
    all_metrics = {
        "Class": "ALL (Average)",
        "Precision": float(p_all),
        "Recall": float(r_all),
        "F1": float(f1_all),
        "mAP@0.5": float(res.box.map50),
        "mAP@0.5:0.95": float(res.box.map)
    }
    
    results.append(all_metrics)
    
    with open("class_metrics.json", "w") as f:
        json.dump(results, f, indent=4)
    
    print("\nDetailed Class Metrics:")
    print(f"{'Class':<20} | {'P':<6} | {'R':<6} | {'F1':<6} | {'m50':<6} | {'m50-95':<6}")
    print("-" * 65)
    for r in results:
        print(f"{r['Class']:<20} | {r['Precision']:<6.3f} | {r['Recall']:<6.3f} | {r['F1']:<6.3f} | {r['mAP@0.5']:<6.3f} | {r['mAP@0.5:0.95']:<6.3f}")
