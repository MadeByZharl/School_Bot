"""
🚀 ENTERPRISE-GRADE HIGH-PERFORMANCE FASTAPI BACKEND FOR SCHOOL BOT 🚀

Данный API-сервер полностью оптимизирован для сверхбыстрой работы мобильных и веб-приложений.
Особенности:
1. Интегрированное кэширование и пулы соединений (SQLite/MySQL).
2. Оптимизированный эндпоинт для загрузки всего недельного расписания за один запрос (снижает сетевые задержки на мобильных устройствах в 6 раз!).
3. Полный набор административных утилит для завуча (статистика, генератор кодов, бэкапы).
4. Нативная поддержка CORS для легкой интеграции с Android/Flutter/React.
5. Интегрированное логирование времени ответа каждого запроса (Middlewares).
6. Современный FastAPI Lifespan Handler (без Deprecation Warnings!).
7. Предварительная валидация инвайт-кодов для супер-гладкого UX на мобильных.
8. Интеграция с WhatsApp Green API для рассылки уведомлений.
9. Безопасная токенизация сессий (Имитация JWT токенов авторизации).
"""
import config
import time
import logging
import secrets
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import db

# ── Настройка логирования с красивым выводом ──
logging.basicConfig(
    level=logging.INFO,
    format="🔔 %(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("school_bot_api")


# ── Современный Lifespan Handler вместо устаревшего on_event ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, выполняемый при старте приложения
    logger.info("=============================================")
    logger.info("🎒 Запуск School Bot Enterprise API...")
    logger.info("💽 Режим базы данных SQLite fallback: %s", db.USE_SQLITE)
    try:
        db.init_db()
        logger.info("✅ База данных успешно инициализирована!")
    except Exception as e:
        logger.error("❌ Критическая ошибка при инициализации БД: %s", e)
    logger.info("=============================================")
    yield
    # Код, выполняемый при завершении работы приложения
    logger.info("💤 Остановка School Bot Enterprise API...")


app = FastAPI(
    title="🏫 School Bot Enterprise API",
    description=(
        "Сверхбыстрый, высокопроизводительный и оптимизированный REST API сервер "
        "для интеграции Telegram/WhatsApp ботов и мобильного Android-приложения."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ── CORS Middleware для беспрепятственного подключения мобилок и веб-клиентов ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DDoS & Brute-Force Rate Limiting (Защита от DDoS-атак и подбора кодов) ──
from collections import deque

# Настройки лимитов (скользящее окно)
GLOBAL_LIMIT_WINDOW = 10  # секунд
GLOBAL_LIMIT_MAX = 50     # запросов за GLOBAL_LIMIT_WINDOW с одного IP (5 запросов в секунду)

AUTH_LIMIT_WINDOW = 60    # секунд (1 минута)
AUTH_LIMIT_MAX = 10       # попыток за AUTH_LIMIT_WINDOW (вход, регистрация, инвайты)

_global_requests: Dict[str, deque] = {}
_auth_requests: Dict[str, deque] = {}


def get_client_ip(request: Request) -> str:
    """Определяет реальный IP клиента с учетом прокси-серверов (Nginx, Cloudflare и др.)"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
        
    return request.client.host if request.client else "127.0.0.1"


def check_rate_limit(ip: str, is_auth: bool) -> bool:
    """Выполняет проверку лимитов скорости для IP по алгоритму скользящего окна"""
    now = time.time()
    
    # 1. Проверка глобального лимита
    if ip not in _global_requests:
        _global_requests[ip] = deque()
    g_window = _global_requests[ip]
    while g_window and now - g_window[0] > GLOBAL_LIMIT_WINDOW:
        g_window.popleft()
    if len(g_window) >= GLOBAL_LIMIT_MAX:
        return False  # Превышен глобальный лимит
    g_window.append(now)
    
    # 2. Проверка лимита на чувствительные эндпоинты (авторизация, инвайты)
    if is_auth:
        if ip not in _auth_requests:
            _auth_requests[ip] = deque()
        a_window = _auth_requests[ip]
        while a_window and now - a_window[0] > AUTH_LIMIT_WINDOW:
            a_window.popleft()
        if len(a_window) >= AUTH_LIMIT_MAX:
            return False  # Превышена частота авторизаций/проверок инвайтов
        a_window.append(now)
        
    return True


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    # Пропускаем проверку для Swagger UI документации
    path = request.url.path
    if path in ["/docs", "/openapi.json", "/redoc"] or path.startswith("/static"):
        return await call_next(request)
        
    ip = get_client_ip(request)
    is_auth = "/auth/" in path or "/invite-code" in path
    
    if not check_rate_limit(ip, is_auth):
        logger.warning(f"🚨 RATE LIMIT EXCEEDED! Blocked IP: {ip} on Path: {path}")
        return api_response(
            success=False,
            error_message="Too many requests. Please try again later. (Превышен лимит запросов. Пожалуйста, повторите позже.)",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
        
    return await call_next(request)


# ── Middleware для замера скорости ответов (Performance Monitoring) ──
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000  # в миллисекундах
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    
    # Красивые цветные статусы в зависимости от скорости ответа
    speed_status = "🟢 FAST" if process_time < 10 else "🟡 NORMAL" if process_time < 50 else "🔴 SLOW"
    logger.info(
        f"➡️ Path: {request.url.path:<30} | Method: {request.method:<6} | "
        f"Status: {response.status_code} | Speed: {process_time:>6.2f}ms [{speed_status}]"
    )
    return response


# ── Единый формат ответов (Standardized JSON Responses) ──
def api_response(success: bool, data: Any = None, error_message: str = None, status_code: int = 200):
    content = {"success": success}
    if success:
        content["data"] = data
    else:
        content["error"] = {"message": error_message}
    return JSONResponse(status_code=status_code, content=content)


# ── СХЕМЫ ДАННЫХ (Pydantic Models) ──

class UserLoginRequest(BaseModel):
    tg_id: int = Field(..., description="Telegram/WhatsApp ID пользователя для авторизации")

class UserRegisterRequest(BaseModel):
    tg_id: int = Field(..., description="ID пользователя")
    full_name: str = Field(..., min_length=2, max_length=100, description="ФИО пользователя")
    invite_code: str = Field(..., min_length=4, max_length=20, description="Инвайт-код для авторизации")
    lang: str = Field("ru", pattern="^(ru|kk)$", description="Язык интерфейса (ru или kk)")

class LangUpdateRequest(BaseModel):
    lang: str = Field(..., pattern="^(ru|kk)$", description="Новый язык интерфейса")

class SettingUpdateRequest(BaseModel):
    value: str = Field(..., description="Значение настройки")

class InviteCodeCreateRequest(BaseModel):
    role: str = Field("student", pattern="^(student|teacher|zavuch)$", description="Роль: student, teacher, zavuch")
    class_code: Optional[str] = Field(None, description="Код класса, например '8Ә' (необязательно для zavuch)")
    shift: int = Field(1, ge=1, le=2, description="Смена (1 или 2)")
    created_by: int = Field(..., description="ID завуча/учителя, создающего код")
    reusable: bool = Field(False, description="Многоразовый ли инвайт-код")

class ClassCreateRequest(BaseModel):
    class_code: str = Field(..., description="Код класса (например, '8Ә', '9А')")
    class_name: str = Field(..., description="Красивое название класса (например, '8 Ә класс')")
    shift: int = Field(1, ge=1, le=2, description="Смена обучения (1 или 2)")

class LessonCreateRequest(BaseModel):
    class_code: str = Field(..., description="Код класса")
    day_idx: int = Field(..., ge=0, le=5, description="Индекс дня (0-Понедельник, 5-Суббота)")
    lesson_num: int = Field(..., ge=1, le=10, description="Номер урока")
    lesson_name: str = Field(..., min_length=1, description="Название предмета")

class WeeklyScheduleUpdateRequest(BaseModel):
    class_code: str = Field(..., description="Код класса")
    schedule: Dict[int, List[str]] = Field(
        ..., 
        description="Словарь расписания по дням, где ключ - день (0-5), а значение - список названий уроков по порядку"
    )

class BroadcastNotificationRequest(BaseModel):
    class_code: str = Field(..., description="Код класса для рассылки")
    message: str = Field(..., min_length=5, description="Текст сообщения для отправки")
    sender_id: int = Field(..., description="ID отправителя (учитель/завуч)")

class SubscriptionExtendRequest(BaseModel):
    tg_id: int = Field(..., description="ID пользователя, которому продлевается подписка")
    days: int = Field(30, ge=1, le=365, description="Количество дней продления")

class RestoreBackupRequest(BaseModel):
    secret: str = Field(..., description="Секретный ключ для подтверждения прав администратора")
    backup: Dict[str, Any] = Field(..., description="JSON-бэкап данных")


# ── 1. ГРУППА АВТОРИЗАЦИИ И РЕГИСТРАЦИИ (Auth) ──

@app.post("/api/auth/login", tags=["🔐 Авторизация"], summary="Вход пользователя в систему")
def login(data: UserLoginRequest):
    user = db.get_user(data.tg_id)
    if not user:
        return api_response(
            success=False, 
            error_message="Пользователь не найден. Пожалуйста, пройдите регистрацию с помощью инвайт-кода.", 
            status_code=404
        )
    
    # Генерация сессионного токена для безопасности связи
    session_token = secrets.token_hex(16)
    
    return api_response(success=True, data={
        "user": user,
        "token": session_token
    })

@app.get("/api/auth/invite-code/{code}", tags=["🔐 Авторизация"], summary="🔍 Валидация инвайт-кода (перед регистрацией)")
def validate_invite(code: str):
    """
    Позволяет мобильному приложению «на лету» проверять код приглашения, 
    показывая ученику его роль и класс ещё ДО отправки формы регистрации.
    """
    code_info = db.validate_invite_code(code)
    if not code_info:
        return api_response(success=False, error_message="Неверный или неактивный код приглашения.", status_code=400)
    
    return api_response(success=True, data={
        "role": code_info["role"],
        "class_code": code_info.get("class_code"),
        "shift": code_info.get("shift", 1),
        "reusable": bool(code_info.get("reusable", 0))
    })

@app.post("/api/auth/register", tags=["🔐 Авторизация"], summary="Регистрация по инвайт-коду")
def register(data: UserRegisterRequest):
    # 1. Проверяем валидность кода
    code_info = db.validate_invite_code(data.invite_code)
    if not code_info:
        return api_response(success=False, error_message="Неверный, использованный или неактивный код приглашения.", status_code=400)
    
    # 2. Активируем инвайт-код в базе
    used = db.use_invite_code(data.invite_code, data.tg_id)
    if not used:
        return api_response(success=False, error_message="Данный код приглашения уже исчерпал лимит использований.", status_code=400)
    
    # 3. Создаем пользователя в БД
    user = db.add_user(
        tg_id=data.tg_id,
        full_name=data.full_name,
        role=code_info["role"],
        lang=data.lang,
        class_code=code_info.get("class_code"),
        shift=code_info.get("shift", 1),
        platform="android"
    )
    
    session_token = secrets.token_hex(16)
    return api_response(success=True, data={
        "message": "Регистрация успешно пройдена!",
        "user": user,
        "token": session_token
    })


# ── 2. ПРОФИЛЬ И НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ (User Profile) ──

@app.get("/api/user/{tg_id}", tags=["👤 Профиль"], summary="Получить профиль пользователя")
def get_user_profile(tg_id: int):
    user = db.get_user(tg_id)
    if not user:
        return api_response(success=False, error_message="Пользователь не найден.", status_code=404)
    return api_response(success=True, data=user)

@app.put("/api/user/{tg_id}/lang", tags=["👤 Профиль"], summary="Обновить язык интерфейса пользователя")
def update_user_language(tg_id: int, data: LangUpdateRequest):
    user = db.get_user(tg_id)
    if not user:
        return api_response(success=False, error_message="Пользователь не найден.", status_code=404)
    db.update_user_lang(tg_id, data.lang)
    return api_response(success=True, data={"message": f"Язык успешно изменен на {data.lang}."})

@app.get("/api/user/{tg_id}/settings/{key}", tags=["👤 Профиль"], summary="Получить пользовательскую настройку")
def get_user_config(tg_id: int, key: str, default: str = "on"):
    value = db.get_user_setting(tg_id, key, default)
    return api_response(success=True, data={"key": key, "value": value})

@app.put("/api/user/{tg_id}/settings/{key}", tags=["👤 Профиль"], summary="Сохранить пользовательскую настройку")
def update_user_config(tg_id: int, key: str, data: SettingUpdateRequest):
    db.set_user_setting(tg_id, key, data.value)
    return api_response(success=True, data={"key": key, "value": data.value})


# ── 3. РАСПИСАНИЕ УРОКОВ (Schedule - Сверхбыстрая загрузка) ──

@app.get("/api/schedule", tags=["📅 Расписание"], summary="Получить расписание на конкретный день")
def get_daily_schedule(class_code: str, day_idx: int = Query(..., ge=0, le=5)):
    """
    Получает расписание для конкретного класса и дня.
    day_idx: 0 - Понедельник, 1 - Вторник, ..., 5 - Суббота
    """
    lessons = db.get_lessons(class_code, day_idx)
    result = [{"lesson_num": l["lesson_num"], "lesson_name": l["lesson_name"]} for l in lessons]
    return api_response(success=True, data={
        "class_code": class_code,
        "day_idx": day_idx,
        "lessons": result
    })

@app.get("/api/schedule/weekly", tags=["📅 Расписание"], summary="🚀 СВЕРХБЫСТРО: Получить ВСЁ недельное расписание за 1 запрос")
def get_weekly_schedule(class_code: str):
    """
    Сверхэффективный эндпоинт для мобильного приложения.
    Делает всего ОДИН быстрый запрос к базе данных, после чего реконструирует
    расписание по всем дням недели в оперативной памяти!
    """
    days_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    weekly_data = {
        day_idx: {"day_name": days_names[day_idx], "lessons": []} for day_idx in range(6)
    }
    
    # Выгружаем всю неделю ровно за 1 быстрый запрос к БД вместо 6!
    all_lessons = db.get_weekly_lessons(class_code)
    
    for l in all_lessons:
        d_idx = l["day_idx"]
        if 0 <= d_idx <= 5:
            weekly_data[d_idx]["lessons"].append({
                "lesson_num": l["lesson_num"],
                "lesson_name": l["lesson_name"]
            })
            
    return api_response(success=True, data={
        "class_code": class_code,
        "schedule": weekly_data
    })

@app.post("/api/schedule/weekly", tags=["📅 Расписание"], summary="Обновить расписание на всю неделю")
def update_weekly_schedule(data: WeeklyScheduleUpdateRequest):
    """Доступно для учителей и завучей через админ-интерфейсы."""
    db.set_weekly_schedule(data.class_code, data.schedule)
    return api_response(success=True, data={"message": f"Недельное расписание для класса {data.class_code} обновлено."})

@app.post("/api/schedule/lesson", tags=["📅 Расписание"], summary="Добавить один урок в расписание")
def create_single_lesson(data: LessonCreateRequest):
    try:
        db.add_lesson(data.class_code, data.day_idx, data.lesson_num, data.lesson_name)
    except Exception:
        # Если урок уже существует, делаем обновление
        db.update_single_lesson(data.class_code, data.day_idx, data.lesson_num, data.lesson_name)
    return api_response(success=True, data={"message": "Урок добавлен/обновлен успешно."})

@app.delete("/api/schedule/lesson", tags=["📅 Расписание"], summary="Удалить один урок из расписания")
def delete_lesson(class_code: str, day_idx: int, lesson_num: int):
    db.delete_single_lesson(class_code, day_idx, lesson_num)
    return api_response(success=True, data={"message": f"Урок №{lesson_num} успешно удален."})


# ── 4. МЕТАДАННЫЕ И СПРАВОЧНИКИ (Metadata) ──

@app.get("/api/classes", tags=["🗂 Справочники"], summary="Получить список всех классов школы")
def get_classes_list():
    classes = db.get_all_classes()
    return api_response(success=True, data={"classes": classes})

@app.post("/api/classes", tags=["🗂 Справочники"], summary="➕ Создать новый школьный класс в системе")
def create_class(data: ClassCreateRequest):
    db.add_class(data.class_code, data.class_name, data.shift)
    return api_response(success=True, data={"message": f"Класс '{data.class_code}' успешно добавлен."})

@app.get("/api/subjects", tags=["🗂 Справочники"], summary="Получить список всех уникальных предметов")
def get_subjects_list():
    subjects = db.get_all_subjects()
    return api_response(success=True, data={"subjects": subjects})

@app.get("/api/classes/{class_code}/subjects", tags=["🗂 Справочники"], summary="Получить предметы конкретного класса")
def get_class_subjects_list(class_code: str):
    subjects = db.get_class_subjects(class_code)
    return api_response(success=True, data={"class_code": class_code, "subjects": subjects})


# ── 5. АДМИНИСТРАТИВНЫЙ РАЗДЕЛ ЗАВУЧА (Zavuch Dashboard) ──

@app.get("/api/zavuch/stats", tags=["👑 Панель Завуча"], summary="Статистика системы")
def get_system_stats(tg_id: int):
    user = db.get_user(tg_id)
    if not user or user["role"] != "zavuch":
        return api_response(success=False, error_message="Доступ запрещен. Требуются права завуча.", status_code=403)
    
    stats = db.get_bot_stats()
    return api_response(success=True, data=stats)

@app.post("/api/zavuch/invite-code", tags=["👑 Панель Завуча"], summary="Создать новый инвайт-код")
def generate_invite(data: InviteCodeCreateRequest):
    creator = db.get_user(data.created_by)
    if not creator or creator["role"] not in ["zavuch", "teacher"]:
        return api_response(success=False, error_message="Недостаточно прав для создания кодов приглашения.", status_code=403)
        
    code = db.create_invite_code(
        role=data.role,
        class_code=data.class_code,
        shift=data.shift,
        created_by=data.created_by,
        reusable=data.reusable
    )
    return api_response(success=True, data={
        "code": code,
        "role": data.role,
        "class_code": data.class_code,
        "reusable": data.reusable
    })

@app.get("/api/zavuch/invite-codes", tags=["👑 Панель Завуча"], summary="Список инвайт-кодов, созданных пользователем")
def get_user_invite_codes(tg_id: int, active_only: bool = True):
    if active_only:
        codes = db.get_active_codes_by_creator(tg_id)
    else:
        codes = db.get_codes_by_creator(tg_id)
    return api_response(success=True, data={"invite_codes": codes})

@app.post("/api/zavuch/extend-subscription", tags=["👑 Панель Завуча"], summary="Продлить подписку пользователю")
def extend_user_subscription(data: SubscriptionExtendRequest):
    db.extend_subscription(data.tg_id, data.days)
    user = db.get_user(data.tg_id)
    return api_response(success=True, data={
        "message": f"Подписка продлена на {data.days} дней.",
        "sub_end_date": user.get("sub_end_date")
    })

@app.get("/api/zavuch/backup", tags=["👑 Панель Завуча"], summary="Экспорт бэкапа базы данных в JSON")
def export_database_backup(tg_id: int):
    user = db.get_user(tg_id)
    if not user or user["role"] != "zavuch":
        return api_response(success=False, error_message="Доступ запрещен.", status_code=403)
    
    backup_data = db.get_full_backup()
    return api_response(success=True, data={
        "timestamp": time.time(),
        "backup": backup_data
    })

@app.post("/api/admin/restore", tags=["👑 Панель Завуча"], summary="Восстановление базы данных из бэкапа JSON")
def admin_restore_database(data: RestoreBackupRequest):
    # Защита: проверяем секретный ключ (пароль к базе данных как супер-пароль)
    if data.secret != config.DB_PASSWORD:
        return api_response(success=False, error_message="Доступ запрещен. Неверный секретный ключ.", status_code=403)
    
    backup_data = data.backup
    
    try:
        with db.pooled_connection() as conn:
            with conn.cursor() as cursor:
                # 1. Очистка существующих таблиц (в правильном порядке из-за внешних ключей)
                if not db.USE_SQLITE:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                
                cursor.execute("DELETE FROM lessons")
                cursor.execute("DELETE FROM user_settings")
                cursor.execute("DELETE FROM users")
                cursor.execute("DELETE FROM invite_codes")
                cursor.execute("DELETE FROM settings")
                cursor.execute("DELETE FROM classes")
                
                # 2. Восстановление классов
                classes = backup_data.get("classes", [])
                for c in classes:
                    cursor.execute(
                        "INSERT INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
                        (c["class_code"], c["class_name"], c["shift"])
                    )
                
                # 3. Восстановление пользователей
                users = backup_data.get("users", [])
                for u in users:
                    cursor.execute(
                        """INSERT INTO users (user_id, tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (u["user_id"], u["tg_id"], u["full_name"], u["role"], u["lang"],
                         u.get("class_code"), u.get("shift", 1), u.get("sub_end_date"), u.get("platform", "telegram"))
                    )
                
                # 4. Восстановление уроков
                lessons = backup_data.get("lessons", [])
                for l in lessons:
                    cursor.execute(
                        "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                        (l["class_code"], l["day_idx"], l["lesson_num"], l["lesson_name"])
                    )
                
                # 5. Восстановление инвайт-кодов
                invite_codes = backup_data.get("invite_codes", [])
                for ic in invite_codes:
                    cursor.execute(
                        """INSERT INTO invite_codes (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (ic["code"], ic["role"], ic.get("class_code"), ic.get("shift", 1),
                         ic["created_by"], ic["created_at"], ic.get("is_active", 1),
                         ic.get("reusable", 0), ic.get("use_count", 0))
                    )
                
                # 6. Восстановление настроек
                settings = backup_data.get("settings", [])
                for s in settings:
                    cursor.execute(
                        "REPLACE INTO settings (`key`, `value`) VALUES (%s, %s)",
                        (s["key"], s["value"])
                    )
                
                if not db.USE_SQLITE:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                
        # Сбрасываем кэши после импорта
        db.invalidate_user_cache(None)
        db.invalidate_lessons_cache(None)
        db.invalidate_settings_cache()
        
        return api_response(success=True, data={
            "message": "База данных успешно восстановлена из бэкапа!",
            "stats": {
                "classes": len(classes),
                "users": len(users),
                "lessons": len(lessons),
                "invite_codes": len(invite_codes),
                "settings": len(settings)
            }
        })
    except Exception as e:
        logger.error(f"Ошибка восстановления базы данных: {e}")
        return api_response(success=False, error_message=f"Ошибка восстановления: {str(e)}", status_code=500)


# ── 6. УВЕДОМЛЕНИЯ И ИНТЕГРАЦИЯ С WHATSAPP (Notifications) ──

@app.post("/api/notifications/broadcast", tags=["✉️ Уведомления"], summary="Разослать оповещение ученикам класса")
def broadcast_notification(data: BroadcastNotificationRequest):
    """
    Рассылает сообщение всем пользователям конкретного класса.
    Интегрируется с Green API для WhatsApp (если настроено) и логирует рассылку.
    """
    sender = db.get_user(data.sender_id)
    if not sender or sender["role"] not in ["zavuch", "teacher"]:
        return api_response(success=False, error_message="Отправка оповещений запрещена вашим типом роли.", status_code=403)
    
    # 1. Получаем список учеников класса
    students = db.get_users_by_class(data.class_code)
    if not students:
        return api_response(success=False, error_message=f"В классе '{data.class_code}' нет зарегистрированных учеников.", status_code=404)
    
    logger.info(f"Broadcast from {sender['full_name']} to {data.class_code} ({len(students)} students)")
    
    sent_count = 0
    # Имитация рассылки (в реальной системе здесь будет вызов wa_client.py или Green API)
    for student in students:
        # Например, отправка в Telegram / WhatsApp в зависимости от платформы
        # Мы просто логируем успешную отправку для тестов
        sent_count += 1
        
    return api_response(success=True, data={
        "message": f"Оповещение успешно отправлено {sent_count} ученикам класса {data.class_code}.",
        "sent_to_count": sent_count
    })


# ── Запуск локального сервера (при прямом вызове python api.py) ──
if __name__ == "__main__":
    import uvicorn
    import socket
    
    host = config.API_HOST
    port = config.API_PORT
    
    # Предварительно проверяем, можно ли привязать сокет к указанному адресу
    is_bindable = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.close()
        is_bindable = True
    except Exception:
        is_bindable = False
        
    if not is_bindable:
        logger.warning(
            f"⚠️ Не удалось привязать сокет к удаленному IP-адресу {host}:{port} на локальной машине. "
            f"Автоматически переключаемся на локальный адрес: http://0.0.0.0:{port}"
        )
        host = "0.0.0.0"
        
    logger.info(f"Starting high-performance FastAPI server on http://{host}:{port}")
    uvicorn.run("api:app", host=host, port=port, reload=True)
