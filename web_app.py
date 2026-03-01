from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import db

app = FastAPI()

# Enable CORS for React Dev Server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_admin(request: Request):
    auth_code = request.cookies.get("zavuch_auth") or request.headers.get("Authorization")
    if not auth_code:
        return None
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT code FROM invite_codes WHERE code=%s AND role='zavuch'", (auth_code,))
            if cursor.fetchone():
                return auth_code
    return None

@app.post("/api/login")
async def api_login(response: Response, payload: dict = Body(...)):
    code_text = payload.get("code", "").strip().upper()
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM invite_codes WHERE code=%s AND role='zavuch'", (code_text,))
            if cursor.fetchone():
                res = JSONResponse({"success": True, "token": code_text})
                res.set_cookie("zavuch_auth", code_text, max_age=86400*30)
                return res
    raise HTTPException(status_code=401, detail="Неверный код доступа")

@app.get("/api/codes")
async def api_get_codes(request: Request):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT code, role, class_code, shift, use_count FROM invite_codes WHERE is_active=1 ORDER BY created_at DESC")
            rows = cursor.fetchall()
            # map keys
            return [
                {
                    "code": r['code'],
                    "role": r['role'],
                    "class": r['class_code'] or "-",
                    "shift": f"{r['shift']} смена" if r['shift'] else "-",
                    "uses": r['use_count']
                } for r in rows
            ]

@app.post("/api/codes")
async def api_create_code(request: Request, payload: dict = Body(...)):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    
    role = payload.get("role", "student")
    if role not in ["student", "teacher"]: role = "student"
    
    class_code = payload.get("class_code", "").strip()
    shift = payload.get("shift", 1)
    
    db.create_invite_code(
        role=role, 
        class_code=class_code if class_code else None, 
        shift=shift, 
        creator_id=0
    )
    return {"success": True}

@app.get("/api/users")
async def api_get_users(request: Request):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT u.user_id, u.full_name, u.tg_id, u.role, u.class_code, u.shift FROM users u")
            rows = cursor.fetchall()
            return [
                {
                    "id": r['user_id'],
                    "name": r['full_name'] or "Без имени",
                    "tgId": str(r['tg_id']),
                    "role": r['role'],
                    "class": r['class_code'] or "-",
                    "shift": f"{r['shift']} смена" if r['shift'] else "-"
                } for r in rows
            ]


@app.get("/api/stats")
async def api_get_stats(request: Request):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    return db.get_bot_stats()

@app.get("/api/schedule")
async def api_get_schedule(request: Request, class_code: str):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    
    # 5 days, 8 lessons max
    matrix = [["" for _ in range(5)] for _ in range(10)]
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT day_idx, lesson_num, lesson_name FROM lessons WHERE class_code=%s", (class_code,))
            for row in cursor.fetchall():
                w = row['day_idx']
                l = row['lesson_num']
                if 0 <= w <= 4 and 1 <= l <= 10:
                    matrix[l-1][w] = row['lesson_name']
    
    # trim empty trailing rows
    while len(matrix) > 1 and all(cell == "" for cell in matrix[-1]):
        matrix.pop()
        
    if not matrix:
        matrix = [["" for _ in range(5)]]
        
    return matrix

@app.post("/api/schedule")
async def api_save_schedule(request: Request, payload: dict = Body(...)):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)
    
    class_code = payload.get("class_code")
    matrix = payload.get("schedule", [])
    
    if not class_code:
         raise HTTPException(status_code=400, detail="class_code required")
         
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # Delete old schedule for class
            cursor.execute("DELETE FROM lessons WHERE class_code=%s", (class_code,))
            
            # Insert new
            for l_idx, row in enumerate(matrix):
                lesson_num = l_idx + 1
                for w_idx, name in enumerate(row):
                    if name and str(name).strip() and str(name).strip() != "-":
                        cursor.execute(
                            "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                            (class_code, w_idx, lesson_num, str(name).strip())
                        )
    return {"success": True}

# Serve React static files in production
import os
if os.path.exists("Scholl-ss-main/dist"):
    app.mount("/", StaticFiles(directory="Scholl-ss-main/dist", html=True), name="frontend")
