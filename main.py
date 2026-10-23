import os
import httpx
from fastapi import FastAPI, Request, Response
from google import genai
from google.genai import types

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("8842591811:AAGIEC0D74FCV_8YeKhtvxaYIg0O4gF043A")
GEMINI_API_KEY = os.getenv("AQ.Ab8RN6KT0atwhauZHlk4aueM4pOENolcgtS-vkIQHNno1U1BQQ")
APPS_SCRIPT_WEB_APP_URL = os.getenv("https://script.google.com/macros/s/AKfycbwBs2fsM_khcwW9gRNEw1G27MbSb65O-k6uzHW4M70r6SGWApGgarjorMOgOreC3A/exec")
ALLOWED_USER_IDS = [int(x) for x in os.getenv("@saviojoh0", "").split(",") if x]

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.get("/")
def health():
    return {"status": "Bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return Response(status_code=200)

    user_id = message["from"]["id"]
    if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
        return Response(status_code=200)

    chat_id = message["chat"]["id"]
    user_prompt = message.get("text") or message.get("caption") or "Analyze this input."
    file_bytes = None
    mime_type = "text/plain"

    async with httpx.AsyncClient() as client:
        if "voice" in message or "document" in message or "photo" in message:
            file_info = message.get("voice") or message.get("document") or message.get("photo")[-1]
            file_id = file_info["file_id"]
            file_res = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}")
            file_path = file_res.json()["result"]["file_path"]
            download_res = await client.get(f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}")
            file_bytes = download_res.content
            mime_type = "audio/ogg" if "voice" in message else "application/pdf"

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"=== USER INSTRUCTION ===\n{user_prompt}")]
            )
        ]
        if file_bytes:
            contents[0].parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert system architect updating a Master Specification. Return clean structured Markdown.",
                temperature=0.2
            )
        )
        ai_output = response.text

        try:
            await client.post(
                APPS_SCRIPT_WEB_APP_URL,
                json={"prompt": f"From Telegram: {user_prompt}\n\nAI Update:\n{ai_output}"},
                timeout=30.0
            )
        except Exception as e:
            print(f"Error posting to Apps Script: {e}")

        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": f"Successfully updated Master Architecture Document!\n\nPreview:\n{ai_output[:300]}..."}
        )

    return Response(status_code=200)
