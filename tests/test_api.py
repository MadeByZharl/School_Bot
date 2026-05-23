"""
🎒 Integration & Unit Tests for FastAPI School Bot Backend.
Runs fully in-memory via SQLite for high performance and zero test-clutter.
"""

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Позволяем pytest находить пакет без установки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Форсируем использование локального SQLite для тестов
os.environ["USE_SQLITE"] = "1"
os.environ["DB_HOST"] = "test_host"
os.environ["DB_USER"] = "test_user"
os.environ["DB_PASSWORD"] = "test_pass"
os.environ["DB_NAME"] = "test_db"

from api import app
import db

# Создаем клиент тестирования FastAPI
client = TestClient(app)


@pytest.fixture(autouse=True)
def run_around_tests():
    """Фикстура для пересоздания базы перед каждым тестом (чистое окружение)."""
    # Инициализируем базу данных (создает таблицы и накатывает демо-данные)
    db.init_db()
    yield
    # При желании можно очистить кэш
    db.invalidate_lessons_cache()
    db.invalidate_settings_cache()


def test_api_classes_endpoint():
    """Тестируем получение списка классов."""
    response = client.get("/api/classes")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert "8Ә" in res_json["data"]["classes"]


def test_api_subjects_list():
    """Тестируем получение списка уникальных предметов."""
    response = client.get("/api/subjects")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert isinstance(res_json["data"]["subjects"], list)


def test_api_invite_code_validation_success():
    """Тестируем валидацию существующего инвайт-кода."""
    # 1. Создаем многоразовый код ученика через внутреннее API бэка
    code = db.create_invite_code("student", "8Ә", 1, 99999, reusable=True)
    
    # 2. Проверяем валидацию кода по API
    response = client.get(f"/api/auth/invite-code/{code}")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["role"] == "student"
    assert res_json["data"]["class_code"] == "8Ә"
    assert res_json["data"]["shift"] == 1


def test_api_invite_code_validation_fail():
    """Тестируем валидацию несуществующего инвайт-кода."""
    response = client.get("/api/auth/invite-code/NON_EXISTENT_CODE_123")
    assert response.status_code == 400
    res_json = response.json()
    assert res_json["success"] is False
    assert "Неверный" in res_json["error"]["message"]


def test_api_weekly_schedule_retrieval():
    """Тестируем сверхбыструю выгрузку недельного расписания."""
    response = client.get("/api/schedule/weekly?class_code=8Ә")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["class_code"] == "8Ә"
    
    # Убеждаемся, что недельное расписание содержит все дни от 0 до 5
    schedule = res_json["data"]["schedule"]
    for day_idx in ["0", "1", "2", "3", "4", "5"]:
        assert day_idx in schedule
        assert "day_name" in schedule[day_idx]
        assert "lessons" in schedule[day_idx]


def test_api_register_user_flow():
    """Тестируем полный флоу регистрации нового пользователя по инвайт-коду."""
    # 1. Создаем инвайт-код
    code = db.create_invite_code("student", "8Ә", 1, 99999, reusable=False)
    
    # 2. Регистрируемся
    register_payload = {
        "tg_id": 123456789,
        "full_name": "Тестовый Студент Студентович",
        "invite_code": code,
        "lang": "kk"
    }
    response = client.post("/api/auth/register", json=register_payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["user"]["full_name"] == "Тестовый Студент Студентович"
    assert res_json["data"]["user"]["role"] == "student"
    assert res_json["data"]["user"]["lang"] == "kk"
    assert "token" in res_json["data"]
    
    # 3. Убеждаемся, что код стал неактивным (так как reusable=False)
    response_validate = client.get(f"/api/auth/invite-code/{code}")
    assert response_validate.status_code == 400


def test_api_login_success():
    """Тестируем успешный вход зарегистрированного пользователя."""
    # Добавляем пользователя вручную в базу
    db.add_user(tg_id=55555, full_name="Иван Завуч", role="zavuch", lang="ru")
    
    # Пытаемся войти
    response = client.post("/api/auth/login", json={"tg_id": 55555})
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["user"]["role"] == "zavuch"
    assert "token" in res_json["data"]


def test_api_login_fail():
    """Тестируем ошибку при входе незарегистрированного пользователя."""
    response = client.post("/api/auth/login", json={"tg_id": 99999999})
    assert response.status_code == 404
    res_json = response.json()
    assert res_json["success"] is False
    assert "Пользователь не найден" in res_json["error"]["message"]


def test_api_rate_limiting_trigger():
    """Тестируем блокировку флуда (DDoS-атак) с помощью Rate Limiter (код 429)."""
    # Импортируем словари лимитов из бэкенда для очистки
    from api import _global_requests, _auth_requests
    _global_requests.clear()
    _auth_requests.clear()
    
    # Делаем 50 запросов подряд (лимит 50 за 10 сек)
    for _ in range(50):
        response = client.get("/api/classes")
        assert response.status_code == 200
        
    # 51-й запрос должен быть заблокирован с кодом 429
    response = client.get("/api/classes")
    assert response.status_code == 429
    res_json = response.json()
    assert res_json["success"] is False
    assert "Too many requests" in res_json["error"]["message"]
    
    # Очищаем за собой, чтобы не ломать другие тесты в сьюте
    _global_requests.clear()
    _auth_requests.clear()

