import React, { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';

function pad(n) { return String(n).padStart(2, '0'); }

const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

// Live wall-clock time display — used to cross-reference breakdown reports & timeline events
export function PlantClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(tick);
  }, []);

  return (
    <div data-testid="plant-time-clock" className="cyber-panel cyber-glow flex items-center gap-3 px-4 py-2.5">
      <Clock className="h-4 w-4 text-[hsl(var(--primary))]" />
      <div>
        <div className="text-[9px] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
          Plant Time · {DAYS[now.getDay()]} {pad(now.getDate())} {MONTHS[now.getMonth()]} {now.getFullYear()}
        </div>
        <div data-testid="plant-time-value" className="font-mono text-lg leading-tight tabular-nums text-[hsl(var(--primary))]" style={{ textShadow: '0 0 10px rgba(var(--accent-rgb),0.45)' }}>
          {pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}
        </div>
      </div>
    </div>
  );
}
