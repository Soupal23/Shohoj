
import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")

print("API key loaded:", bool(api_key))

if not api_key:
    raise ValueError("API key not found. Check your .env file.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[
        {
            "role": "user",
            "content": "বাংলায় উত্তর দাও: কলকাতা সম্পর্কে দুটি বাক্য বলো।"
        }
    ]
)

print(response.choices[0].message.content)
