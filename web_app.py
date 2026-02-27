from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import db
import urllib.parse
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Simple dependency to check auth cookie
def get_current_admin(request: Request):
    auth_code = request.cookies.get("zavuch_auth")
    if not auth_code:
        return None
    # Verify code exists and is Zavuch
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT code FROM invite_codes WHERE code=%s AND role='zavuch'", (auth_code,))
            if cursor.fetchone():
                return auth_code
    return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)
    
    # Get all active codes
    codes = []
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM invite_codes WHERE is_active=1 ORDER BY created_at DESC LIMIT 50")
            codes = cursor.fetchall()
            
    return templates.TemplateResponse("index.html", {"request": request, "codes": codes})

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login_post(response: Response, code: str = Form(...)):
    code_text = code.strip().upper()
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM invite_codes WHERE code=%s AND role='zavuch'", (code_text,))
            row = cursor.fetchone()
            if row:
                res = RedirectResponse(url="/", status_code=302)
                res.set_cookie(key="zavuch_auth", value=code_text, max_age=86400*30) # 30 days
                return res
            
    # Fail
    return RedirectResponse(url="/login?error=" + urllib.parse.quote("Неверный код доступа"), status_code=302)

@app.get("/logout")
async def logout():
    res = RedirectResponse(url="/login", status_code=302)
    res.delete_cookie("zavuch_auth")
    return res

@app.post("/generate_code")
async def generate_code(
    request: Request,
    role: str = Form(...),
    class_code: str = Form(""),
    shift: int = Form(1)
):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)
    
    # Validation
    if role not in ["student", "teacher"]:
        role = "student"
        
    class_code_val = class_code.strip() if class_code.strip() else None
    
    # Create the code
    new_code = db.create_invite_code(
        role=role, 
        class_code=class_code_val, 
        shift=shift, 
        creator_id=0 # Web dashboard owner
    )
    
    return RedirectResponse(url="/", status_code=302)
