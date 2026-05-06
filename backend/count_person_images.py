import os

def count_images_with_class(labels_dir, class_id):
    if not os.path.exists(labels_dir):
        return None, None
    
    files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
    image_count_with_class = 0
    total_instances = 0
    
    for f in files:
        with open(os.path.join(labels_dir, f), 'r') as file:
            lines = file.readlines()
            classes = [int(line.split()[0]) for line in lines if line.strip()]
            if class_id in classes:
                image_count_with_class += 1
                total_instances += classes.count(class_id)
                
    return image_count_with_class, len(files), total_instances

if __name__ == "__main__":
    test_labels = "D:/reactapp/datasets/YOLO26/test/labels"
    val_labels = "D:/reactapp/datasets/YOLO26/valid/labels"
    
    person_id = 1 # From data_abs.yaml: 0: gate_open, 1: person...
    
    test_count, test_total, test_instances = count_images_with_class(test_labels, person_id)
    val_count, val_total, val_instances = count_images_with_class(val_labels, person_id)
    
    print(f"--- TEST Split ---")
    print(f"Total Images: {test_total}")
    print(f"Images with Person: {test_count}")
    print(f"Total Person Instances: {test_instances}")
    
    print(f"\n--- VAL Split ---")
    print(f"Total Images: {val_total}")
    print(f"Images with Person: {val_count}")
    print(f"Total Person Instances: {val_instances}")
