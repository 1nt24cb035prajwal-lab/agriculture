import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Legend } from 'recharts'
import { api, blobUrl, download, clearToken } from '../api'
import { useApp } from '../App.jsx'
import { Spinner, Err, Tag, Empty, Note, fmt, useLoad, Field } from '../ui.jsx'

const NoFarm = ({ need = 'location' }) => <div className="card"><Empty>Save your crop and land information{need === 'location' ? ' and farm location' : ''} first. <Link to="/app/land">Open Crop and Land Information</Link></Empty></div>
const Unavail = ({ e }) => e ? <div className="info">{e.notConfigured ? '⚙️ Not configured yet: ' : 'Unavailable: '}{e.message}</div> : null

// ---------------------------------------------------------------- Disease
export function Disease() {
  const { farm } = useApp()
  const { data: ref } = useLoad(() => api('/crops'))
  const { data: cfg } = useLoad(() => api('/config'))
  const hist = useLoad(() => api('/history?kind=disease'))
  const [file, setFile] = useState(null); const [prev, setPrev] = useState(null)
  const [crop, setCrop] = useState(farm?.crop || ''); const [v, setV] = useState({ variety: '', stage: '', symptoms: '', observed: new Date().toISOString().slice(0, 10) })
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [r, setR] = useState(null)
  const [cam, setCam] = useState(false); const vid = useRef(null); const stream = useRef(null)
  useEffect(() => { if (farm?.crop && !crop) setCrop(farm.crop) }, [farm])
  const choose = f => { setFile(f); setR(null); setPrev(f ? URL.createObjectURL(f) : null) }
  const openCam = async () => { try { stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }); setCam(true); setTimeout(() => { vid.current.srcObject = stream.current }, 50) } catch { setErr(new Error('Camera not available or permission denied. Use upload instead.')) } }
  const closeCam = () => { stream.current?.getTracks().forEach(t => t.stop()); setCam(false) }
  const snap = () => { const c = document.createElement('canvas'); c.width = vid.current.videoWidth; c.height = vid.current.videoHeight; c.getContext('2d').drawImage(vid.current, 0, 0); c.toBlob(b => { choose(new File([b], 'capture.jpg', { type: 'image/jpeg' })); closeCam() }, 'image/jpeg', .92) }
  const run = async () => {
    setErr(null); setR(null)
    if (!file) return setErr(new Error('Add a photo first.')); if (!crop.trim()) return setErr(new Error('Select the crop.'))
    setBusy(true)
    try { const fd = new FormData(); fd.append('file', file); fd.append('crop', crop); Object.entries(v).forEach(([k, x]) => fd.append(k, x)); if (farm) fd.append('farm_id', farm.id); setR(await api('/disease', { method: 'POST', form: fd })); hist.reload() }
    catch (e) { setErr(e) } setBusy(false)
  }
  return (
    <div className="fade"><h2>Disease Detection</h2>
      <div className="grid g2">
        <div className="card"><h3>1. Photo</h3>
          <div className="row"><button className="btn" onClick={openCam}>📷 Open Camera</button>
            <label className="btn alt" style={{ textAlign: 'center', margin: 0 }}>🖼️ Gallery<input hidden type="file" accept="image/*" onChange={e => choose(e.target.files[0])} /></label>
            <label className="btn alt" style={{ textAlign: 'center', margin: 0 }}>📁 Files<input hidden type="file" accept="image/*,.jpg,.jpeg,.png,.webp" onChange={e => choose(e.target.files[0])} /></label></div>
          {cam && <div style={{ marginTop: 10 }}><video ref={vid} autoPlay playsInline style={{ width: '100%', borderRadius: 12 }} /><div className="row"><button className="btn" onClick={snap}>Capture Live Photo</button><button className="btn alt" onClick={closeCam}>Cancel</button></div></div>}
          {prev && <div style={{ marginTop: 10 }}><img src={prev} alt="preview" style={{ width: '100%', borderRadius: 12 }} /><div className="row"><button className="btn alt" onClick={openCam}>Retake</button><button className="btn alt" onClick={() => choose(null)}>Remove</button></div></div>}
          <div className="mut" style={{ marginTop: 8 }}>Tip: one affected leaf, close-up, daylight, plain background.</div></div>
        <div className="card"><h3>2. Details</h3>
          <Field label="Crop"><input list="dcrops" value={crop} onChange={e => setCrop(e.target.value)} /></Field><datalist id="dcrops">{ref?.crops.map(c => <option key={c.name} value={c.name} />)}</datalist>
          <div className="row"><Field label="Variety"><input value={v.variety} onChange={e => setV({ ...v, variety: e.target.value })} /></Field><Field label="Growth stage"><select value={v.stage} onChange={e => setV({ ...v, stage: e.target.value })}><option value="">Select…</option>{ref?.stages.map(x => <option key={x}>{x}</option>)}</select></Field></div>
          <Field label="Symptoms observed"><textarea rows={2} value={v.symptoms} onChange={e => setV({ ...v, symptoms: e.target.value })} /></Field>
          <Field label="Date of observation"><input type="date" value={v.observed} onChange={e => setV({ ...v, observed: e.target.value })} /></Field>
          <button className="btn" style={{ width: '100%', marginTop: 10 }} disabled={busy} onClick={run}>{busy ? 'Analysing…' : 'Analyse image'}</button></div>
      </div>
      <Err e={err} />{err?.notConfigured && <Note>Train the model first: see README → “Train the disease model”.</Note>}
      {r && <div className="card fade" style={{ marginTop: 14 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}><h3>{r.healthy ? 'Plant looks healthy' : r.disease}</h3><span className="big-n">{Math.round(r.confidence * 100)}%</span></div>
        <div className="mut">Crop detected: {r.crop_detected} · Category: {r.category}</div>
        <div className={r.confident ? 'ok' : 'err'}>{r.message}</div>
        <div className="mut">Severity: {r.severity}</div>
        <div className="mut">Other possibilities: {r.top3.slice(1).map(t => `${t.label} (${Math.round(t.confidence * 100)}%)`).join(', ')}</div>
        {r.confident && r.advice && <><h4>Prevention</h4><p>{r.advice.prevention}</p><h4>Organic options</h4><p>{r.advice.organic}</p><h4>Chemical options</h4><p>{r.advice.chemical}</p>
          {r.advice.nutrient_note && <><h4>Nutrients</h4><p>{r.advice.nutrient_note}</p></>}<h4>Follow-up</h4><p>{r.advice.follow_up}</p>
          <a className="btn" href={r.supplier_url} target="_blank" rel="noreferrer">Find Fertilizer Suppliers</a><div className="mut" style={{ marginTop: 6 }}>{r.supplier_note}</div></>}
      </div>}
      <h3 style={{ marginTop: 22 }}>Disease history</h3>
      {hist.loading ? <Spinner /> : !hist.data?.length ? <div className="card"><Empty>No detections yet.</Empty></div> : <div className="grid g3">{hist.data.map(h => <HistCard key={h.id} h={h} />)}</div>}
    </div>
  )
}
function HistCard({ h }) {
  const [src, setSrc] = useState(null); const [d, setD] = useState(null)
  useEffect(() => { blobUrl('/files/' + h.id).then(setSrc).catch(() => {}); api('/history/' + h.id).then(setD).catch(() => {}) }, [h.id])
  return <div className="card">{src && <img src={src} alt="" style={{ width: '100%', height: 150, objectFit: 'cover', borderRadius: 10 }} />}<b>{h.title}</b>
    <div className="mut">{new Date(h.created).toLocaleString()}</div>{d?.data?.result && <div className="mut">Confidence {Math.round(d.data.result.confidence * 100)}%</div>}</div>
}

