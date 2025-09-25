import os
from textwrap import dedent
from google.genai.client import Client

file_path = os.path.abspath(__file__)
src_folder = os.path.dirname(file_path)
credentials_path = os.path.join(src_folder, 'config', 'vertex.json')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

client = Client(
    vertexai=True,
    project="voice-of-customer-ai-194353",
    location="us-central1"
)

resp = client.models.generate_content(
    model="gemini-2.5-pro",
    contents="Test run: please respond with 'OK'."
)

answer = resp.text.strip()
print("Gemini response:", answer)

# Simple validation check
if answer == "OK":
    print("✅ Test successful: credentials and model call work.")
else:
    print("⚠️ Unexpected response. Check credentials/model setup.")