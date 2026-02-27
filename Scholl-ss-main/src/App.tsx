import React, { useState, useEffect, useRef } from 'react';
import {
  KeyRound,
  CalendarDays,
  Users as UsersIcon,
  LogOut,
  Trash2,
  Plus,
  GraduationCap,
  BookOpen,
  School,
  ChevronDown,
  Check,
  Save,
  X,
  Edit3,
  Menu
} from 'lucide-react';

type Page = 'login' | 'dashboard' | 'schedule' | 'users';

const CLASSES_LIST = ['8 А', '8 Ә', '9 Б', '10 А', '11 Б'];

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('login');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  if (currentPage === 'login') {
    return <Login onLogin={() => setCurrentPage('dashboard')} />;
  }

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/40 to-slate-900 text-white flex font-sans selection:bg-purple-500/30">

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden"
          onClick={closeMobileMenu}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 border-r border-white/10 bg-slate-900/95 lg:bg-black/20 backdrop-blur-xl flex flex-col shrink-0 transition-transform duration-300 ease-in-out ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="p-6 flex items-center justify-between gap-3 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center shadow-[0_0_15px_rgba(147,51,234,0.5)]">
              <School className="w-6 h-6 text-white" />
            </div>
            <span className="font-bold text-lg tracking-wide">SchoolBot</span>
          </div>
          <button className="lg:hidden text-white/70 hover:text-white" onClick={closeMobileMenu}>
            <X size={24} />
          </button>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          <SidebarItem
            icon={<KeyRound size={20} />}
            label="Инвайт-коды"
            active={currentPage === 'dashboard'}
            onClick={() => { setCurrentPage('dashboard'); closeMobileMenu(); }}
          />
          <SidebarItem
            icon={<CalendarDays size={20} />}
            label="Расписание"
            active={currentPage === 'schedule'}
            onClick={() => { setCurrentPage('schedule'); closeMobileMenu(); }}
          />
          <SidebarItem
            icon={<UsersIcon size={20} />}
            label="Ученики/Учителя"
            active={currentPage === 'users'}
            onClick={() => { setCurrentPage('users'); closeMobileMenu(); }}
          />
        </nav>

        <div className="p-4 border-t border-white/10">
          <button
            onClick={() => setCurrentPage('login')}
            className="flex items-center gap-3 w-full p-3 rounded-xl text-white/70 hover:text-white hover:bg-white/5 transition-all"
          >
            <LogOut size={20} />
            <span>Выйти</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative w-full">
        <header className="h-16 lg:h-20 border-b border-white/10 bg-slate-900/50 backdrop-blur-md flex items-center px-4 lg:px-8 shrink-0 gap-4 z-30">
          <button
            className="lg:hidden p-2 -ml-2 text-white/70 hover:text-white rounded-lg hover:bg-white/5"
            onClick={() => setIsMobileMenuOpen(true)}
          >
            <Menu size={24} />
          </button>
          <h1 className="text-xl lg:text-2xl font-semibold truncate">
            {currentPage === 'dashboard' && 'Управление инвайт-кодами'}
            {currentPage === 'schedule' && 'Расписание занятий'}
            {currentPage === 'users' && 'Пользователи бота'}
          </h1>
        </header>
        <div className="flex-1 overflow-auto p-4 lg:p-8">
          {currentPage === 'dashboard' && <Dashboard />}
          {currentPage === 'schedule' && <Schedule />}
          {currentPage === 'users' && <Users />}
        </div>
      </main>
    </div>
  );
}