// ---------------------------------------------------------------- Yield
export function Yield() {
  const { farm } = useApp()
  const [r, setR] = useState(null); const [err, setErr] = useState(null); const [busy, setBusy] = useState(false)
  const [mk, setMk] = useState(null); const [mkErr, setMkErr] = useState(null); const [pr, setPr] = useState(null); const [prErr, setPrErr] = useState(null); const [selM, setSelM] = useState(null)
  const go = async () => { setBusy(true); setErr(null); try { setR(await api('/yield', { method: 'POST', body: { farm_id: farm.id } })) } catch (e) { setErr(e) } setBusy(false) }
  useEffect(() => { if (farm?.crop) { api(`/prices?crop=${encodeURIComponent(farm.crop)}&state=${encodeURIComponent(farm.state || '')}`).then(setPr).catch(setPrErr) } }, [farm?.id])
  const markets = async () => { setMkErr(null); try { setMk(await api(`/farms/${farm.id}/markets`)) } catch (e) { setMkErr(e) } }
  if (!farm) return <NoFarm />
  return (
    <div className="fade"><h2>Crop Yield Prediction</h2>
      <div className="card"><div className="grid g3">{[['Crop', farm.crop], ['Area', farm.area && `${farm.area} ${farm.unit}`], ['Season', farm.season], ['Soil', farm.soil], ['Irrigation', farm.irrigation], ['State / District', [farm.state, farm.district].filter(Boolean).join(' / ')]].map(([k, x]) => <div key={k}><div className="mut">{k}</div><b>{x || '—'}</b></div>)}</div>
        <div className="mut" style={{ marginTop: 6 }}>Using your saved details. <Link to="/app/land">Edit</Link></div>
        <button className="btn" style={{ marginTop: 10 }} disabled={busy} onClick={go}>{busy ? 'Predicting…' : 'Predict yield'}</button></div>
      <Unavail e={err} />
      {r && <div className="card fade" style={{ marginTop: 14 }}>
        <div className="grid g3"><div><div className="mut">Expected yield / acre</div><div className="big-n">{r.yield_t_per_acre} t</div></div>
          <div><div className="mut">Expected total</div><div className="big-n">{r.total_tonnes} t</div></div>
          <div><div className="mut">Likely range / acre</div><div className="big-n" style={{ fontSize: '1.4rem' }}>{r.range_t_per_acre[0]}–{r.range_t_per_acre[1]} t</div></div></div>
        <div className="mut">{r.source_label} · Harvest: {r.harvest_date || 'enter start date'} · Season used: {r.season_used}</div>
        {r.regional_avg ? <><h4>Compared with regional average</h4><div style={{ height: 220 }}><ResponsiveContainer><BarChart data={[{ n: 'Your predicted', v: r.yield_t_per_acre }, { n: r.regional_avg.label, v: r.regional_avg.t_per_acre }]}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="n" /><YAxis unit=" t" /><Tooltip /><Bar dataKey="v" fill="#16a34a" /></BarChart></ResponsiveContainer></div>
          <div>{r.diff_pct > 0 ? '▲' : '▼'} {Math.abs(r.diff_pct)}% {r.diff_pct > 0 ? 'above' : 'below'} the {r.regional_avg.level}-level average ({r.regional_avg.t_per_acre} t/acre).</div>
          {!r.district_matched && <div className="mut">District not found in the dataset - a broader average is shown.</div>}</> : <div className="mut">No regional average available for this crop in the dataset.</div>}
        {r.qualitative_factors.length > 0 && <><h4>Factors (qualitative — not numerically in the model)</h4>{r.qualitative_factors.map((f, i) => <div key={i}>{f.effect === 'reducing' ? '🔻' : '🔺'} {f.text}</div>)}</>}
        {r.model_quality && <div className="mut" style={{ marginTop: 8 }}>Model hold-out R² = {r.model_quality.holdout_r2}, MAE = {r.model_quality.holdout_mae_t_per_ha} t/ha.</div>}
        <Note>{r.disclaimer}</Note></div>}
      <div className="card" style={{ marginTop: 14 }}><h3>Live crop market prices</h3>
        <Unavail e={prErr} />{!pr && !prErr && <Spinner />}
        {pr && (pr.rows.length ? <><table><thead><tr><th>Market</th><th>District</th><th>Min</th><th>Max</th><th>Modal</th><th>Date</th></tr></thead><tbody>{pr.rows.slice(0, 15).map((x, i) => <tr key={i}><td>{x.market}</td><td>{x.district}</td><td>{x.min}</td><td>{x.max}</td><td><b>{x.modal}</b></td><td>{x.date}</td></tr>)}</tbody></table>
          <div className="mut">{pr.unit} · {pr.source} · fetched {pr.fetched_at}. {pr.note}</div></> : <Empty>No price records for this crop/state.</Empty>)}</div>
      <div className="card" style={{ marginTop: 14 }}><h3>Nearby agricultural markets</h3>
        <button className="btn" onClick={markets}>Find Nearby Markets</button><Unavail e={mkErr} />
        {mk && <><div className="mut">{mk.source}</div>{mk.markets.length === 0 ? <Empty>No mapped markets within 50 km.</Empty> : <>
          <div style={{ height: 340, marginTop: 10 }}><MapContainer center={[farm.lat, farm.lon]} zoom={9} style={{ height: '100%', borderRadius: 12 }}><TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
            <Marker position={[farm.lat, farm.lon]}><Popup>Your farm</Popup></Marker>{mk.markets.map((m, i) => <Marker key={i} position={[m.lat, m.lon]} eventHandlers={{ click: () => setSelM(m) }}><Popup>{m.name}<br />{m.distance_km} km</Popup></Marker>)}</MapContainer></div>
          <table><thead><tr><th>Market</th><th>Address</th><th>Distance</th></tr></thead><tbody>{mk.markets.map((m, i) => <tr key={i} onClick={() => setSelM(m)} style={{ cursor: 'pointer', background: selM === m ? '#dcfce7' : undefined }}><td>{m.name}</td><td>{m.address}</td><td>{m.distance_km} km</td></tr>)}</tbody></table></>}</>}</div>
    </div>
  )
}

