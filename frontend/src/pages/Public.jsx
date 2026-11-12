import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'
import { Err } from '../ui.jsx'

const FEATS = [['🔬', 'AI Disease Detection', 'Photograph a leaf and get an AI suggestion with a confidence score.'],
  ['🌱', 'Crop Recommendation', 'Pick any point on the map and see crops that suit its climate and soil.'],
  ['⛅', 'Weather Monitoring', '7-day forecast, rain alerts and farm-specific warnings.'],
  ['🛰️', 'Satellite Vegetation', 'Sentinel-2 NDVI trends for your field.'],
  ['📈', 'Yield Prediction', 'Model-based yield estimate versus the regional historical average.'],
  ['💧', 'Water Requirement', 'FAO-56 irrigation estimates from crop, stage and weather.']]

export function Landing() {
  return (
    <div>
      <div className="hero"><div className="container">
        <div className="top"><span className="logo">🌾 Agriculture Threat Fusion</span>
          <div className="row" style={{ flex: '0 0 auto' }}>
            <a href="#about" style={{ color: '#fff' }}>About</a><a href="#features" style={{ color: '#fff' }}>Features</a><a href="#how" style={{ color: '#fff' }}>How it works</a><a href="#contact" style={{ color: '#fff' }}>Contact</a>
            <Link className="btn ghost" to="/auth">Farmer Login</Link><Link className="btn alt" to="/auth?mode=register">Get Started</Link>
          </div></div>
        <div style={{ padding: '14vh 0 12vh', maxWidth: 720 }} className="fade">
          <h1 style={{ fontSize: 'clamp(2rem,5vw,3.4rem)' }}>Smart Farming Starts with Intelligent Threat Detection</h1>
          <p style={{ fontSize: '1.1rem', opacity: .92 }}>Monitor your crops, detect diseases early, understand weather conditions, receive intelligent crop recommendations, and improve your agricultural productivity.</p>
          <Link className="btn alt" to="/auth?mode=register" style={{ marginRight: 10 }}>Get Started — Register</Link><Link className="btn ghost" to="/auth">Farmer Login</Link>
        </div></div></div>
      <div className="container" style={{ padding: '50px 18px' }}>
        <section id="about"><h2>About Us</h2><p>Agriculture Threat Fusion combines your farm details, weather, satellite vegetation and AI to give decision-support estimates. It supports — it does not replace — advice from your local agriculture officer.</p></section>
        <section id="features"><h2>Features</h2><div className="grid g3">{FEATS.map(([i, t, d]) => <div key={t} className="card"><div style={{ fontSize: '2rem' }}>{i}</div><b>{t}</b><p className="mut">{d}</p></div>)}</div></section>
        <section id="how"><h2>How it works</h2><div className="grid g4">{['Create an account', 'Add crop & pick farm on map', 'Get weather, water, NDVI & threat alerts', 'Detect disease, predict yield, find markets'].map((s, i) => <div key={s} className="card"><div className="big-n">{i + 1}</div>{s}</div>)}</div></section>
        <section id="contact"><h2>Contact</h2><p className="mut">Replace this with your support email / helpline.</p></section>
      </div></div>
  )
}

const Pw = ({ value, onChange, label = 'Password', ...p }) => {
  const [s, set] = useState(false)
  return <div><label>{label}</label><div style={{ position: 'relative' }}><input type={s ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)} {...p} />
    <button type="button" onClick={() => set(!s)} style={{ position: 'absolute', right: 8, top: 8, border: 0, background: 'none', cursor: 'pointer' }}>{s ? 'Hide' : 'Show'}</button></div></div>
}