function SidebarItem({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 w-full p-3 rounded-xl transition-all ${active
        ? 'bg-white/10 text-white shadow-[inset_0_0_20px_rgba(255,255,255,0.05)]'
        : 'text-white/60 hover:text-white hover:bg-white/5'
        }`}
    >
      <div className={active ? 'text-purple-400' : ''}>{icon}</div>
      <span className="font-medium">{label}</span>
    </button>
  );
}

// --- Custom Select Component ---
function CustomSelect({
  value,
  options,
  onChange,
  placeholder = "Выберите..."
}: {
  value: string,
  options: string[],
  onChange: (val: string) => void,
  placeholder?: string
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative w-full" ref={dropdownRef}>
      <div
        className={`w-full bg-black/20 border ${isOpen ? 'border-purple-500/50' : 'border-white/10'} rounded-xl px-4 py-2.5 text-white cursor-pointer flex justify-between items-center hover:bg-black/30 transition-all`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={value ? 'text-white' : 'text-white/50'} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value || placeholder}</span>
        <ChevronDown size={18} className={`text-white/50 transition-transform duration-200 shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-full min-w-[160px] bg-slate-800/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl z-[100] overflow-hidden py-2 animate-in fade-in slide-in-from-top-2 duration-200">
          {options.map(opt => (
            <div
              key={opt}
              className={`px-4 py-2.5 cursor-pointer flex items-center gap-3 transition-colors ${value === opt ? 'bg-white/10' : 'hover:bg-white/5'}`}
              onClick={() => { onChange(opt); setIsOpen(false); }}
            >
              <div className="w-5 flex justify-center shrink-0">
                {value === opt && <Check size={18} className="text-white" />}
              </div>
              <span className="text-base font-medium text-white/90">{opt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      if (res.ok) onLogin();
      else {
        const data = await res.json();
        setError(data.detail || 'Ошибка авторизации');
      }
    } catch {
      setError('Ошибка сети');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/50 to-indigo-950 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-md bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
        {/* Decorative glow */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-purple-500/30 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/30 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 flex flex-col items-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center shadow-[0_0_20px_rgba(147,51,234,0.5)] mb-6">
            <School className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-2">SchoolBot Admin</h2>
          <p className="text-white/60 mb-6 text-center">Панель управления школьным Telegram-ботом</p>
          {error && <p className="text-red-400 mb-4 bg-red-400/10 px-4 py-2 rounded-lg">{error}</p>}

          <form onSubmit={handleSubmit} className="w-full space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-white/80 ml-1">Код доступа</label>
              <input
                type="password"
                value={code}
                onChange={e => setCode(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl shadow-[0_0_20px_rgba(147,51,234,0.4)] hover:shadow-[0_0_30px_rgba(147,51,234,0.6)] transition-all duration-300"
            >
              Войти в систему
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const [role, setRole] = useState('Ученик');
  const [className, setClassName] = useState('8 А');
  const [shift, setShift] = useState('1 смена');
  const [codes, setCodes] = useState<any[]>([]);

  useEffect(() => { loadCodes(); }, []);

  const loadCodes = async () => {
    try {
      const r = await fetch('/api/codes');
      if (r.ok) setCodes(await r.json());
    } catch { }
  };

  const generateCode = async () => {
    try {
      await fetch('/api/codes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: role === 'Ученик' ? 'student' : 'teacher',
          class_code: role === 'Ученик' ? className : '',
          shift: parseInt(shift.split(' ')[0])
        })
      });
      loadCodes();
    } catch { }
  };

  return (
    <div className="space-y-6 lg:space-y-8 max-w-5xl mx-auto animate-in fade-in duration-300">
      {/* Create Code Card */}
      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-5 lg:p-6 shadow-xl relative z-20">
        <h2 className="text-lg lg:text-xl font-semibold mb-4 lg:mb-6 flex items-center gap-2">
          <Plus className="text-purple-400" size={24} />
          Создать новый код
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div className="space-y-2">
            <label className="text-sm text-white/70 ml-1">Роль</label>
            <CustomSelect
              value={role}
              options={['Ученик', 'Учитель']}
              onChange={setRole}
            />
          </div>

          {role === 'Ученик' && (
            <div className="space-y-2 animate-in fade-in slide-in-from-left-2 duration-200">
              <label className="text-sm text-white/70 ml-1">Класс</label>
              <CustomSelect
                value={className}
                options={CLASSES_LIST}
                onChange={setClassName}
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm text-white/70 ml-1">Смена</label>
            <CustomSelect
              value={shift}
              options={['1 смена', '2 смена']}
              onChange={setShift}
            />
          </div>

          <button onClick={generateCode} className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium py-2.5 px-4 rounded-xl shadow-[0_0_15px_rgba(147,51,234,0.4)] hover:shadow-[0_0_25px_rgba(147,51,234,0.6)] transition-all h-[46px] sm:col-span-2 lg:col-span-1 lg:col-start-4">
            Сгенерировать
          </button>
        </div>
      </div>

      {/* Codes Table */}
      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl overflow-hidden relative z-10">
        <div className="p-5 lg:p-6 border-b border-white/10">
          <h2 className="text-lg lg:text-xl font-semibold">Активные инвайт-коды</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[600px]">
            <thead>
              <tr className="bg-black/20">
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Код</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Роль</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Класс</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Смена</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Использований</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {codes.map((item, i) => (
                <tr key={i} className="hover:bg-white/5 transition-colors">
                  <td className="p-4 font-mono text-purple-300 whitespace-nowrap">{item.code}</td>
                  <td className="p-4 whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${item.role === 'student'
                      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      }`}>
                      {item.role === 'student' ? <GraduationCap size={14} /> : <BookOpen size={14} />}
                      {item.role === 'student' ? 'Ученик' : 'Учитель'}
                    </span>
                  </td>
                  <td className="p-4 text-white/90 whitespace-nowrap">{item.class}</td>
                  <td className="p-4 text-white/90 whitespace-nowrap">{item.shift}</td>
                  <td className="p-4 text-white/70 whitespace-nowrap">{item.uses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const INITIAL_SCHEDULE = [
  ['Алгебра', 'Физика', 'История', 'Каз. язык', 'Биология'],
  ['Геометрия', 'Информатика', 'Англ. язык', 'Каз. лит.', 'Химия'],
  ['Физика', 'Физкультура', 'География', 'Алгебра', 'Рус. язык'],
  ['Рус. язык', 'Англ. язык', 'Биология', 'Геометрия', 'История'],
  ['Физкультура', 'Каз. язык', 'Химия', 'Информатика', 'География'],
  ['-', '-', 'Классный час', '-', '-'],
];

function Schedule() {
  const [selectedClass, setSelectedClass] = useState('8 А');
  const [isChanging, setIsChanging] = useState(false);

  const [isEditing, setIsEditing] = useState(false);
  const [schedule, setSchedule] = useState<string[][]>([]);
  const [tempSchedule, setTempSchedule] = useState<string[][]>([]);

  const days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];

  useEffect(() => { loadSchedule(selectedClass); }, []);

  const loadSchedule = async (cls: string) => {
    setIsChanging(true);
    try {
      const res = await fetch(`/api/schedule?class_code=${encodeURIComponent(cls)}`);
      if (res.ok) {
        const data = await res.json();
        setSchedule(data);
      }
    } catch { }
    setIsChanging(false);
  };

  const handleClassChange = (newClass: string) => {
    if (isEditing) return; // Prevent changing class while editing
    setSelectedClass(newClass);
    loadSchedule(newClass);
  };

  const startEditing = () => {
    const matrix = JSON.parse(JSON.stringify(schedule));
    while (matrix.length < 8) matrix.push(['', '', '', '', '']);
    setTempSchedule(matrix);
    setIsEditing(true);
  };

  const saveChanges = async () => {
    try {
      await fetch('/api/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ class_code: selectedClass, schedule: tempSchedule })
      });
      setSchedule(tempSchedule);
      setIsEditing(false);
      loadSchedule(selectedClass);
    } catch { }
  };

  const cancelChanges = () => {
    setIsEditing(false);
  };

  const handleCellChange = (rowIndex: number, colIndex: number, value: string) => {
    const newSchedule = [...tempSchedule];
    newSchedule[rowIndex][colIndex] = value;
    setTempSchedule(newSchedule);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-4 shadow-xl gap-4 relative z-20">
        <div className="flex items-center gap-4 w-full sm:w-64">
          <label className="text-white/70 font-medium whitespace-nowrap">Класс:</label>
          <div className={isEditing ? 'opacity-50 pointer-events-none w-full' : 'w-full'}>
            <CustomSelect
              value={selectedClass}
              options={CLASSES_LIST}
              onChange={handleClassChange}
            />
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          {isEditing ? (
            <>
              <button
                onClick={cancelChanges}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 text-white/80 px-4 py-2.5 rounded-xl transition-colors border border-white/10 text-sm font-medium"
              >
                <X size={16} />
                Отмена
              </button>
              <button
                onClick={saveChanges}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 px-4 py-2.5 rounded-xl transition-colors border border-emerald-500/30 text-sm font-medium shadow-[0_0_15px_rgba(16,185,129,0.2)]"
              >
                <Save size={16} />
                Сохранить
              </button>
            </>
          ) : (
            <button
              onClick={startEditing}
              className="w-full sm:w-auto flex items-center justify-center gap-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 px-4 py-2.5 rounded-xl transition-colors border border-purple-500/30 text-sm font-medium"
            >
              <Edit3 size={16} />
              Редактировать
            </button>
          )}
        </div>
      </div>

      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl overflow-hidden relative z-10">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead>
              <tr className="bg-black/20 border-b border-white/10">
                <th className="p-4 w-16 text-center text-white/50 font-medium">#</th>
                {days.map(day => (
                  <th key={day} className="p-4 text-white/80 font-medium text-center border-l border-white/5 w-1/5">{day}</th>
                ))}
              </tr>
            </thead>
            <tbody className={`divide-y divide-white/5 transition-opacity duration-150 ${isChanging ? 'opacity-0' : 'opacity-100'}`}>
              {(isEditing ? tempSchedule : schedule).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  <td className="p-4 text-center text-white/50 font-medium bg-black/10">{rowIndex + 1}</td>
                  {row.map((lesson, colIndex) => (
                    <td
                      key={colIndex}
                      className="p-3 text-center border-l border-white/5 hover:bg-white/5 transition-colors group relative"
                    >
                      {isEditing ? (
                        <input
                          type="text"
                          value={lesson}
                          onChange={(e) => handleCellChange(rowIndex, colIndex, e.target.value)}
                          className="w-full bg-black/30 border border-purple-500/30 rounded-lg px-3 py-2 text-center text-white text-sm focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all placeholder-white/20"
                          placeholder="Пусто"
                        />
                      ) : (
                        <span className={`inline-block px-3 py-1.5 rounded-lg text-sm w-full ${lesson === '-' || !lesson ? 'text-white/20' : 'bg-white/5 text-white/90 group-hover:bg-purple-500/20 group-hover:text-purple-200 transition-colors'
                          }`}>
                          {lesson || '-'}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Users() {
  const [users, setUsers] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/users').then(r => r.json()).then(setUsers).catch(console.error);
  }, []);

  return (
    <div className="max-w-6xl mx-auto animate-in fade-in duration-300">
      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl overflow-hidden relative z-10">
        <div className="p-5 lg:p-6 border-b border-white/10 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
          <h2 className="text-lg lg:text-xl font-semibold">Зарегистрированные пользователи</h2>
          <div className="self-start sm:self-auto bg-black/20 border border-white/10 rounded-xl px-3 py-1.5 text-sm text-white/70">
            Всего: {users.length}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[700px]">
            <thead>
              <tr className="bg-black/20">
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Имя</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Telegram ID</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Роль</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Класс</th>
                <th className="p-4 text-white/60 font-medium text-sm whitespace-nowrap">Смена</th>
                <th className="p-4 text-white/60 font-medium text-sm text-right whitespace-nowrap">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-white/5 transition-colors group">
                  <td className="p-4 font-medium text-white/90 whitespace-nowrap">{user.name}</td>
                  <td className="p-4 font-mono text-white/50 text-sm whitespace-nowrap">{user.tgId}</td>
                  <td className="p-4 whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${user.role === 'Ученик'
                      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      }`}>
                      {user.role === 'Ученик' ? 'Ученик' : 'Учитель'}
                    </span>
                  </td>
                  <td className="p-4 text-white/70 whitespace-nowrap">{user.class}</td>
                  <td className="p-4 text-white/70 whitespace-nowrap">{user.shift}</td>
                  <td className="p-4 text-right whitespace-nowrap">
                    <button className="p-2 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-100 lg:opacity-0 lg:group-hover:opacity-100">
                      <Trash2 size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