// ---------------------------------------------------------------- Weather
export function Weather() {
  const { farm } = useApp()
  const { loading, data: w, error } = useLoad(() => farm?.lat ? api(`/weather?lat=${farm.lat}&lon=${farm.lon}`) : Promise.resolve(null), [farm?.id])
  if (!farm?.lat) return <NoFarm />
  if (loading) return <Spinner />
  if (error) return <Unavail e={error} />
  const rows = [...w.history.map(r => ({ ...r, past: true })), ...w.forecast]
  return (
    <div className="fade"><h2>Weather Monitoring</h2>
      <div className="grid g4">{[['Temperature', fmt(w.current.temp, '°C')], ['Humidity', fmt(w.current.humidity, '%')], ['Rainfall now', fmt(w.current.rain, ' mm')], ['Wind', fmt(w.current.wind, ' km/h')], ['Cloud cover', fmt(w.current.cloud, '%')], ['Condition', w.current.text]].map(([k, x]) => <div className="card" key={k}><div className="mut">{k}</div><div className="big-n" style={{ fontSize: '1.5rem' }}>{x}</div></div>)}</div>
      <div className="card" style={{ marginTop: 14 }}><h3>Agriculture alerts</h3>{w.alerts.length ? w.alerts.map((a, i) => <div key={i} style={{ margin: '6px 0' }}><Tag level={a.level} /> <b>{a.title}</b> <span className="mut">{a.message}</span></div>) : 'No alerts for the next 7 days.'}</div>
      <div className="card" style={{ marginTop: 14 }}><h3>Past 7 days and next 7 days</h3><div style={{ height: 280 }}><ResponsiveContainer><LineChart data={rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={x => x.slice(5)} /><YAxis yAxisId="a" unit="°" /><YAxis yAxisId="b" orientation="right" unit="mm" /><Tooltip /><Legend />
        <Line yAxisId="a" dataKey="tmax" name="Max °C" stroke="#dc2626" /><Line yAxisId="a" dataKey="tmin" name="Min °C" stroke="#2563eb" /><Line yAxisId="b" dataKey="rain" name="Rain mm" stroke="#16a34a" /></LineChart></ResponsiveContainer></div></div>
      <div className="card" style={{ marginTop: 14 }}><table><thead><tr><th>Date</th><th>Min–Max °C</th><th>Rain mm</th><th>Rain chance</th><th>Wind max</th></tr></thead><tbody>{w.forecast.map(r => <tr key={r.date}><td>{r.date}</td><td>{r.tmin}–{r.tmax}</td><td>{r.rain}</td><td>{fmt(r.rain_prob, '%')}</td><td>{fmt(r.wind_max, ' km/h')}</td></tr>)}</tbody></table><div className="mut">Source: {w.source} · {w.fetched_at}</div></div>
    </div>
  )
}

// ---------------------------------------------------------------- Satellite
export function Satellite() {
  const { farm } = useApp()
  const { loading, data: s, error } = useLoad(() => farm?.lat ? api(`/farms/${farm.id}/satellite`) : Promise.resolve(null), [farm?.id])
  const [a, setA] = useState(null); const [b, setB] = useState(null)
  const th = useLoad(() => farm?.lat ? api(`/farms/${farm.id}/threats`) : Promise.resolve({ threats: [] }), [farm?.id])
  if (!farm?.lat) return <NoFarm />
  return (
    <div className="fade"><h2>Satellite Vegetation Monitoring</h2>
      {loading ? <Spinner text="Querying Sentinel-2…" /> : error ? <Unavail e={error} /> : !s.series.length ? <div className="card"><Empty>{s.limitation}</Empty></div> :
        <div className="card"><div className="row" style={{ justifyContent: 'space-between' }}><div><div className="mut">Latest NDVI ({s.latest.from} → {s.latest.to})</div><span className="big-n">{s.latest.ndvi}</span> <span className={'tag ' + s.latest.class}>{s.latest.class}</span></div></div>
          <div style={{ height: 260 }}><ResponsiveContainer><LineChart data={s.series}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="from" tickFormatter={x => x.slice(5)} /><YAxis domain={[0, 1]} /><Tooltip /><Line dataKey="ndvi" stroke="#16a34a" strokeWidth={2} /></LineChart></ResponsiveContainer></div>
          <h4>Compare two dates</h4><div className="row"><select value={a ?? ''} onChange={e => setA(+e.target.value)}><option value="">First period</option>{s.series.map((x, i) => <option key={i} value={i}>{x.from}</option>)}</select>
            <select value={b ?? ''} onChange={e => setB(+e.target.value)}><option value="">Second period</option>{s.series.map((x, i) => <option key={i} value={i}>{x.from}</option>)}</select></div>
          {a !== null && b !== null && a !== '' && b !== '' && <div style={{ marginTop: 8 }}>{s.series[a].ndvi} ({s.series[a].class}) → {s.series[b].ndvi} ({s.series[b].class}): change {(s.series[b].ndvi - s.series[a].ndvi).toFixed(3)}</div>}
          <div className="mut" style={{ marginTop: 8 }}>{s.source}. {s.note}</div></div>}
      <div className="card" style={{ marginTop: 14 }}><h3>Agricultural threat fusion</h3>
        {th.loading ? <Spinner /> : th.error ? <Unavail e={th.error} /> : th.data.threats.length === 0 ? <div>No active threats from available data.</div> :
          th.data.threats.map((x, i) => <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--line)' }}><Tag level={x.level} /> <b>{x.threat}</b> <span className="mut">· {x.crop} · {x.stage || 'stage not set'} · {x.source}</span>
            <div>{x.evidence}</div><div className="mut">Impact: {x.impact}. Prevention: {x.prevention}. <b>Action:</b> {x.action}</div></div>)}
        {th.data?.satellite_note && <div className="mut">Satellite data not included: {th.data.satellite_note}</div>}<div className="mut" style={{ marginTop: 6 }}>Decision-support estimates, not guaranteed outcomes.</div></div>
    </div>
  )
}

