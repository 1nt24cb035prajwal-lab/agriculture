import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'
import { api } from '../api'
import { useApp } from '../App.jsx'
import { Spinner, Err, Tag, Empty, Note, Section, fmt, useLoad, Field } from '../ui.jsx'

L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})
const Click = ({ onPick }) => { useMapEvents({ click: e => onPick(e.latlng.lat, e.latlng.lng) }); return null }
const Fly = ({ pos }) => { const m = useMap(); useEffect(() => { if (pos) m.flyTo(pos, Math.max(m.getZoom(), 13)) }, [pos]); return null }

// Full-screen map page: search, click/tap, GPS (only on user click), reverse-geocode, manual correction, confirm.
export function MapPicker({ initial, onConfirm, onCancel }) {
  const [pos, setPos] = useState(initial?.lat != null && initial?.lon != null ? [initial.lat, initial.lon] : null)
  const [loc, setLoc] = useState({ state: initial?.state || '', district: initial?.district || '', taluk: initial?.taluk || '', village: initial?.village || '' })
  const [q, setQ] = useState(''); const [hits, setHits] = useState([]); const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [note, setNote] = useState('')
  const geocodeRequest = useRef(0)
  const pick = async (lat, lon) => {
    const request = ++geocodeRequest.current
    setPos([lat, lon]); setBusy(true); setErr(null); setNote('')
    try {
      const r = await api(`/geo/reverse?lat=${lat}&lon=${lon}`)
      if (request === geocodeRequest.current) {
        setLoc({ state: r.state || '', district: r.district || '', taluk: r.taluk || '', village: r.village || '' })
        setNote(r.note)
      }
    } catch (e) {
      if (request === geocodeRequest.current) {
        setErr(e)
        setNote('Could not auto-detect the place. Please type State/District/Taluk/Village yourself.')
      }
    } finally {
      if (request === geocodeRequest.current) setBusy(false)
    }
  }
  const search = async () => { setErr(null); try { setHits(await api('/geo/search?q=' + encodeURIComponent(q))) } catch (e) { setErr(e) } }
  const gps = () => navigator.geolocation ? navigator.geolocation.getCurrentPosition(p => pick(p.coords.latitude, p.coords.longitude), () => setErr(new Error('Location permission denied. Search or tap the map instead.'))) : setErr(new Error('GPS not available.'))
  return (
    <div className="full">
      <div className="bar">
        <input style={{ flex: '2 1 200px' }} placeholder="Search village, town or district…" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} />
        <button className="btn" onClick={search}>Search</button><button className="btn alt" onClick={gps}>📍 Use my current location</button><button className="btn alt" onClick={onCancel}>✕ Close</button>
      </div>
      {hits.length > 0 && <div style={{ maxHeight: 130, overflow: 'auto', borderBottom: '1px solid var(--line)' }}>{hits.map((h, i) => <div key={i} style={{ padding: '6px 12px', cursor: 'pointer' }} onClick={() => { setHits([]); pick(h.lat, h.lon) }}>{h.name}</div>)}</div>}
      <div style={{ flex: 1, minHeight: 0 }}>
        <MapContainer center={pos || [15.3173, 75.7139]} zoom={pos ? 14 : 7} style={{ height: '100%' }}>
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Click onPick={pick} /><Fly pos={pos} />{pos && <Marker position={pos} />}
        </MapContainer>
      </div>
      <div style={{ padding: 12, background: '#fff', borderTop: '1px solid var(--line)' }}>
        <Err e={err} />{note && <div className="mut">{note}</div>}
        {pos ? <><div className="mut">Lat {pos[0].toFixed(5)}, Lon {pos[1].toFixed(5)} {busy && <span className="spin" />}</div>
          <div className="row">{['state', 'district', 'taluk', 'village'].map(k => <div key={k}><label style={{ textTransform: 'capitalize' }}>{k}</label><input value={loc[k]} onChange={e => setLoc({ ...loc, [k]: e.target.value })} /></div>)}</div>
          <button className="btn" style={{ marginTop: 10 }} disabled={busy} onClick={() => onConfirm({ lat: pos[0], lon: pos[1], ...loc })}>Confirm this location</button></>
          : <div className="mut">Tap the exact spot on the map, search for a place, or use your current location.</div>}
      </div>
    </div>
  )
}

