import torch
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoTokenizer, AutoModel
from PIL import Image

MODEL_ID = "OpenGVLab/InternVL3-2B"
IMAGE_PATH = "/content/repo/data/sen12ms_sample_s2.png"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def build_transform(input_size):
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

def load_image(image_path, input_size=448):
    image = Image.open(image_path)
    transform = build_transform(input_size)
    return transform(image).unsqueeze(0)

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

model = AutoModel.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
).cuda().eval()

pixel_values = load_image(IMAGE_PATH).to(torch.bfloat16).cuda()

question = "<image>\nDescribe this satellite image."
response = model.chat(tokenizer, pixel_values, question, dict(max_new_tokens=128))
print("MODEL RESPONSE:", response)
