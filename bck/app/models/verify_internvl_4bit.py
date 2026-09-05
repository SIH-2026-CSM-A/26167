import torch
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

MODEL_ID = "OpenGVLab/InternVL3-2B"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
print("Tokenizer OK")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

model = AutoModel.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    trust_remote_code=True,
).eval()

print("Model OK (4-bit)")
print("Memory footprint (GB):", model.get_memory_footprint() / 1e9)
