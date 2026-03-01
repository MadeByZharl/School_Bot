import { useEffect, useState } from 'react';
import WebApp from '@twa-dev/sdk';
import { Calendar, User, BookOpen, Loader2 } from 'lucide-react';
import './App.css';

interface UserData {
  id: number;
  role: string;
  class_code: string;
  name: string;
}

function App() {
  const [activeTab, setActiveTab] = useState('schedule');
  const [userData, setUserData] = useState<UserData | null>(null);
  const [schedule, setSchedule] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    WebApp.ready();
    WebApp.expand();

    // Set theme color
    WebApp.setHeaderColor('secondary_bg_color');
    WebApp.setBackgroundColor('bg_color');

    // Fetch data
    const fetchData = async () => {
      try {
        const initData = WebApp.initData || '';

        // Use full URL if testing locally without initData, otherwise relative
        const baseUrl = initData ? '' : 'http://localhost:8000';

        // Fetch user data
        const userRes = await fetch(`${baseUrl}/api/student/me`, {
          headers: { 'twa-init-data': initData }
        });

        if (!userRes.ok) throw new Error('Не удалось загрузить данные пользователя');
        const userJson = await userRes.json();
        setUserData(userJson);

        // Fetch schedule
        const schedRes = await fetch(`${baseUrl}/api/student/schedule`, {
          headers: { 'twa-init-data': initData }
        });

        if (!schedRes.ok) throw new Error('Не удалось загрузить расписание');
        const schedJson = await schedRes.json();
        setSchedule(schedJson);

      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];

  return (
    <div className="flex flex-col min-h-screen font-sans" style={{ backgroundColor: 'var(--tg-theme-secondary-bg-color, #f3f4f6)', color: 'var(--tg-theme-text-color, #111827)' }}>
      <header className="p-4 shadow-sm border-b" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)', borderColor: 'var(--tg-theme-hint-color, #e5e7eb)20' }}>
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-500 to-indigo-500 bg-clip-text text-transparent">Dnevnik App</h1>
        <p className="text-sm font-medium tracking-wide" style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>
          {userData ? `Привет, ${userData.name.split(' ')[0]} 👋` : `Привет, Студент 👋`}
        </p>
      </header>

      <main className="flex-1 p-4 overflow-y-auto pb-24">
        {loading && (
          <div className="flex flex-col items-center justify-center h-64 space-y-4">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <p className="font-medium" style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>Загрузка данных...</p>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 p-4 rounded-xl text-center border border-red-100 dark:border-red-800/50">
            <p className="font-semibold">Ошибка</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && activeTab === 'schedule' && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h2 className="text-lg font-bold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-blue-500" /> Расписание
              </span>
              <span className="text-sm font-semibold px-3 py-1 rounded-full" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)' }}>
                {userData?.class_code}
              </span>
            </h2>

            {schedule.length === 0 ? (
              <div className="p-6 rounded-2xl shadow-sm text-center" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)' }}>
                <p style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>Расписание пока пусто.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {DAYS.map((day, dIdx) => {
                  const dayLessons = schedule.map(row => row[dIdx]).filter(Boolean);
                  if (dayLessons.length === 0) return null;

                  return (
                    <div key={dIdx} className="rounded-2xl shadow-sm overflow-hidden border" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)', borderColor: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}>
                      <div className="px-4 py-3 border-b" style={{ backgroundColor: 'var(--tg-theme-secondary-bg-color, #f9fafb)', borderColor: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}>
                        <h3 className="font-bold">{day}</h3>
                      </div>
                      <div className="divide-y" style={{ borderColor: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}>
                        {schedule.map((row, lIdx) => {
                          const lesson = row[dIdx];
                          if (!lesson) return null;
                          return (
                            <div key={lIdx} className="flex items-center px-4 py-3">
                              <span className="w-8 text-center font-bold text-sm" style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>{lIdx + 1}</span>
                              <div className="w-px h-8 mx-3" style={{ backgroundColor: 'var(--tg-theme-secondary-bg-color, #e5e7eb)' }}></div>
                              <span className="font-medium text-[15px]">{lesson}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {!loading && !error && activeTab === 'homework' && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-green-500" /> Домашнее задание
            </h2>
            <div className="p-8 rounded-2xl shadow-sm flex flex-col items-center justify-center text-center" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)' }}>
              <div className="w-16 h-16 bg-gradient-to-tr from-green-400 to-emerald-500 text-white rounded-full flex items-center justify-center mb-4 shadow-lg shadow-green-500/30">
                <BookOpen className="w-8 h-8" />
              </div>
              <h3 className="font-bold text-lg mb-1">ДЗ пока недоступно</h3>
              <p className="text-sm leading-relaxed max-w-xs" style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>
                Учителя скоро начнут добавлять сюда домашние задания по предметам.
              </p>
            </div>
          </div>
        )}

        {!loading && !error && activeTab === 'profile' && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <User className="w-5 h-5 text-purple-500" /> Профиль
            </h2>
            <div className="p-6 rounded-2xl shadow-sm" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)' }}>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-gradient-to-tr from-purple-500 to-pink-500 text-white rounded-full flex items-center justify-center text-2xl font-bold shadow-lg shadow-purple-500/30">
                  {userData?.name?.[0] || 'С'}
                </div>
                <div>
                  <h3 className="font-bold text-xl">{userData?.name || 'Студент'}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-xs font-bold px-2.5 py-0.5 rounded-md uppercase tracking-wider">
                      {userData?.role === 'student' ? 'Ученик' : userData?.role}
                    </span>
                    <span className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs font-bold px-2.5 py-0.5 rounded-md">
                      {userData?.class_code}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between items-center py-3 border-b border-gray-50 dark:border-gray-750">
                  <span style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>ID пользователя</span>
                  <span className="font-medium">{userData?.id}</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-50 dark:border-gray-750">
                  <span style={{ color: 'var(--tg-theme-hint-color, #9ca3af)' }}>Статус аккаунта</span>
                  <span className="font-medium text-green-500 flex items-center gap-1">Активен <div className="w-2 h-2 rounded-full bg-green-500"></div></span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <nav className="fixed bottom-0 w-full border-t flex justify-around p-2 pb-safe z-50 transition-colors" style={{ backgroundColor: 'var(--tg-theme-bg-color, #ffffff)', borderColor: 'var(--tg-theme-hint-color, #e5e7eb)30' }}>
        <button
          onClick={() => {
            setActiveTab('schedule');
            WebApp.HapticFeedback.impactOccurred('light');
          }}
          className={`flex flex-col items-center justify-center w-20 h-14 rounded-xl transition-all ${activeTab === 'schedule' ? 'text-blue-500 bg-blue-50 dark:bg-blue-900/40 shadow-sm' : ''}`}
          style={{ color: activeTab === 'schedule' ? '' : 'var(--tg-theme-hint-color, #9ca3af)' }}
        >
          <Calendar className="w-6 h-6 mb-1" strokeWidth={activeTab === 'schedule' ? 2.5 : 2} />
          <span className="text-[10px] font-bold tracking-wide">Уроки</span>
        </button>
        <button
          onClick={() => {
            setActiveTab('homework');
            WebApp.HapticFeedback.impactOccurred('light');
          }}
          className={`flex flex-col items-center justify-center w-20 h-14 rounded-xl transition-all ${activeTab === 'homework' ? 'text-green-500 bg-green-50 dark:bg-green-900/40 shadow-sm' : ''}`}
          style={{ color: activeTab === 'homework' ? '' : 'var(--tg-theme-hint-color, #9ca3af)' }}
        >
          <BookOpen className="w-6 h-6 mb-1" strokeWidth={activeTab === 'homework' ? 2.5 : 2} />
          <span className="text-[10px] font-bold tracking-wide">ДЗ</span>
        </button>
        <button
          onClick={() => {
            setActiveTab('profile');
            WebApp.HapticFeedback.impactOccurred('light');
          }}
          className={`flex flex-col items-center justify-center w-20 h-14 rounded-xl transition-all ${activeTab === 'profile' ? 'text-purple-500 bg-purple-50 dark:bg-purple-900/40 shadow-sm' : ''}`}
          style={{ color: activeTab === 'profile' ? '' : 'var(--tg-theme-hint-color, #9ca3af)' }}
        >
          <User className="w-6 h-6 mb-1" strokeWidth={activeTab === 'profile' ? 2.5 : 2} />
          <span className="text-[10px] font-bold tracking-wide">Профиль</span>
        </button>
      </nav>
    </div>
  );
}

export default App;
