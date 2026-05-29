import { useState } from 'react';
import { BirthInfo } from './api';
import { isValid, parse, format } from 'date-fns';

interface BirthFormProps {
  onSubmit: (info: BirthInfo) => void;
  disabled: boolean;
  collapsed?: boolean;
  onExpand?: () => void;
  summary?: BirthInfo | null;
}

export default function BirthForm({ onSubmit, disabled, collapsed, onExpand, summary }: BirthFormProps) {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [place, setPlace] = useState('');
  const [timeUnknown, setTimeUnknown] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!date.trim()) {
      e.date = 'Date is required';
    } else {
      const parsed = parse(date, 'yyyy-MM-dd', new Date());
      if (!isValid(parsed)) e.date = 'Invalid date';
      else {
        const year = parsed.getFullYear();
        if (year < 1900 || year > new Date().getFullYear()) {
          e.date = 'Year must be between 1900 and now';
        }
      }
    }
    if (!timeUnknown && !time.trim()) {
      e.time = 'Time is required (or check unknown)';
    } else if (!timeUnknown && time.trim()) {
      if (!/^\d{1,2}:\d{2}$/.test(time.trim())) {
        e.time = 'Use HH:MM (24h)';
      } else {
        const [h, m] = time.split(':').map(Number);
        if (h < 0 || h > 23 || m < 0 || m > 59) e.time = 'Invalid time';
      }
    }
    if (!place.trim()) {
      e.place = 'Place is required';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate() || disabled) return;
    onSubmit({
      date: date.trim(),
      time: timeUnknown ? 'unknown' : time.trim(),
      place: place.trim(),
    });
  }

  if (collapsed && summary) {
    return (
      <button
        onClick={onExpand}
        className="w-full px-4 py-3 m-3 rounded-xl bg-[var(--card-bg)] border border-[var(--border-subtle)] hover:border-[rgba(201,75,31,0.3)] transition-all duration-150 text-left"
      >
        <span className="text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--accent)] block mb-0.5">Chart</span>
        <span className="text-[0.95rem] font-body text-[var(--text-primary)]">{summary.date} · {summary.time !== 'unknown' ? summary.time : 'Time unknown'} · {summary.place}</span>
      </button>
    );
  }

  const inputClass = (field: string) =>
    `w-full bg-[var(--input-bg)] border-[1.5px] ${
      errors[field] ? 'border-[rgba(201,75,31,0.5)]' : 'border-transparent'
    } rounded-[10px] py-3 px-4 font-body text-[1rem] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[rgba(201,75,31,0.4)] focus:bg-[var(--card-bg)] focus:shadow-[0_0_0_3px_rgba(201,75,31,0.08)] transition-all duration-200`;

  return (
    <form onSubmit={handleSubmit} className="space-y-5 p-7">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">✦</span>
        <h2 className="text-[1.2rem] font-display font-medium text-[var(--text-heading)]">
          Your Birth Details
        </h2>
      </div>

      <div>
        <label htmlFor="astro-date" className="block text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--accent)] mb-1.5">
          Birth Date
        </label>
        <input
          id="astro-date"
          type="date"
          className={inputClass('date')}
          value={date}
          onChange={(e) => setDate(e.target.value)}
          disabled={disabled}
          aria-label="Birth date"
          min="1900-01-01"
          max={format(new Date(), 'yyyy-MM-dd')}
        />
        {errors.date && <p className="text-[var(--accent)] text-[0.75rem] mt-1.5 ml-1">{errors.date}</p>}
      </div>

      <div>
        <label htmlFor="astro-time" className="block text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--accent)] mb-1.5">
          Birth Time
        </label>
        <input
          id="astro-time"
          type="text"
          placeholder="e.g. 08:30"
          className={inputClass('time')}
          value={time}
          onChange={(e) => setTime(e.target.value)}
          disabled={disabled || timeUnknown}
          aria-label="Birth time"
        />
        {errors.time && <p className="text-[var(--accent)] text-[0.75rem] mt-1.5 ml-1">{errors.time}</p>}
        <label className="flex items-center gap-2 mt-2.5 cursor-pointer ml-1">
          <input
            type="checkbox"
            checked={timeUnknown}
            onChange={(e) => {
              setTimeUnknown(e.target.checked);
              if (e.target.checked) { setTime(''); setErrors((prev) => { const n = { ...prev }; delete n.time; return n; }); }
            }}
            className="rounded border-[rgba(201,149,43,0.3)] bg-[var(--input-bg)] text-[var(--accent)] focus:ring-[rgba(201,75,31,0.2)]"
          />
          <span className="text-[0.8rem] font-body text-[var(--text-muted)]">Time unknown</span>
        </label>
      </div>

      {/* Decorative divider */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-[rgba(201,149,43,0.3)]" />
        <span className="text-[0.6rem] text-[var(--gold)]">✦</span>
        <div className="flex-1 h-px bg-[rgba(201,149,43,0.3)]" />
      </div>

      <div>
        <label htmlFor="astro-place" className="block text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--accent)] mb-1.5">
          Birth Place
        </label>
        <input
          id="astro-place"
          type="text"
          placeholder="e.g. New York, NY"
          className={inputClass('place')}
          value={place}
          onChange={(e) => setPlace(e.target.value)}
          disabled={disabled}
          aria-label="Birth place"
        />
        {errors.place && <p className="text-[var(--accent)] text-[0.75rem] mt-1.5 ml-1">{errors.place}</p>}
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="w-full py-[13px] rounded-full bg-[var(--accent)] text-white font-label text-[0.8rem] uppercase tracking-[0.2em] hover:bg-[var(--accent-soft)] hover:scale-[1.01] disabled:opacity-40 disabled:scale-100 transition-all duration-150"
      >
        {disabled ? '✦ Please wait...' : 'Reveal My Chart'}
      </button>
    </form>
  );
}
