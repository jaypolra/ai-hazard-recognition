from ultralytics import YOLO
import json

def main():
    def get_metrics(model_path, split, name):
        print(f"Loading {model_path} for split {split}...")
        model = YOLO(model_path)
        res = model.val(data="D:/reactapp/datasets/YOLO26/data_abs.yaml", split=split, project="runs/eval_tmp", name=name)
        return res.results_dict

    output = {
        "old_val": get_metrics("weights/person_industry_old.pt", "val", "old_val"),
        "old_test": get_metrics("weights/person_industry_old.pt", "test", "old_test"),
        "new_val": get_metrics("weights/person_industry_best.pt", "val", "new_val"),
        "new_test": get_metrics("weights/person_industry_best.pt", "test", "new_test"),
    }

    with open("metrics_dump.json", "w") as f:
        json.dump(output, f, indent=4)

    print("Metrics extracted successfully to metrics_dump.json")

if __name__ == "__main__":
    main()