const ICON = { Low: '🟢', Medium: '🟡', High: '🟠', Critical: '🔴' }

export function Dashboard() {
  const { farm, farms, me, t } = useApp()
  const nav = useNavigate()
  const [d, setD] = useState(null); const [err, setErr] = useState(null)
  useEffect(() => { setD(null); setErr(null); if (farm) api(`/farms/${farm.id}/dashboard`).then(setD).catch(setErr) }, [farm?.id])
  const big = [['/app/land', '🌾', 'Crop and Land Information'], ['/app/recommend', '🌱', 'Crop Recommendation'], ['/app/disease', '🔬', 'Disease Detection'], ['/app/yield', '📈', 'Crop Yield Prediction']]
  return (
    <div className="fade">
      <div className="grid g4">{big.map(([to, i, l]) => <Link key={to} to={to} className="btn big" style={{ background: 'linear-gradient(135deg,#14532d,#22a45d)' }}><div style={{ fontSize: '2rem' }}>{i}</div>{l}</Link>)}</div>
      <h2 style={{ marginTop: 24 }}>{farm ? `${farm.name}${farm.crop ? ' · ' + farm.crop : ''}` : 'Your farm'}</h2>
      <Err e={err} />
      {!farms ? <Spinner /> : !farm ? <div className="card"><Empty>No farm saved yet. Start with <Link to="/app/land">Crop and Land Information</Link> — add your crop and pick the farm location on the map.</Empty></div>
        : !farm.lat ? <div className="card"><Empty>Farm location is not set. <Link to="/app/land">Select it on the map</Link> to see weather, water, satellite and threat information.</Empty></div>
        : !d ? <Spinner text="Loading live data…" /> :
        <div className="grid g3">
          <Section title="Current weather" res={d.weather}>{w => <><div className="big-n">{fmt(w.current.temp, '°C')}</div><div>{w.current.text}</div>
            <div className="mut">Humidity {fmt(w.current.humidity, '%')} · Rain {fmt(w.current.rain, ' mm')} · Wind {fmt(w.current.wind, ' km/h')}</div>
            <div className="mut">Today: {fmt(w.forecast[0].tmin)}–{fmt(w.forecast[0].tmax)}°C · Rain chance {fmt(w.forecast[0].rain_prob, '%')}</div><div className="mut">Source: {w.source}</div></>}</Section>
          <Section title="Rain alert & weather alerts" res={d.weather}>{w => w.alerts.length ? w.alerts.map((a, i) => <div key={i} style={{ marginBottom: 6 }}><Tag level={a.level} /> <b>{a.title}</b><div className="mut">{a.message}</div></div>) : <div>No weather alerts for the next 7 days.</div>}</Section>
          <Section title="Water requirement" res={d.water}>{w => !w.available ? <div className="mut">{w.reason}</div> : <><div className="big-n">{w.etc_mm_day} mm/day</div>
            <div>≈ {w.daily_litres.toLocaleString()} L/day · {w.weekly_litres.toLocaleString()} L/week</div><div className="mut">{w.irrigation_note}</div>
            <div className="mut">Shortage risk: <Tag level={w.shortage_risk} /> Excess risk: <Tag level={w.excess_risk} /></div><div className="mut">{w.method}</div></>}</Section>
          <Section title="Satellite vegetation (NDVI)" res={d.satellite}>{s => s.latest ? <><div className="big-n">{s.latest.ndvi}</div><span className={'tag ' + s.latest.class}>{s.latest.class}</span><div className="mut">{s.latest.from} → {s.latest.to}</div><div className="mut">{s.source}</div></> : <div className="mut">{s.limitation}</div>}</Section>
          <Section title="Market price" res={d.price}>{p => p.rows.length ? <><div className="big-n">₹{p.rows[0].modal}/q</div><div>{p.rows[0].market}, {p.rows[0].district}</div><div className="mut">Modal price · {p.rows[0].date} · {p.source}</div></> : <div className="mut">No price records found for this crop/state.</div>}</Section>
          <div className="card"><div className="mut" style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '.75rem' }}>Soil fertility (farmer-entered test)</div>{d.fertility.map((n, i) => <div key={i} className="mut" style={{ marginTop: 4 }}><b>{n.nutrient}</b> {n.rating !== 'Unknown' && <>({n.rating})</>} — {n.advice}</div>)}</div>
          <Section title="Seven-day forecast" res={d.weather} wide>{w => <div style={{ height: 230 }}><ResponsiveContainer><LineChart data={w.forecast}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={x => x.slice(5)} /><YAxis yAxisId="a" unit="°" /><YAxis yAxisId="b" orientation="right" unit="mm" /><Tooltip />
            <Line yAxisId="a" dataKey="tmax" name="Max °C" stroke="#dc2626" /><Line yAxisId="a" dataKey="tmin" name="Min °C" stroke="#2563eb" /><Line yAxisId="b" dataKey="rain" name="Rain mm" stroke="#16a34a" /></LineChart></ResponsiveContainer></div>}</Section>
          <div className="card" style={{ gridColumn: '1/-1' }}><div className="mut" style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '.75rem' }}>Agricultural threat alerts</div>
            {d.threats.length === 0 ? <div style={{ padding: 8 }}>No active threats detected from the available data.</div> :
              <table><thead><tr><th>Threat</th><th>Risk</th><th>Source</th><th>Evidence</th><th>Recommended action</th></tr></thead><tbody>{d.threats.map((x, i) => <tr key={i}><td><b>{x.threat}</b></td><td>{ICON[x.level]} <Tag level={x.level} /></td><td>{x.source}</td><td>{x.evidence}</td><td>{x.action}</td></tr>)}</tbody></table>}
            <div className="mut" style={{ marginTop: 8 }}>{d.disclaimer}</div></div>
        </div>}
    </div>
  )
}

