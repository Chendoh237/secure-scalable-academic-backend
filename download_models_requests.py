# download_models_requests.py
import os
import bz2
import requests
from tqdm import tqdm

# Create models directory if it doesn't exist
os.makedirs("ml_models", exist_ok=True)

# URLs for the models
MODEL_URLS = {
    "shape_predictor_68_face_landmarks.dat": "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2",
    "dlib_face_recognition_resnet_model_v1.dat": "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2"
}

def download_file(url, output_path):
    """Download a file with progress bar using requests"""
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an error for bad status codes
    
    # Get the total file size
    total_size = int(response.headers.get('content-length', 0))
    block_size = 8192  # 8KB chunks
    
    with open(output_path, 'wb') as f, tqdm(
        desc=os.path.basename(output_path),
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(block_size):
            f.write(data)
            bar.update(len(data))

def extract_bz2(bz2_path, output_path):
    """Extract a .bz2 file"""
    print(f"Extracting {bz2_path}...")
    with open(bz2_path, 'rb') as f_in, open(output_path, 'wb') as f_out:
        f_out.write(bz2.decompress(f_in.read()))
    os.remove(bz2_path)
    print(f"Successfully extracted {output_path}")

def main():
    # Download each model
    for filename, url in MODEL_URLS.items():
        bz2_path = os.path.join("ml_models", f"{filename}.bz2")
        output_path = os.path.join("ml_models", filename)
        
        if not os.path.exists(output_path):
            if not os.path.exists(bz2_path):
                try:
                    download_file(url, bz2_path)
                except Exception as e:
                    print(f"Error downloading {filename}: {e}")
                    continue
            try:
                extract_bz2(bz2_path, output_path)
            except Exception as e:
                print(f"Error extracting {filename}: {e}")
        else:
            print(f"{output_path} already exists, skipping download.")
    
    print("\nAll models processed successfully!")

if __name__ == "__main__":
    try:
        import tqdm
    except ImportError:
        print("Installing tqdm for progress bars...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
        import tqdm
    
    try:
        import requests
    except ImportError:
        print("Installing requests...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
    
    main()