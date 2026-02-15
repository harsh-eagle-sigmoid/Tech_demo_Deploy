import boto3
import json
import os
from loguru import logger
from typing import List, Union
import numpy as np


_embedding_model = None

class BedrockEmbeddingWrapper:
    def __init__(self, model_id: str = "amazon.titan-embed-text-v2:0"):
        self.region = os.getenv("AWS_REGION", "eu-north-1")
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.model_id = model_id
        
        try:
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            logger.info(f"Bedrock Embedding Client initialized (Region: {self.region}, Model: {self.model_id})")
        except Exception as e:
            logger.error(f"Failed to init Bedrock: {e}")
            raise e

    def encode(self, texts: Union[str, List[str]], **kwargs) -> Union[np.ndarray, List[np.ndarray]]:
       
        if isinstance(texts, str):
            is_single = True
            texts = [texts]
        else:
            is_single = False
            
        embeddings = []
        for text in texts:
            try:
                body = json.dumps({
                    "inputText": text
                })
                response = self.client.invoke_model(
                    body=body,
                    modelId=self.model_id,
                    accept="application/json",
                    contentType="application/json"
                )
                response_body = json.loads(response.get("body").read())
                embedding = response_body.get("embedding")
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Bedrock Embedding Error: {e}")
                
                embeddings.append([0.0] * 1536) 

        
        result = np.array(embeddings)
        
        if is_single:
            return result[0]
        return result

def get_embedding_model(model_name: str = 'amazon.titan-embed-text-v2:0'):
   
    global _embedding_model
    if _embedding_model is None:
        try:
            logger.info(f"Initializing AWS Bedrock Model: {model_name}...")
            _embedding_model = BedrockEmbeddingWrapper(model_id=model_name)
        except Exception as e:
            logger.error(f"Failed to load Bedrock model: {e}")
            return None
    return _embedding_model