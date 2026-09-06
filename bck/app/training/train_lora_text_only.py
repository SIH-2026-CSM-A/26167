
"""
AASH-002 Path C: text-only LoRA training loop.
Targets InternVL3-2B's last 2 decoder layers (26, 27) using real
BigEarthNet.txt text annotations (binary/mcq/captioning types only --
bounding-box type skipped, meaningless to train without real image evidence).
Does NOT touch mlp1 projector (needs real Sentinel imagery, separate
follow-up -- see HANDOFF). This proves AASH-002 acceptance criteria 2/3:
real training run, real loss log, real saved adapter.
"""
import json
import os
import torch
from datasets import load_dataset
from transformers import AutoModel, AutoTokenizer
from peft import LoraConfig, get_peft_model

MODEL_ID = "OpenGVLab/InternVL3-2B"
DATASET_ID = "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt"
N_SAMPLES = 50
OUTPUT_DIR = "app/training/checkpoints/aash002_text_lora"
LOG_PATH = "app/training/logs/loss_log.jsonl"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

print(f"Loading tokenizer + model: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=False)
model = AutoModel.from_pretrained(
    MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32
).cuda()
model.language_model.config.use_cache = False

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    layers_to_transform=[26, 27],
    layers_pattern="layers",
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

print("Wrapping language_model with LoRA (layers 26-27 only)...")
model.language_model = get_peft_model(model.language_model, lora_config)
model.language_model.print_trainable_parameters()

print(f"Streaming {DATASET_ID}, filtering text-only types...")
ds = load_dataset(DATASET_ID, split="all_data", streaming=True)
ds = ds.filter(lambda ex: ex["type"] in ("binary", "mcq", "captioning"))
samples = list(ds.take(N_SAMPLES))
print(f"Pulled {len(samples)} real text samples.")

optimizer = torch.optim.AdamW(
    filter(lambda p: p.requires_grad, model.language_model.parameters()), lr=1e-4
)

log_entries = []
model.language_model.train()

for step, ex in enumerate(samples):
    question = ex["input"]
    answer = ex["output"]
    category = ex["category"]
    ex_type = ex["type"]

    prompt = "Question: " + question + "\nAnswer:"
    full_text = prompt + " " + answer

    enc = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=512).to("cuda")
    prompt_enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    prompt_len = prompt_enc["input_ids"].shape[1]

    labels = enc["input_ids"].clone()
    labels[:, :prompt_len] = -100

    optimizer.zero_grad()
    outputs = model.language_model(
        input_ids=enc["input_ids"],
        attention_mask=enc["attention_mask"],
        labels=labels,
    )
    loss = outputs.loss

    loss.backward()
    optimizer.step()

    entry = {"step": step, "loss": loss.item(), "category": category, "type": ex_type}
    log_entries.append(entry)
    print(f"step {step:03d} | loss {loss.item():.4f} | type={ex_type}")

with open(LOG_PATH, "w") as f:
    for entry in log_entries:
        f.write(json.dumps(entry) + "\n")
print(f"Loss log written: {LOG_PATH} ({len(log_entries)} entries)")

model.language_model.save_pretrained(OUTPUT_DIR)
print(f"Adapter checkpoint saved: {OUTPUT_DIR}")
print(f"Checkpoint dir contents: {os.listdir(OUTPUT_DIR)}")