// ---------------------------------------------------------------- History / Reports
const KINDS = ['crop', 'analysis', 'recommendation', 'disease', 'water', 'satellite', 'yield', 'price', 'threat']
export function History() {
  const [f, setF] = useState({ kind: '', crop: '', start: '', end: '' }); const [open, setOpen] = useState(null)
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString()
  const { loading, data, error } = useLoad(() => api('/history?' + qs), [qs])
  const show = async id => setOpen(await api('/history/' + id))
  return (
    <div className="fade"><h2>Activity History</h2>
      <div className="card"><div className="row"><Field label="Type"><select value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}><option value="">All</option>{KINDS.map(k => <option key={k}>{k}</option>)}</select></Field>
        <Field label="Crop"><input value={f.crop} onChange={e => setF({ ...f, crop: e.target.value })} /></Field><Field label="From"><input type="date" value={f.start} onChange={e => setF({ ...f, start: e.target.value })} /></Field><Field label="To"><input type="date" value={f.end} onChange={e => setF({ ...f, end: e.target.value })} /></Field></div></div>
      <Err e={error} />{loading ? <Spinner /> : !data?.length ? <div className="card" style={{ marginTop: 14 }}><Empty>No records match.</Empty></div> :
        <div className="card" style={{ marginTop: 14 }}><table><thead><tr><th>Date</th><th>Type</th><th>Crop</th><th>Details</th><th /></tr></thead><tbody>{data.map(r => <tr key={r.id}><td>{new Date(r.created).toLocaleDateString()}</td><td>{r.kind}</td><td>{r.crop || '—'}</td><td>{r.title}</td><td><button className="btn alt" onClick={() => show(r.id)}>Open</button></td></tr>)}</tbody></table></div>}
      {open && <div className="full" style={{ background: 'rgba(0,0,0,.4)', alignItems: 'center', justifyContent: 'center' }}><div className="card" style={{ maxWidth: 700, maxHeight: '85vh', overflow: 'auto', width: '92%' }}><h3>{open.title}</h3><div className="mut">{new Date(open.created).toLocaleString()}</div>
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '.8rem' }}>{JSON.stringify(open.data, null, 2)}</pre><button className="btn" onClick={() => setOpen(null)}>Close</button></div></div>}
    </div>
  )
}

