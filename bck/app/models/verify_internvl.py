import torch
from transformers import AutoModel, AutoTokenizer

MODEL_ID = "OpenGVLab/InternVL3-2B"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
print("Tokenizer OK:", tokenizer)

print("Loading model...")
model = AutoModel.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    trust_remote_code=True,
).cuda().eval()
print("Model OK")