export function Auth() {
  const nav = useNavigate()
  const q = new URLSearchParams(location.search)
  const [mode, setMode] = useState(q.get('mode') === 'register' ? 'register' : 'login') // login|register|otp|forgot|reset|complete
  const [f, setF] = useState({ identifier: '', password: '', remember: true, name: '', phone: '', email: '', confirm: '', terms: false, code: '', newpw: '' })
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [msg, setMsg] = useState(null)
  const [cd, setCd] = useState(0)
  const set = k => v => setF(x => ({ ...x, [k]: v }))
  useEffect(() => { if (cd > 0) { const t = setTimeout(() => setCd(cd - 1), 1000); return () => clearTimeout(t) } }, [cd])
  const run = async fn => { setBusy(true); setErr(null); setMsg(null); try { await fn() } catch (e) { setErr(e) } finally { setBusy(false) } }
  const done = r => { setToken(r.token, f.remember); if (r.needs_profile) { setMode('complete'); setMsg('Add and verify your mobile number to finish setting up.') } else nav('/app') }

  const gref = useRef(null)
  useEffect(() => {
    const cid = import.meta.env.VITE_GOOGLE_CLIENT_ID
    if (!cid || !gref.current || !['login', 'register'].includes(mode)) return
    const s = document.createElement('script'); s.src = 'https://accounts.google.com/gsi/client'; s.async = true
    s.onload = () => { window.google.accounts.id.initialize({ client_id: cid, callback: r => run(async () => done(await api('/auth/google', { method: 'POST', body: { id_token: r.credential } }))) }); window.google.accounts.id.renderButton(gref.current, { theme: 'outline', size: 'large', text: 'continue_with', width: 320 }) }
    document.body.appendChild(s); return () => s.remove()
  }, [mode])

  const doRegister = () => run(async () => {
    if (!f.terms) throw new Error('Please accept the Terms and Conditions.')
    const r = await api('/auth/register', { method: 'POST', body: { name: f.name, phone: f.phone, email: f.email, password: f.password, confirm: f.confirm } })
    if (r.token) { done(r); return }
    setMode('otp'); setCd(30); setMsg('OTP sent to your mobile number.')
  })
  const doLogin = () => run(async () => done(await api('/auth/login', { method: 'POST', body: { identifier: f.identifier, password: f.password, remember: f.remember } })))

  return (
    <div className="split">
      <div className="left"><Link to="/" className="logo">🌾 Agriculture Threat Fusion</Link>
        <h1 style={{ marginTop: 60 }}>Welcome Back, Farmer!</h1>
        <p style={{ opacity: .9 }}>Agriculture Threat Fusion helps you watch your crops, read the weather, and act early on disease, water and yield risks.</p>
        <ul style={{ lineHeight: 2 }}>{['AI Disease Detection', 'Crop Recommendation', 'Weather Monitoring', 'Satellite Vegetation Monitoring', 'Crop Yield Prediction'].map(x => <li key={x}>✅ {x}</li>)}</ul></div>
      <div className="right"><div className="card fade" style={{ width: '100%', maxWidth: 420 }}>
        {['login', 'register'].includes(mode) && <div className="tabs"><button className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr(null) }}>Login</button><button className={mode === 'register' ? 'on' : ''} onClick={() => { setMode('register'); setErr(null) }}>Register</button></div>}
        <Err e={err} />{msg && <div className="ok">{msg}</div>}

        {mode === 'login' && <form onSubmit={e => { e.preventDefault(); doLogin() }}>
          <label>Phone number or Email</label><input value={f.identifier} onChange={e => set('identifier')(e.target.value)} required autoComplete="username" />
          <Pw value={f.password} onChange={set('password')} required autoComplete="current-password" />
          <div className="row" style={{ marginTop: 10 }}><label style={{ display: 'flex', gap: 6, margin: 0 }}><input type="checkbox" style={{ width: 'auto' }} checked={f.remember} onChange={e => set('remember')(e.target.checked)} />Remember me</label><a href="#" style={{ textAlign: 'right' }} onClick={e => { e.preventDefault(); setMode('forgot'); setErr(null) }}>Forgot password?</a></div>
          <button className="btn" style={{ width: '100%', marginTop: 12 }} disabled={busy}>{busy ? 'Signing in…' : 'Login'}</button>
          <div className="mut" style={{ textAlign: 'center', margin: '12px 0' }}>or</div>
          {import.meta.env.VITE_GOOGLE_CLIENT_ID ? <div ref={gref} style={{ display: 'grid', placeItems: 'center' }} /> : <button type="button" className="btn alt" style={{ width: '100%' }} disabled title="Set VITE_GOOGLE_CLIENT_ID">Continue with Google (not configured)</button>}
          <p style={{ textAlign: 'center' }}><a href="#" onClick={e => { e.preventDefault(); setMode('register') }}>Create New Account</a></p></form>}

        {mode === 'register' && <form onSubmit={e => { e.preventDefault(); doRegister() }}>
          <label>Full name</label><input value={f.name} onChange={e => set('name')(e.target.value)} required />
          <label>Mobile number</label><input value={f.phone} onChange={e => set('phone')(e.target.value)} inputMode="tel" placeholder="10-digit number" required />
          <label>Email address</label><input type="email" value={f.email} onChange={e => set('email')(e.target.value)} required />
          <Pw value={f.password} onChange={set('password')} required /><Pw label="Confirm password" value={f.confirm} onChange={set('confirm')} required />
          <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" style={{ width: 'auto' }} checked={f.terms} onChange={e => set('terms')(e.target.checked)} />I accept the Terms and Conditions</label>
          <button className="btn" style={{ width: '100%', marginTop: 8 }} disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button></form>}

        {mode === 'otp' && <form onSubmit={e => { e.preventDefault(); run(async () => done(await api('/auth/verify-otp', { method: 'POST', body: { phone: f.phone, code: f.code } }))) }}>
          <h3>Verify your mobile number</h3><p className="mut">Enter the 6-digit OTP sent to {f.phone}.</p>
          <input value={f.code} onChange={e => set('code')(e.target.value)} inputMode="numeric" maxLength={6} autoFocus required />
          <button className="btn" style={{ width: '100%', marginTop: 10 }} disabled={busy}>Verify & complete registration</button>
          <button type="button" className="btn alt" style={{ width: '100%', marginTop: 8 }} disabled={cd > 0 || busy} onClick={() => run(async () => { await api('/auth/resend-otp', { method: 'POST', body: { phone: f.phone } }); setCd(30); setMsg('New OTP sent.') })}>{cd > 0 ? `Resend OTP in ${cd}s` : 'Resend OTP'}</button></form>}

        {mode === 'forgot' && <div><h3>Forgot password</h3><p className="mut">We will send an OTP to your registered mobile number.</p>
          <label>Phone number or Email</label><input value={f.identifier} onChange={e => set('identifier')(e.target.value)} />
          <button className="btn" style={{ width: '100%', marginTop: 10 }} disabled={busy} onClick={() => run(async () => { await api('/auth/forgot', { method: 'POST', body: { identifier: f.identifier } }); setMode('reset'); setMsg('If the account exists, an OTP has been sent.') })}>Send OTP</button>
          <p><a href="#" onClick={e => { e.preventDefault(); setMode('login') }}>← Back to login</a></p></div>}

        {mode === 'reset' && <form onSubmit={e => { e.preventDefault(); run(async () => { await api('/auth/reset', { method: 'POST', body: { identifier: f.identifier, code: f.code, new_password: f.newpw, confirm: f.confirm } }); setMode('login'); setMsg('Password updated. Please log in.') }) }}>
          <h3>Create a new password</h3><label>OTP</label><input value={f.code} onChange={e => set('code')(e.target.value)} inputMode="numeric" maxLength={6} required />
          <Pw label="New password" value={f.newpw} onChange={set('newpw')} required /><Pw label="Confirm new password" value={f.confirm} onChange={set('confirm')} required />
          <button className="btn" style={{ width: '100%', marginTop: 10 }} disabled={busy}>Save password</button></form>}

        {mode === 'complete' && <div><h3>Complete your profile</h3>
          <label>Mobile number</label><input value={f.phone} onChange={e => set('phone')(e.target.value)} inputMode="tel" />
          <button className="btn alt" style={{ width: '100%', margin: '8px 0' }} disabled={busy} onClick={() => run(async () => { await api('/me/phone/request', { method: 'POST', body: { phone: f.phone } }); setMsg('OTP sent.') })}>Send OTP</button>
          <label>OTP</label><input value={f.code} onChange={e => set('code')(e.target.value)} maxLength={6} />
          <button className="btn" style={{ width: '100%', marginTop: 10 }} disabled={busy} onClick={() => run(async () => { await api('/me/phone/verify', { method: 'POST', body: { phone: f.phone, code: f.code } }); nav('/app') })}>Verify & continue</button></div>}
      </div></div>
    </div>
  )
}