export function Reports() {
  const [busy, setBusy] = useState(null); const [err, setErr] = useState(null)
  const R = [['crop', 'Crop & land reports'], ['analysis', 'Crop health / analysis reports'], ['disease', 'Disease reports'], ['recommendation', 'Crop recommendation reports'], ['satellite', 'Satellite vegetation reports'], ['yield', 'Yield prediction reports'], ['threat', 'Agricultural threat reports'], ['price', 'Market price reports']]
  const get = async k => { setBusy(k); setErr(null); try { await download('/reports/pdf?kind=' + k, k + '-report.pdf') } catch (e) { setErr(e) } setBusy(null) }
  return <div className="fade"><h2>Reports</h2><Err e={err} /><div className="grid g3">{R.map(([k, l]) => <div className="card" key={k}><b>{l}</b><div className="mut">PDF of your saved records</div><button className="btn" style={{ marginTop: 10 }} disabled={busy === k} onClick={() => get(k)}>{busy === k ? 'Preparing…' : '⬇ Download PDF'}</button></div>)}</div></div>
}

// ---------------------------------------------------------------- Profile
export function Profile() {
  const { me, setMe, farm } = useApp(); const nav = useNavigate()
  const [f, setF] = useState({ name: me.name, email: me.email || '', state: me.state || '', district: me.district || '', taluk: me.taluk || '', village: me.village || '' })
  const [pw, setPw] = useState({ old: '', new: '' }); const [ph, setPh] = useState({ phone: '', code: '', sent: false }); const [msg, setMsg] = useState(null); const [err, setErr] = useState(null)
  const run = fn => async () => { setErr(null); setMsg(null); try { await fn() } catch (e) { setErr(e) } }
  return (
    <div className="fade"><h2>Profile</h2><Err e={err} />{msg && <div className="ok">{msg}</div>}
      <div className="grid g2"><div className="card"><h3>Farmer details</h3><div className="mut">Farmer ID: {me.farmer_code} · Mobile: {me.phone || '—'} · Sign-in: {me.auth_provider}</div>
        {[['name', 'Full name'], ['email', 'Email'], ['state', 'State'], ['district', 'District'], ['taluk', 'Taluk'], ['village', 'Village']].map(([k, l]) => <Field key={k} label={l}><input value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></Field>)}
        {farm && <div className="mut" style={{ marginTop: 8 }}>Current farm: {farm.name} · {farm.crop || 'no crop'} · {farm.area} {farm.unit} · <Link to="/app/land">edit / update location</Link></div>}
        <button className="btn" style={{ marginTop: 10 }} onClick={run(async () => { setMe(await api('/me', { method: 'PUT', body: f })); setMsg('Profile updated.') })}>Save profile</button></div>
        <div><div className="card"><h3>Change password</h3>{me.auth_provider === 'local' && <Field label="Current password"><input type="password" value={pw.old} onChange={e => setPw({ ...pw, old: e.target.value })} /></Field>}<Field label="New password"><input type="password" value={pw.new} onChange={e => setPw({ ...pw, new: e.target.value })} /></Field>
          <button className="btn" style={{ marginTop: 10 }} onClick={run(async () => { await api('/me/password', { method: 'POST', body: pw }); setPw({ old: '', new: '' }); setMsg('Password changed.') })}>Update password</button></div>
          <div className="card" style={{ marginTop: 14 }}><h3>Update mobile number (OTP)</h3><Field label="New mobile number"><input value={ph.phone} onChange={e => setPh({ ...ph, phone: e.target.value })} /></Field>
            <button className="btn alt" onClick={run(async () => { await api('/me/phone/request', { method: 'POST', body: { phone: ph.phone } }); setPh({ ...ph, sent: true }); setMsg('OTP sent.') })}>Send OTP</button>
            {ph.sent && <><Field label="OTP"><input value={ph.code} onChange={e => setPh({ ...ph, code: e.target.value })} /></Field><button className="btn" style={{ marginTop: 8 }} onClick={run(async () => { setMe(await api('/me/phone/verify', { method: 'POST', body: { phone: ph.phone, code: ph.code } })); setPh({ phone: '', code: '', sent: false }); setMsg('Mobile number updated.') })}>Verify</button></>}</div>
          <button className="btn alt" style={{ marginTop: 14 }} onClick={() => { clearToken(); nav('/') }}>Logout</button></div></div>
    </div>
  )
}

