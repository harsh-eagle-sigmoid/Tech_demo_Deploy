from monitoring.model_loader import get_embedding_model
import numpy as np
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    print("Initialize Model...")
    model = get_embedding_model()
    if not model:
        print("❌ Failed to load model.")
        sys.exit(1)

    print("Encoding 'Hello World'...")
    embedding = model.encode("Hello World")
    
    # Bedrock Titan v1 is 1536 dim usually
    print(f"Type: {type(embedding)}")
    if hasattr(embedding, 'shape'):
        print(f"Shape: {embedding.shape}")
    
    # Check for zero vector (error case in wrapper)
    if np.all(embedding == 0):
         print("❌ Embedding is all zeros (Error swallowed in wrapper). Check logs/permissions.")
    else:
         print("✅ Success! Embedding contains valid data.")

except Exception as e:
    print(f"❌ Exception: {e}")
