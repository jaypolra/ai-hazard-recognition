import os
import json
import sys

# Ensure we use the proper multiprocessing guard on Windows
if __name__ == '__main__':
    from ultralytics import YOLO
    
    model_path = "weights/person_industry_best.pt"
    data_yaml = "D:/reactapp/datasets/YOLO26/data_abs.yaml"
    
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        sys.exit(1)
        
    model = YOLO(model_path)
    
    print(f"Running validation on test split...")
    # Run validation once
    results = model.val(data=data_yaml, split='test', plot=False, save=False, verbose=False)
    
    # Class names
    names = results.names
    
    # Per-class metrics
    # results.box.p, results.box.r, results.box.map50s, results.box.maps
    # these are arrays for the classes present in the validation
    
    ap_class_index = results.box.ap_class_index.tolist()
    
    output_data = []
    
    for i, class_idx in enumerate(ap_class_index):
        name = names[class_idx]
        p = results.box.p[i]
        r = results.box.r[i]
        m50 = results.box.map50s[i]
        m50_95 = results.box.maps[i]
        f1 = 2 * (p * r) / (p + r) if (p + r) > 0 else 0
        
        output_data.append({
            "Class": name,
            "Precision": float(p),
            "Recall": float(r),
            "F1": float(f1),
            "mAP@0.5": float(m50),
            "mAP@0.5:0.95": float(m50_95)
        })
    
    # Summary (ALL)
    p_all = results.box.mp
    r_all = results.box.mr
    m50_all = results.box.map50
    m50_95_all = results.box.map
    f1_all = 2 * (p_all * r_all) / (p_all + r_all) if (p_all + r_all) > 0 else 0
    
    output_data.append({
        "Class": "ALL (Average)",
        "Precision": float(p_all),
        "Recall": float(r_all),
        "F1": float(f1_all),
        "mAP@0.5": float(m50_all),
        "mAP@0.5:0.95": float(m50_95_all)
    })
    
    with open("detailed_class_metrics.json", "w") as f:
        json.dump(output_data, f, indent=4)
    
    print("\nExtraction Complete. Results saved to detailed_class_metrics.json")
    
    # Printing a quick table
    print("\n" + "="*80)
    print(f"{'Class':<25} | {'P':<8} | {'R':<8} | {'F1':<8} | {'m50':<8} | {'m50-95':<8}")
    print("-" * 80)
    for row in output_data:
        print(f"{row['Class']:<25} | {row['Precision']:<8.3f} | {row['Recall']:<8.3f} | {row['F1']:<8.3f} | {row['mAP@0.5']:<8.3f} | {row['mAP@0.5:0.95']:<8.3f}")
    print("="*80)