// ---------------------------------------------------------------- Admin
export function Admin() {
  const { me } = useApp()
  const s = useLoad(() => api('/admin/stats')); const fr = useLoad(() => api('/admin/farmers')); const ac = useLoad(() => api('/admin/activity')); const it = useLoad(() => api('/admin/integrations'))
  if (me.role !== 'admin') return <Empty>Admin access required.</Empty>
  return (
    <div className="fade"><h2>Admin dashboard</h2>
      <div className="grid g3"><div className="card"><div className="mut">Registered farmers</div><div className="big-n">{s.data?.farmers ?? '…'}</div></div><div className="card"><div className="mut">Farms</div><div className="big-n">{s.data?.farms ?? '…'}</div></div>
        <div className="card"><div className="mut">AI / prediction activity</div>{s.data && Object.entries(s.data.records_by_kind).map(([k, v]) => <div key={k}>{k}: <b>{v}</b></div>)}</div></div>
      <div className="card" style={{ marginTop: 14 }}><h3>Integrations</h3><div className="mut">Keys are set in backend/.env (never in the browser).</div>{it.data && Object.entries(it.data).map(([k, v]) => <div key={k}>{v ? '✅' : '⚠️'} {k.replace('_', ' ')}</div>)}</div>
      <div className="card" style={{ marginTop: 14 }}><h3>Model quality</h3><pre style={{ fontSize: '.8rem' }}>{JSON.stringify(s.data?.models, null, 2)}</pre></div>
      <div className="card" style={{ marginTop: 14 }}><h3>Farmers</h3><table><thead><tr><th>ID</th><th>Name</th><th>Phone</th><th>Email</th><th>Active</th><th /></tr></thead><tbody>{fr.data?.map(f => <tr key={f.id}><td>{f.farmer_code}</td><td>{f.name}</td><td>{f.phone}</td><td>{f.email}</td><td>{f.is_active ? 'Yes' : 'No'}</td><td>{f.role === 'farmer' && <button className="btn alt" onClick={() => api(`/admin/farmers/${f.id}/toggle`, { method: 'POST' }).then(fr.reload)}>{f.is_active ? 'Disable' : 'Enable'}</button>}</td></tr>)}</tbody></table></div>
      <div className="card" style={{ marginTop: 14 }}><h3>Recent system activity</h3>{ac.data?.slice(0, 30).map(a => <div key={a.id} className="mut">{new Date(a.created).toLocaleString()} · farmer #{a.farmer_id} · {a.kind} · {a.title}</div>)}</div>
    </div>
  )
}
