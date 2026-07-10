import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Factory, Loader2, AlertTriangle } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errMsg } from '@/lib/api';
import { CrackedGear } from '@/components/StatusBits';
import { ReportBreakdownDialog } from '@/components/ReportBreakdownDialog';

export default function Login() {
  const { login, branding } = useApp();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [warningOpen, setWarningOpen] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: 'radial-gradient(900px 500px at 20% 10%, rgba(var(--accent-rgb),0.08), transparent 60%), radial-gradient(700px 420px at 80% 0%, rgba(255,46,99,0.05), transparent 55%)' }}
      />
      <div className="login-grid" aria-hidden="true" />
      <div className="relative w-full max-w-md border border-border bg-[hsl(var(--panel-1))]/90 p-8 backdrop-blur-md" style={{ boxShadow: '0 0 0 1px rgba(var(--accent-rgb),0.1), 0 0 60px rgba(var(--accent-rgb),0.06), 0 30px 80px rgba(0,0,0,0.85)' }}>
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-[hsl(var(--primary))]/30 bg-[hsl(var(--primary))]/10">
            {branding?.logo_data ? (
              <img src={branding.logo_data} alt="logo" className="h-8 w-8 object-contain" />
            ) : (
              <Factory className="h-6 w-6 text-[hsl(var(--primary))]" />
            )}
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{branding?.app_name || 'ForgeOps'}</h1>
            <p className="text-xs uppercase tracking-widest text-muted-foreground">Factory Operations Platform</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="username">Username</Label>
            <Input id="username" data-testid="login-username-input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" autoComplete="username" required className="bg-[hsl(var(--panel-2))]" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" required className="bg-[hsl(var(--panel-2))]" />
          </div>
          {error && <div data-testid="login-error" className="rounded-md border border-[#ff2e63]/40 bg-[#ff2e63]/10 px-3 py-2 text-sm text-[#ff2e63]">{error}</div>}
          <Button type="submit" data-testid="login-submit-button" disabled={loading} className="w-full">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Sign in to Control Room'}
          </Button>
        </form>
        {/* Public kiosk reporting — no login required */}
        <div className="mt-4 border border-[#ff2e63]/30 p-3" data-testid="public-report-section">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-foreground">Machine issue? No login needed.</div>
              <div className="text-[11px] text-muted-foreground">Breakdown = machine down · Warning = concern, still running</div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" data-testid="public-report-breakdown-button" onClick={() => setReportOpen(true)}
                className="border border-[#ff2e63]/60 bg-transparent text-[#ff2e63] hover:bg-[#ff2e63]/10">
                <CrackedGear className="mr-1 h-4 w-4" /> Breakdown
              </Button>
              <Button type="button" data-testid="public-report-warning-button" onClick={() => setWarningOpen(true)}
                className="border border-[#f9f871]/60 bg-transparent text-[#f9f871] hover:bg-[#f9f871]/10">
                <AlertTriangle className="mr-1 h-4 w-4" /> Warning
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3 text-xs text-muted-foreground">
          <div className="mb-1 font-semibold text-foreground">Default access</div>
          <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
            <span>admin / admin123</span>
            <span>tech / tech123</span>
            <span>operator / operator123</span>
          </div>
        </div>
      </div>

      <ReportBreakdownDialog open={reportOpen} setOpen={setReportOpen} publicMode />
      <ReportBreakdownDialog open={warningOpen} setOpen={setWarningOpen} publicMode mode="warning" />
    </div>
  );
}
