import { useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
const money = n => '₹' + Number(n || 0).toFixed(2)

function formatDate(val) {
  if (!val) return ''
  const str = String(val)
  const isUtc = str.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(str)
  const d = new Date(isUtc ? str : str + 'Z')
  return isNaN(d.getTime()) ? str : d.toLocaleString()
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('stationery_token') || '')
  const [username, setUsername] = useState(localStorage.getItem('stationery_user') || '')
  const [page, setPage] = useState('Dashboard')
  const [products, setProducts] = useState([])
  const [sales, setSales] = useState([])
  const [dashboard, setDashboard] = useState({ product_count: 0, units_in_stock: 0, sales_total: 0, bills_count: 0 })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [login, setLogin] = useState({ username: 'shopkeeper', password: 'Shop@123' })
  const [form, setForm] = useState({ name: '', category: 'General', price: '', stock: '' })
  const [editingId, setEditingId] = useState(null)
  const [cart, setCart] = useState({})
  const [lastBill, setLastBill] = useState(null)
  const [search, setSearch] = useState('')

  async function api(path, options = {}) {
    const response = await fetch(API + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    })
    const data = response.status === 204 ? null : await response.json().catch(() => ({}))
    if (!response.ok) {
      if (response.status === 401 && token) logout()
      let msg = 'Request failed.'
      if (typeof data.detail === 'string') {
        msg = data.detail
      } else if (Array.isArray(data.detail)) {
        msg = data.detail.map(d => d.msg || JSON.stringify(d)).join(', ')
      } else if (data.message) {
        msg = data.message
      }
      throw new Error(msg)
    }
    return data
  }

  function logout() {
    localStorage.removeItem('stationery_token')
    localStorage.removeItem('stationery_user')
    setToken(''); setUsername(''); setProducts([]); setSales([])
  }

  async function loadAll() {
    try {
      const [p, s, d] = await Promise.all([api('/products'), api('/sales'), api('/dashboard')])
      setProducts(p); setSales(s); setDashboard(d); setError('')
    } catch (e) { setError(e.message) }
  }

  useEffect(() => { if (token) loadAll() }, [token])

  async function doLogin(e) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const result = await fetch(API + '/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(login)
      })
      const data = await result.json().catch(() => ({}))
      if (!result.ok) {
        let msg = 'Login failed.'
        if (typeof data.detail === 'string') msg = data.detail
        else if (Array.isArray(data.detail)) msg = data.detail.map(d => d.msg || JSON.stringify(d)).join(', ')
        throw new Error(msg)
      }
      localStorage.setItem('stationery_token', data.access_token)
      localStorage.setItem('stationery_user', data.username)
      setToken(data.access_token); setUsername(data.username); setNotice('Welcome back!')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  function clearForm() {
    setForm({ name: '', category: 'General', price: '', stock: '' }); setEditingId(null)
  }

  async function saveProduct(e) {
    e.preventDefault(); setError(''); setNotice('')
    const name = form.name.trim()
    const category = form.category.trim() || 'General'
    const price = parseFloat(form.price)
    const stock = parseInt(form.stock, 10)

    if (!name) {
      setError('Product name is required.')
      return
    }
    if (isNaN(price) || price <= 0) {
      setError('Price must be a positive number.')
      return
    }
    if (isNaN(stock) || stock < 0) {
      setError('Stock quantity cannot be negative.')
      return
    }

    const body = { name, category, price: Math.round(price * 100) / 100, stock }
    try {
      await api(editingId ? `/products/${editingId}` : '/products', {
        method: editingId ? 'PUT' : 'POST', body: JSON.stringify(body)
      })
      clearForm(); await loadAll(); setNotice(editingId ? 'Product updated.' : 'Product added.')
    } catch (e) { setError(e.message) }
  }

  async function removeProduct(id) {
    if (!confirm('Delete this product?')) return
    try {
      await api(`/products/${id}`, { method: 'DELETE' })
      if (editingId === id) clearForm()
      setCart(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      await loadAll()
      setNotice('Product deleted.')
    }
    catch (e) { setError(e.message) }
  }

  const filteredProducts = products.filter(p => `${p.name} ${p.category}`.toLowerCase().includes(search.toLowerCase()))
  const cartItems = useMemo(() => Object.entries(cart).map(([id, quantity]) => {
    const product = products.find(p => p.id === Number(id))
    return product ? { ...product, quantity, line_total: Math.round(product.price * quantity * 100) / 100 } : null
  }).filter(Boolean), [cart, products])
  const cartTotal = Math.round(cartItems.reduce((sum, item) => sum + item.line_total, 0) * 100) / 100

  function changeQty(id, amount) {
    const numericId = Number(id)
    const product = products.find(p => p.id === numericId)
    if (!product) return
    setCart(prev => {
      const next = { ...prev }
      const quantity = (next[numericId] || 0) + amount
      if (quantity <= 0) delete next[numericId]
      else if (quantity <= product.stock) next[numericId] = quantity
      else setError(`Only ${product.stock} units available for "${product.name}".`)
      return next
    })
  }

  async function checkout() {
    if (!cartItems.length) return
    setError(''); setNotice('')
    try {
      const bill = await api('/sales', {
        method: 'POST',
        body: JSON.stringify({ items: cartItems.map(i => ({ product_id: i.id, quantity: i.quantity })) })
      })
      setLastBill(bill); setCart({}); await loadAll(); setPage('Billing'); setNotice(`Bill #${bill.id} created successfully.`)
    } catch (e) { setError(e.message); await loadAll() }
  }

  if (!token) return <main className="login-wrap">
    <form className="login-card" onSubmit={doLogin}>
      <div className="brand-icon">✎</div>
      <p className="eyebrow">SMART STATIONERY SHOP</p>
      <h1>Shopkeeper Login</h1>
      <p className="muted">Sign in to manage products and create bills.</p>
      {error && <div className="alert error">{error}</div>}
      <label>Username<input value={login.username} onChange={e => setLogin({ ...login, username: e.target.value })} required /></label>
      <label>Password<input type="password" value={login.password} onChange={e => setLogin({ ...login, password: e.target.value })} required /></label>
      <button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in →'}</button>
      <div className="demo"><b>Demo login</b><br />Username: shopkeeper<br />Password: Shop@123</div>
    </form>
  </main>

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon small">✎</span><div><b>Paper & Pen</b><small>STATIONERY SHOP</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      {['Dashboard', 'Products', 'Billing', 'Sales History'].map((item, i) =>
        <button key={item} className={`nav-item ${page === item ? 'active' : ''}`} onClick={() => { setPage(item); setError(''); setNotice('') }}>
          <span>{['▦', '▤', '＋', '◷'][i]}</span>{item}
        </button>)}
      <div className="sidebar-bottom"><div className="user-chip"><div className="avatar">{username.slice(0,1).toUpperCase()}</div><div><b>{username}</b><small>Shopkeeper</small></div></div><button className="logout" onClick={logout}>↪ Sign out</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><p className="eyebrow">STORE MANAGEMENT</p><h1>{page}</h1></div><div className="top-user"><span className="status-dot"></span> Shop open <div className="avatar">{username.slice(0,1).toUpperCase()}</div></div></header>
      <section className="content">
        {error && <div className="alert error">{error}<button onClick={() => setError('')}>×</button></div>}
        {notice && <div className="alert success">{notice}<button onClick={() => setNotice('')}>×</button></div>}

        {page === 'Dashboard' && <>
          <div className="welcome"><div><p className="eyebrow light">YOUR STORE AT A GLANCE</p><h2>Everything in one place.</h2><p>Manage your stationery inventory and sales with ease.</p></div><div className="welcome-art">✎<span>✦</span></div></div>
          <div className="stats-grid">
            <Stat title="Total products" value={dashboard.product_count} icon="▤" foot="Different products" />
            <Stat title="Units in stock" value={dashboard.units_in_stock} icon="▧" foot="Across all products" />
            <Stat title="Total sales" value={money(dashboard.sales_total)} icon="₹" foot="All completed bills" />
            <Stat title="Bills generated" value={dashboard.bills_count} icon="▣" foot="Completed transactions" />
          </div>
          <div className="panel"><div className="panel-heading"><div><h3>Recent bills</h3><p>Latest completed transactions</p></div><button className="text-button" onClick={() => setPage('Sales History')}>View all →</button></div>
            {sales.length ? <SalesTable sales={sales.slice(0,5)} /> : <Empty text="No sales yet. Open Billing to create your first bill." />}</div>
          <div className="quick-actions"><button onClick={() => setPage('Products')}>＋ Add a product</button><button onClick={() => setPage('Billing')}>＋ Create a bill</button></div>
        </>}

        {page === 'Products' && <div className="two-col">
          <div className="panel form-panel"><div className="panel-heading"><div><h3>{editingId ? 'Edit product' : 'Add a product'}</h3><p>Keep your inventory up to date.</p></div></div>
            <form onSubmit={saveProduct} className="product-form">
              <label>Product name<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Gel Pen" required maxLength="160" /></label>
              <label>Category<input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} placeholder="e.g. Pens" required /></label>
              <div className="form-row"><label>Price (₹)<input type="number" min="0.01" step="0.01" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} required /></label><label>Stock quantity<input type="number" min="0" step="1" value={form.stock} onChange={e => setForm({ ...form, stock: e.target.value })} required /></label></div>
              <button className="primary full">{editingId ? 'Save changes' : 'Add product'}</button>
              {editingId && <button type="button" className="secondary full" onClick={clearForm}>Cancel edit</button>}
            </form>
          </div>
          <div className="panel"><div className="panel-heading wrap"><div><h3>Product inventory</h3><p>{products.length} products in your store</p></div><input className="search" placeholder="Search products…" value={search} onChange={e => setSearch(e.target.value)} /></div>
            <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>PRICE</th><th>STOCK</th><th>ACTIONS</th></tr></thead><tbody>
              {filteredProducts.map(p => <tr key={p.id}><td><b>{p.name}</b><small className="cell-sub">{p.category}</small></td><td>{money(p.price)}</td><td><span className={`stock ${p.stock < 10 ? 'low' : ''}`}>{p.stock}</span></td><td><div className="actions"><button title="Edit" onClick={() => { setForm({ name:p.name, category:p.category, price:String(p.price), stock:String(p.stock) }); setEditingId(p.id); window.scrollTo({top:0,behavior:'smooth'}) }}>Edit</button><button className="danger-text" onClick={() => removeProduct(p.id)}>Delete</button></div></td></tr>)}
            </tbody></table>{!filteredProducts.length && <Empty text="No matching products found." />}</div>
          </div>
        </div>}

        {page === 'Billing' && <div className="billing-grid">
          <div className="panel"><div className="panel-heading wrap"><div><h3>Select products</h3><p>Add items to the current bill.</p></div><input className="search" placeholder="Search products…" value={search} onChange={e => setSearch(e.target.value)} /></div>
            <div className="product-picker">{filteredProducts.map(p => <div className="pick-card" key={p.id}><div className="product-symbol">✎</div><div className="pick-info"><b>{p.name}</b><small>{p.category} · {p.stock} in stock</small><strong>{money(p.price)}</strong></div><button disabled={p.stock === 0} className="add-button" onClick={() => changeQty(p.id,1)}>＋</button></div>)}</div>
          </div>
          <div className="panel bill-panel"><div className="panel-heading"><div><h3>Current bill</h3><p>{cartItems.reduce((n,i) => n+i.quantity,0)} items selected</p></div><span className="bill-icon">▤</span></div>
            {cartItems.length ? <div className="cart-lines">{cartItems.map(i => <div className="cart-line" key={i.id}><div className="cart-name"><b>{i.name}</b><small>{money(i.price)} each</small></div><div className="qty"><button onClick={() => changeQty(i.id,-1)}>−</button><span>{i.quantity}</span><button onClick={() => changeQty(i.id,1)}>＋</button></div><b>{money(i.line_total)}</b></div>)}</div> : <Empty text="Your bill is empty. Add products from the list." />}
            <div className="bill-total"><span>Total amount</span><strong>{money(cartTotal)}</strong></div><button className="primary full" disabled={!cartItems.length} onClick={checkout}>Complete sale →</button><button className="secondary full" onClick={() => setCart({})} disabled={!cartItems.length}>Clear bill</button>
            {lastBill && (
              <div className="last-bill">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <b>Receipt #{lastBill.id}</b>
                  <small style={{ color: '#8892a0' }}>{formatDate(lastBill.created_at)}</small>
                </div>
                {lastBill.items && lastBill.items.length > 0 && (
                  <div style={{ margin: '8px 0', borderTop: '1px dashed #dce2eb', borderBottom: '1px dashed #dce2eb', padding: '6px 0' }}>
                    {lastBill.items.map(item => (
                      <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', margin: '3px 0' }}>
                        <span>{item.product_name} × {item.quantity}</span>
                        <span>{money(item.line_total)}</span>
                      </div>
                    ))}
                  </div>
                )}
                <p style={{ display: 'flex', justifyContent: 'space-between', margin: '6px 0', fontSize: '12px' }}>
                  <span>Total paid:</span>
                  <b>{money(lastBill.total)}</b>
                </p>
                <button className="secondary full" onClick={() => window.print()}>Print receipt</button>
              </div>
            )}
          </div>
        </div>}

        {page === 'Sales History' && <div className="panel"><div className="panel-heading"><div><h3>Sales history</h3><p>Your latest 100 completed bills.</p></div><button className="secondary" onClick={loadAll}>↻ Refresh</button></div>
          {sales.length ? <SalesTable sales={sales} detailed /> : <Empty text="Completed bills will appear here." />}</div>}
      </section>
      <footer>Paper & Pen <span>·</span> Stationery Shop Management</footer>
    </main>
  </div>
}

function Stat({ title, value, icon, foot }) {
  return <div className="stat-card"><div className="stat-top"><span>{title}</span><span className="stat-icon">{icon}</span></div><strong>{value}</strong><small>{foot}</small></div>
}
function Empty({ text }) { return <div className="empty"><span>▤</span><p>{text}</p></div> }
function SalesTable({ sales, detailed = false }) {
  return <div className="table-wrap"><table><thead><tr><th>BILL</th><th>DATE & TIME</th>{detailed && <th>ITEMS</th>}<th>TOTAL</th></tr></thead><tbody>
    {sales.map(s => <tr key={s.id}><td><b>#{s.id}</b></td><td>{formatDate(s.created_at)}</td>{detailed && <td>{s.items?.map(i => `${i.product_name} × ${i.quantity}`).join(', ') || '—'}</td>}<td><b>{money(s.total)}</b></td></tr>)}
  </tbody></table></div>
}
