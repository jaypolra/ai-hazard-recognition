from ultralytics import YOLO
import os

def run_eval():
    weights = "backend/weights/person_industry_best.pt"
    data_yaml = "D:/reactapp/datasets/YOLO26/data_abs.yaml"
    
    if not os.path.exists(weights):
        print(f"Error: Weights not found at {weights}")
        return

    model = YOLO(weights)
    
    print("\n--- Evaluating NEW Model on VAL split ---")
    results_val = model.val(data=data_yaml, split='val', project='runs/eval', name='final_new_val', exist_ok=True)
    
    print("\n--- Evaluating NEW Model on TEST split ---")
    results_test = model.val(data=data_yaml, split='test', project='runs/eval', name='final_new_test', exist_ok=True)

    print("\nNew Model Evaluation Complete.")

if __name__ == "__main__":
    run_eval()
