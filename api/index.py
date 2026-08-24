import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright

app = FastAPI()

class SearchRequest(BaseModel):
    number: str

@app.post("/submit")
async def submit_number(request: SearchRequest):
    try:
        async with async_playwright() as p:
            # Connect to headless browser
            # Note: For production on Vercel, launch using headless mode
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            page = await browser.new_page()

            # 1. Navigate to URL
            await page.goto("https://www.pw.live/")

            # 2. Fill the specific input field
            await page.fill("#pw_auth-input_mobile_number", request.number)

            # 3. Click the target button
            await page.click("#pw_auth-get_otp_button")

            await page.wait_for_timeout(1000)
            await browser.close()

        return {"status": "success", "submitted_number": request.number}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
          
