import React, { useEffect, useState } from 'react'

export const Spinner = ({ text }) => <div className="empty"><span className="spin" /> {text && <div className="mut">{text}</div>}</div>
export const Err = ({ e }) => e ? <div className="err">{e.message || String(e)}</div> : null
export const Tag = ({ level }) => <span className={'tag ' + level}>{level}</span>
export const Empty = ({ children }) => <div className="empty">{children}</div>
export const Note = ({ children }) => <div className="info">{children}</div>

export function useLoad(fn, deps = []) {
  const [s, set] = useState({ loading: true, data: null, error: null })
  const run = () => { set(x => ({ ...x, loading: true, error: null })); fn().then(data => set({ loading: false, data, error: null })).catch(error => set({ loading: false, data: null, error })) }
  useEffect(run, deps)
  return { ...s, reload: run }
}

// Renders a dashboard section {ok,data|error}
export function Section({ title, res, children, wide }) {
  return (
    <div className="card fade" style={wide ? { gridColumn: '1/-1' } : undefined}>
      <div className="mut" style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '.75rem' }}>{title}</div>
      {!res ? <Spinner /> : res.ok ? children(res.data) : <div className="mut" style={{ marginTop: 8 }}>Unavailable: {res.error}</div>}
    </div>
  )
}
export const fmt = (v, u = '') => (v === null || v === undefined ? '—' : v + u)
export const Field = ({ label, children }) => <div><label>{label}</label>{children}</div>
