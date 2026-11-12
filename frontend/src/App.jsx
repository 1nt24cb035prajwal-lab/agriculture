import React, { createContext, useContext, useEffect, useState } from 'react'
import { Routes, Route, Navigate, NavLink, Outlet, Link, useNavigate } from 'react-router-dom'
import { api, getToken, clearToken } from './api'
import { LANGS, tr } from './i18n'
import { Landing, Auth } from './pages/Public.jsx'
import { Dashboard, CropLand, Recommend } from './pages/Main.jsx'
import { Disease, Yield, Weather, Satellite, History, Reports, Profile, Admin } from './pages/More.jsx'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

function Protected() {
  const nav = useNavigate()
  const [me, setMe] = useState(null)
  const [farms, setFarms] = useState(null)
  const [fid, setFid] = useState(null)
  const [notifs, setNotifs] = useState([])
  const [open, setOpen] = useState(false)
  const loadFarms = () => api('/farms').then(f => { setFarms(f); setFid(id => id ?? f[0]?.id ?? null) })
  useEffect(() => {
    if (!getToken()) return nav('/auth')
    api('/me').then(setMe).catch(() => nav('/auth'))
    loadFarms().catch(() => {})
    api('/notifications').then(setNotifs).catch(() => {})
  }, [])
  if (!me) return <div className="bg"><div className="empty"><span className="spin" /></div></div>
  const lang = me.language || 'en'
  const t = k => tr(lang, k)
  const farm = farms?.find(f => f.id === fid) || null
  const setLang = async l => setMe(await api('/me', { method: 'PUT', body: { language: l } }))
  const unread = notifs.filter(n => !n.read).length
  const links = [['/app', 'dashboard'], ['/app/land', 'land'], ['/app/recommend', 'recommend'], ['/app/disease', 'disease'], ['/app/yield', 'yield'],
    ['/app/weather', 'weather'], ['/app/satellite', 'satellite'], ['/app/history', 'history'], ['/app/reports', 'reports']]
  return (
    <Ctx.Provider value={{ me, setMe, farms, farm, fid, setFid, loadFarms, t, notifs, setNotifs }}>
      <div className="bg">
        <div className="hdr"><div className="container">
          <div className="top">
            <Link to="/app" className="logo">🌾 Agriculture Threat Fusion</Link>
            <div className="mut">{t('welcome')}, <b>{me.name}</b> · {new Date().toLocaleDateString(undefined, { dateStyle: 'long' })}</div>
            <div className="row" style={{ flex: '0 0 auto', gap: 8, flexWrap: 'nowrap' }}>
              {farms?.length > 1 && <select style={{ width: 150 }} value={fid ?? ''} onChange={e => setFid(+e.target.value)}>{farms.map(f => <option key={f.id} value={f.id}>{f.name} {f.crop ? `(${f.crop})` : ''}</option>)}</select>}
              <select style={{ width: 110 }} value={lang} onChange={e => setLang(e.target.value)}>{Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
              <button className="avatar" title="Notifications" onClick={() => { setOpen(!open); if (unread) api('/notifications/read', { method: 'POST' }).then(() => setNotifs(n => n.map(x => ({ ...x, read: true })))) }}>🔔{unread > 0 && <sup>{unread}</sup>}</button>
              <Link to="/app/profile" className="avatar" title="Profile" style={{ textDecoration: 'none' }}>{me.name.split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()}</Link>
            </div>
          </div>
          <div className="nav">
            {links.map(([to, k]) => <NavLink key={to} to={to} end={to === '/app'} className={({ isActive }) => isActive ? 'active' : ''}>{t(k)}</NavLink>)}
            {me.role === 'admin' && <NavLink to="/app/admin">Admin</NavLink>}
          </div>
        </div></div>
        {open && <div className="container"><div className="card" style={{ margin: '10px 0' }}>
          <b>Notifications</b>
          {notifs.length === 0 ? <div className="mut">No notifications yet.</div> : notifs.slice(0, 10).map(n => <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--line)' }}><span className={'tag ' + n.level}>{n.level}</span> <b>{n.title}</b><div className="mut">{n.body} · {new Date(n.created).toLocaleString()}</div></div>)}
        </div></div>}
        <div className="container" style={{ padding: '16px 18px 60px' }}><Outlet /></div>
      </div>
    </Ctx.Provider>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/app" element={<Protected />}>
        <Route index element={<Dashboard />} />
        <Route path="land" element={<CropLand />} />
        <Route path="recommend" element={<Recommend />} />
        <Route path="disease" element={<Disease />} />
        <Route path="yield" element={<Yield />} />
        <Route path="weather" element={<Weather />} />
        <Route path="satellite" element={<Satellite />} />
        <Route path="history" element={<History />} />
        <Route path="reports" element={<Reports />} />
        <Route path="profile" element={<Profile />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}