const SOILS = ['Black Soil', 'Red Soil', 'Alluvial Soil', 'Laterite Soil', 'Sandy Soil', 'Clay Soil', 'Loamy Soil', 'Silty Soil', 'Other']
const IRR = ['Drip Irrigation', 'Sprinkler Irrigation', 'Flood Irrigation', 'Furrow Irrigation', 'Rainfed Farming', 'Other']
const SRC = ['Borewell', 'Open Well', 'River', 'Canal', 'Lake', 'Rainwater', 'Tank', 'Other']
const SEASONS = ['Kharif', 'Rabi', 'Zaid', 'Summer', 'Other / Custom Season']
const EMPTY = { name: 'My Farm', crop: '', variety: '', stage: '', method: '', prev_crop: '', season: '', start_date: '', harvest_date: '', area: '', unit: 'acres', soil: '', irrigation: '', water_source: '', lat: null, lon: null, state: '', district: '', taluk: '', village: '', soil_ph: '', soil_n: '', soil_p: '', soil_k: '', soil_moisture: '', organic_carbon: '' }
const NUM = ['area', 'soil_ph', 'soil_n', 'soil_p', 'soil_k', 'soil_moisture', 'organic_carbon']

export function CropLand() {
  const { farm, loadFarms, setFid } = useApp()
  const { data: ref } = useLoad(() => api('/crops'))
  const [f, setF] = useState(EMPTY); const [map, setMap] = useState(false); const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null); const [res, setRes] = useState(null); const [wx, setWx] = useState(null); const [saved, setSaved] = useState(false)
  useEffect(() => { if (farm) setF(Object.fromEntries(Object.keys(EMPTY).map(k => [k, farm[k] ?? EMPTY[k]]))); else setF(EMPTY) }, [farm?.id])
  const s = k => e => setF({ ...f, [k]: e.target.value })
  const fetchWx = async (lat, lon) => { try { const w = await api(`/weather?lat=${lat}&lon=${lon}`); setWx(w) } catch (e) { setWx({ error: e.message }) } }
  useEffect(() => { if (f.lat) fetchWx(f.lat, f.lon) }, [f.lat, f.lon])
  const suggest = ref?.crops.find(c => c.name.toLowerCase() === f.crop.toLowerCase())
  const save = async () => {
    setBusy(true); setErr(null); setRes(null)
    try {
      if (!f.crop.trim()) throw new Error('Select or type a crop.')
      if (!f.area || +f.area <= 0) throw new Error('Enter the land area.')
      const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === '' ? null : NUM.includes(k) && v !== null ? +v : v]))
      const saved = farm ? await api('/farms/' + farm.id, { method: 'PUT', body }) : await api('/farms', { method: 'POST', body })
      await loadFarms(); setFid(saved.id); setSaved(true)
      if (saved.lat) setRes(await api(`/farms/${saved.id}/analysis`))
      else setErr(new Error('Saved. Select the farm location on the map to generate the weather-based analysis.'))
    } catch (e) { setErr(e) }
    setBusy(false)
  }
  return (
    <div className="fade">
      {map && <MapPicker initial={f} onCancel={() => setMap(false)} onConfirm={l => { setF({ ...f, ...l }); setMap(false) }} />}
      <h2>Crop and Land Information</h2>
      <div className="grid g2">
        <div className="card"><h3>Crop</h3>
          <Field label="Crop (type to search, or enter your own)"><input list="crops" value={f.crop} onChange={s('crop')} placeholder="e.g. Ragi" /></Field>
          <datalist id="crops">{ref?.crops.map(c => <option key={c.name} value={c.name} />)}</datalist>
          <div className="row"><Field label="Variety"><input value={f.variety} onChange={s('variety')} /></Field>
            <Field label="Growth stage"><select value={f.stage} onChange={s('stage')}><option value="">Select…</option>{ref?.stages.map(x => <option key={x}>{x}</option>)}</select></Field></div>
          <div className="row"><Field label="Farming method"><select value={f.method} onChange={s('method')}><option value="">Select…</option><option>Organic</option><option>Conventional</option></select></Field>
            <Field label="Previous crop"><input value={f.prev_crop} onChange={s('prev_crop')} /></Field></div>
          <div className="row"><Field label="Cultivation start date"><input type="date" value={f.start_date} onChange={s('start_date')} /></Field>
            <Field label="Expected harvest date"><input type="date" value={f.harvest_date} onChange={s('harvest_date')} /></Field></div>
          <Field label="Season"><select value={f.season} onChange={s('season')}><option value="">Select…</option>{SEASONS.map(x => <option key={x}>{x}</option>)}</select></Field>
          {suggest && <div className="mut">Typical season for {suggest.name}: {suggest.seasons.join(', ')} · ~{suggest.days} days. You can choose any season.</div>}
        </div>
        <div className="card"><h3>Land</h3>
          <div className="row"><Field label="Total land area"><input type="number" min="0" step="0.01" value={f.area} onChange={s('area')} /></Field>
            <Field label="Unit"><select value={f.unit} onChange={s('unit')}><option value="acres">Acres</option><option value="hectares">Hectares</option></select></Field></div>
          <Field label="Soil type"><select value={f.soil} onChange={s('soil')}><option value="">Select…</option>{SOILS.map(x => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Irrigation method"><select value={f.irrigation} onChange={s('irrigation')}><option value="">Select…</option>{IRR.map(x => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Water source"><select value={f.water_source} onChange={s('water_source')}><option value="">Select…</option>{SRC.map(x => <option key={x}>{x}</option>)}</select></Field>
          <details><summary style={{ cursor: 'pointer', margin: '10px 0' }}>Optional soil test values</summary>
            <div className="row"><Field label="Soil pH"><input type="number" step="0.1" value={f.soil_ph} onChange={s('soil_ph')} /></Field><Field label="Organic carbon (%)"><input type="number" step="0.01" value={f.organic_carbon} onChange={s('organic_carbon')} /></Field></div>
            <div className="row"><Field label="Available N (kg/ha)"><input type="number" value={f.soil_n} onChange={s('soil_n')} /></Field><Field label="Available P (kg/ha)"><input type="number" value={f.soil_p} onChange={s('soil_p')} /></Field><Field label="Available K (kg/ha)"><input type="number" value={f.soil_k} onChange={s('soil_k')} /></Field></div>
            <Field label="Soil moisture (%) — your own reading"><input type="number" value={f.soil_moisture} onChange={s('soil_moisture')} /></Field></details>
        </div>
      </div>
      <div className="card" style={{ marginTop: 14 }}><h3>Farm location</h3>
        <button className="btn" onClick={() => setMap(true)}>📍 Select Farm Location</button>
        {f.lat ? <div style={{ marginTop: 10 }}><b>{[f.village, f.taluk, f.district, f.state].filter(Boolean).join(', ') || 'Location selected'}</b><div className="mut">Lat {(+f.lat).toFixed(5)}, Lon {(+f.lon).toFixed(5)}</div></div> : <div className="mut" style={{ marginTop: 8 }}>No location selected yet.</div>}
        {wx && (wx.error ? <div className="mut">Weather unavailable: {wx.error}</div> : <div style={{ marginTop: 10 }}><b>Weather at this location</b> <span className="mut">({wx.source})</span>
          <div>{wx.current.text} · {wx.current.temp}°C · Humidity {wx.current.humidity}% · Rain {wx.current.rain} mm · Wind {wx.current.wind} km/h</div>
          <div className="mut">7-day rain forecast: {wx.forecast.map(r => `${r.date.slice(5)}: ${r.rain}mm`).join(' · ')}</div></div>)}
      </div>
      <Err e={err} />{saved && !err && <div className="ok">Crop and land information saved.</div>}
      <button className="btn" style={{ marginTop: 14 }} onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save Crop and Land Information'}</button>
      {busy && <Spinner text="Generating analysis…" />}
      {res && <div className="card fade" style={{ marginTop: 16 }}><h3>Agricultural analysis</h3>
        <div className="grid g3">
          <div><b>Growth stage</b><div>{res.growth_stage || 'Not entered'}</div></div>
          <div><b>Weather suitability</b><div>{res.weather_suitability ? `${res.weather_suitability.score}% — ${res.weather_suitability.text}` : 'Crop not in reference table'}</div></div>
          <div><b>Soil suitability</b><div>{res.soil_suitability || 'Not enough data'}</div></div>
          <div><b>Water requirement</b>{res.water.available ? <div>{res.water.etc_mm_day} mm/day (~{res.water.daily_litres.toLocaleString()} L/day)<div className="mut">{res.water.method}</div></div> : <div>{res.water.reason}</div>}</div>
          <div><b>Irrigation</b><div>{res.water.available ? res.water.irrigation_note : '—'}</div></div>
          <div><b>Expected harvest</b><div>{res.expected_harvest || 'Enter start date / harvest date'}</div></div>
          <div><b>Disease risk</b><div>{typeof res.disease_risk === 'string' ? res.disease_risk : res.disease_risk.map(a => a.title).join('; ')}</div></div>
          <div style={{ gridColumn: 'span 2' }}><b>Fertilizer / nutrients</b>{res.fertilizer.map((n, i) => <div key={i} className="mut">{n.advice}</div>)}</div>
        </div>
        <h4>Threat warnings</h4>{res.threats.length ? res.threats.map((x, i) => <div key={i}><Tag level={x.level} /> <b>{x.threat}</b> — {x.action}</div>) : <div>None detected.</div>}
        <Note>Estimated yield: use the <Link to="/app/yield">Yield Prediction</Link> page (needs the trained model). {res.disclaimer}</Note></div>}
    </div>
  )
}

export function Recommend() {
  const { farm, loadFarms, me } = useApp()
  const nav = useNavigate()
  const [map, setMap] = useState(false); const [loc, setLoc] = useState(null)
  const [soil, setSoil] = useState(''); const [ph, setPh] = useState('')
  const [npk, setNpk] = useState({ nitrogen: '', phosphorus: '', potassium: '' })
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [r, setR] = useState(null); const [sel, setSel] = useState([]); const [det, setDet] = useState(null)
  const go = async l => {
    setBusy(true); setErr(null); setR(null)
    try {
      setR(await api('/recommend', { method: 'POST', body: {
        lat: l.lat, lon: l.lon, soil: soil || null, ph: ph ? +ph : null,
        nitrogen: npk.nitrogen === '' ? null : +npk.nitrogen,
        phosphorus: npk.phosphorus === '' ? null : +npk.phosphorus,
        potassium: npk.potassium === '' ? null : +npk.potassium,
        state: l.state, district: l.district,
      } }))
    } catch (e) { setErr(e) }
    setBusy(false)
  }
  const add = async c => {
    try {
      const body = { crop: c.crop, lat: loc.lat, lon: loc.lon, state: loc.state, district: loc.district, taluk: loc.taluk, village: loc.village, soil: soil || null, name: farm ? undefined : 'My Farm' }
      if (farm) await api('/farms/' + farm.id, { method: 'PUT', body: { crop: c.crop } }); else await api('/farms', { method: 'POST', body })
      await loadFarms(); nav('/app/land')
    } catch (e) { setErr(e) }
  }
  const cmp = r?.results.filter(x => sel.includes(x.crop))
  return (
    <div className="fade">
      {map && <MapPicker initial={loc} onCancel={() => setMap(false)} onConfirm={l => { setLoc(l); setMap(false); go(l) }} />}
      <h2>Crop Recommendation</h2>
      <div className="card" style={{ textAlign: 'center', padding: 30 }}>
        <button className="btn" style={{ fontSize: '1.2rem', padding: '18px 40px' }} onClick={() => setMap(true)}>📍 Select Location</button>
        {loc && <div style={{ marginTop: 10 }}><b>{[loc.village, loc.taluk, loc.district, loc.state].filter(Boolean).join(', ')}</b></div>}
        <details style={{ textAlign: 'left', marginTop: 14 }}><summary style={{ cursor: 'pointer' }}>Optional: add soil information for a better score</summary>
          <div className="row"><Field label="Soil type"><select value={soil} onChange={e => setSoil(e.target.value)}><option value="">Unknown</option>{SOILS.map(x => <option key={x}>{x}</option>)}</select></Field>
            <Field label="Soil pH"><input type="number" step="0.1" value={ph} onChange={e => setPh(e.target.value)} /></Field></div>
          <div className="row">{[['nitrogen', 'Nitrogen (N)'], ['phosphorus', 'Phosphorus (P)'], ['potassium', 'Potassium (K)']].map(([key, label]) =>
            <Field key={key} label={label}><input type="number" min="0" step="any" value={npk[key]} onChange={e => setNpk({ ...npk, [key]: e.target.value })} /></Field>)}</div>
          <div className="mut">Enter soil-test N/P/K values to use the trained crop model; avoid entering fertilizer application rates.</div>
          {loc && <button className="btn alt" onClick={() => go(loc)}>Re-run with this soil info</button>}</details>
      </div>
      <Err e={err} />{busy && <Spinner text="Fetching 12-month climate and scoring crops…" />}
      {r && <>
        <div className="card" style={{ margin: '14px 0' }}><b>Climate used:</b> last-12-month rainfall ≈ {r.climate.annual_rain_mm} mm, recent mean temperature {r.climate.recent_mean_temp_c} °C <span className="mut">({r.climate.source})</span>
          {r.data_missing.map((x, i) => <div key={i} className="mut">ℹ️ {x}</div>)}<div className="mut">{r.disclaimer}</div></div>
        {r.trained_model && <div className="card" style={{ marginBottom: 14 }}>
          <h3>Trained crop model</h3>
          {r.trained_model.metrics && <div className="mut">Held-out test accuracy: {Math.round(r.trained_model.metrics.test_accuracy * 100)}% · {r.trained_model.metrics.rows.toLocaleString()} training-dataset rows</div>}
          {r.trained_model.results?.length
            ? <><div className="grid g3" style={{ marginTop: 10 }}>{r.trained_model.results.map(item =>
              <div className="card" key={item.crop}><b>{item.crop}</b><div className="mut">{Math.round(item.confidence * 100)}% model score</div></div>)}</div>
              {r.trained_model.input_notes?.map((message, index) => <div className="mut" key={index}>{message}</div>)}
              <div className="mut">{r.trained_model.disclaimer}</div></>
            : <div className="mut">{r.trained_model.message}</div>}
        </div>}
        {r.results.length === 0 ? <Empty>No crop in the reference table scored well for this location with the data available.</Empty> :
          <div className="grid g3">{r.results.map(c => <div key={c.crop} className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}><h3>{c.crop}</h3><span className="big-n">{c.score}%</span></div>
            <div className="bar-bg"><div className="bar-fg" style={{ width: c.score + '%' }} /></div>
            <div className="mut" style={{ marginTop: 8 }}>Season: {c.seasons.join(', ')} · {c.duration_days} days · Water need {c.water_need_mm} mm</div>
            <div className="mut">Irrigation: {c.irrigation}</div>
            <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" style={{ width: 'auto' }} checked={sel.includes(c.crop)} onChange={e => setSel(e.target.checked ? [...sel, c.crop] : sel.filter(x => x !== c.crop))} />Compare</label>
            <div className="row"><button className="btn alt" onClick={() => setDet(c)}>View Full Details</button><button className="btn" onClick={() => add(c)}>Add to My Farm</button></div></div>)}</div>}
        {cmp?.length > 1 && <div className="card" style={{ marginTop: 14 }}><h3>Comparison</h3><div style={{ height: 240 }}><ResponsiveContainer><BarChart data={cmp.map(c => ({ crop: c.crop, ...c.factors }))}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="crop" /><YAxis domain={[0, 100]} /><Tooltip /><Bar dataKey="temperature" fill="#dc2626" /><Bar dataKey="water" fill="#2563eb" /><Bar dataKey="season" fill="#16a34a" /><Bar dataKey="soil" fill="#92400e" /></BarChart></ResponsiveContainer></div></div>}
      </>}
      {det && <div className="full" style={{ background: 'rgba(0,0,0,.4)', alignItems: 'center', justifyContent: 'center' }}><div className="card" style={{ maxWidth: 560, maxHeight: '85vh', overflow: 'auto' }}>
        <h3>{det.crop} — why {det.score}%?</h3>{det.explanation.map((x, i) => <div key={i} style={{ margin: '4px 0' }}>• {x}</div>)}
        <div className="mut">Suitable soils: {det.good_soils.join(', ')}</div>{det.risks.map((x, i) => <div key={i} className="mut">⚠ {x}</div>)}
        <button className="btn" style={{ marginTop: 10 }} onClick={() => setDet(null)}>Close</button></div></div>}
    </div>
  )
}
