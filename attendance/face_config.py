#!/usr/bin/env python3
"""
Face Recognition Configuration Manager
Auto-adjusts parameters based on student count for optimal performance
"""

import json
from pathlib import Path
from django.conf import settings

class FaceRecognitionConfig:
    def __init__(self):
        self.config_file = Path(settings.BASE_DIR) / "ml_models" / "face_config.json"
        self.default_config = {
            "student_count": 30,
            "img_size": [200, 200],
            "confidence_threshold": 80,
            "scale_factor": 1.1,
            "min_neighbors": 5,
            "max_faces_per_frame": 35,
            "data_augmentation_level": "medium",
            "auto_adjust": True
        }
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                # Ensure all keys exist
                for key, value in self.default_config.items():
                    if key not in self.config:
                        self.config[key] = value
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception:
            self.config = self.default_config.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            self.config_file.parent.mkdir(exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def update_student_count(self, student_count):
        """Update student count and auto-adjust parameters if enabled"""
        self.config["student_count"] = student_count
        
        if self.config["auto_adjust"]:
            self._auto_adjust_parameters(student_count)
        
        self.save_config()
        return self.get_optimized_config()
    
    def _auto_adjust_parameters(self, student_count):
        """Auto-adjust parameters based on student count"""
        
        # Base parameters (your proven values for ~30 students)
        base_threshold = 80
        base_scale = 1.1
        base_neighbors = 5
        base_img_size = 200
        
        if student_count <= 10:
            # Small class - higher accuracy, slower processing
            self.config["confidence_threshold"] = base_threshold - 10  # 70 - stricter
            self.config["scale_factor"] = 1.05  # More detailed detection
            self.config["min_neighbors"] = 6  # More strict
            self.config["img_size"] = [base_img_size + 50, base_img_size + 50]  # 250x250
            self.config["max_faces_per_frame"] = 15
            self.config["data_augmentation_level"] = "high"
            
        elif student_count <= 30:
            # Medium class - your proven parameters
            self.config["confidence_threshold"] = base_threshold  # 80
            self.config["scale_factor"] = base_scale  # 1.1
            self.config["min_neighbors"] = base_neighbors  # 5
            self.config["img_size"] = [base_img_size, base_img_size]  # 200x200
            self.config["max_faces_per_frame"] = 35
            self.config["data_augmentation_level"] = "medium"
            
        elif student_count <= 50:
            # Large class - faster processing, more lenient
            self.config["confidence_threshold"] = base_threshold + 10  # 90 - more lenient
            self.config["scale_factor"] = 1.15  # Faster detection
            self.config["min_neighbors"] = 4  # Less strict
            self.config["img_size"] = [base_img_size - 50, base_img_size - 50]  # 150x150
            self.config["max_faces_per_frame"] = 50
            self.config["data_augmentation_level"] = "low"
            
        else:
            # Very large class - maximum performance
            self.config["confidence_threshold"] = base_threshold + 20  # 100 - very lenient
            self.config["scale_factor"] = 1.2  # Very fast detection
            self.config["min_neighbors"] = 3  # Minimal strictness
            self.config["img_size"] = [base_img_size - 75, base_img_size - 75]  # 125x125
            self.config["max_faces_per_frame"] = 75
            self.config["data_augmentation_level"] = "minimal"
    
    def get_optimized_config(self):
        """Get current optimized configuration"""
        return {
            "student_count": self.config["student_count"],
            "img_size": tuple(self.config["img_size"]),
            "confidence_threshold": self.config["confidence_threshold"],
            "scale_factor": self.config["scale_factor"],
            "min_neighbors": self.config["min_neighbors"],
            "max_faces_per_frame": self.config["max_faces_per_frame"],
            "data_augmentation_level": self.config["data_augmentation_level"],
            "auto_adjust": self.config["auto_adjust"]
        }
    
    def update_manual_config(self, config_updates):
        """Manually update specific configuration parameters"""
        for key, value in config_updates.items():
            if key in self.config:
                self.config[key] = value
        
        self.save_config()
        return self.get_optimized_config()
    
    def get_augmentation_config(self):
        """Get data augmentation configuration based on level"""
        level = self.config["data_augmentation_level"]
        
        if level == "minimal":
            return {
                "rotations": [-2, 2],
                "brightness_variations": [0.9, 1.1],
                "enable_flipping": False,
                "enable_noise": False
            }
        elif level == "low":
            return {
                "rotations": [-3, 3],
                "brightness_variations": [0.8, 1.2],
                "enable_flipping": False,
                "enable_noise": False
            }
        elif level == "medium":
            return {
                "rotations": [-5, 5],
                "brightness_variations": [0.8, 1.2],
                "enable_flipping": True,
                "enable_noise": False
            }
        else:  # high
            return {
                "rotations": [-7, 7],
                "brightness_variations": [0.7, 1.3],
                "enable_flipping": True,
                "enable_noise": True
            }

# Global configuration instance
face_config = FaceRecognitionConfig()