import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Factory, Loader2 } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errMsg } from '@/lib/api';

export default function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
    <div className="relative flex min-h-screen items-center justify-center bg-background px-4">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: 'radial-gradient(900px 500px at 20% 10%, rgba(46,168,255,0.10), transparent 60%), radial-gradient(700px 420px at 80% 0%, rgba(34,197,94,0.06), transparent 55%)' }}
      />
      <div className="relative w-full max-w-md rounded-xl border border-border bg-[hsl(var(--panel-1))] p-8">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-[hsl(var(--primary))]/30 bg-[rgba(46,168,255,0.10)]">
            <Factory className="h-6 w-6 text-[hsl(var(--primary))]" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">ForgeOps</h1>
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
          {error && <div data-testid="login-error" className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
          <Button type="submit" data-testid="login-submit-button" disabled={loading} className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:bg-[rgba(46,168,255,0.9)]">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Sign in to Control Room'}
          </Button>
        </form>
        <div className="mt-6 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3 text-xs text-muted-foreground">
          <div className="mb-1 font-semibold text-foreground">Default access</div>
          <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
            <span>admin / admin123</span>
            <span>tech / tech123</span>
            <span>operator / operator123</span>
          </div>
        </div>
      </div>
    </div>
  );
}
