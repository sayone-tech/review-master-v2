// Sample data and helpers
const ORGS = [
  { name: 'Bella Bistro Group', type: 'Restaurant', email: 'finance@bellabistro.com', used: 8, alloc: 12, status: 'Active', created: 'Mar 14, 2026', admin: 'Active' },
  { name: 'Nimbus Labs', type: 'Retail', email: 'ops@nimbus.co', used: 3, alloc: 5, status: 'Active', created: 'Feb 28, 2026', admin: 'Active' },
  { name: 'Urban Grocers', type: 'Supermarket', email: 'hello@urbangrocers.com', used: 14, alloc: 20, status: 'Active', created: 'Feb 12, 2026', admin: 'Pending' },
  { name: 'Meridian Pharmacy', type: 'Pharmacy', email: 'admin@meridianrx.com', used: 2, alloc: 4, status: 'Disabled', created: 'Jan 30, 2026', admin: 'Active' },
  { name: 'Cobalt & Co.', type: 'Retail', email: 'team@cobaltco.com', used: 1, alloc: 3, status: 'Active', created: 'Jan 22, 2026', admin: 'Expired' },
  { name: 'Ramen Hōjō', type: 'Restaurant', email: 'books@ramenhojo.jp', used: 6, alloc: 6, status: 'Active', created: 'Jan 11, 2026', admin: 'Active' },
  { name: 'Oak & Ember', type: 'Restaurant', email: 'hi@oakandember.co', used: 0, alloc: 2, status: 'Active', created: 'Dec 30, 2025', admin: 'Pending' },
  { name: 'Helio Markets', type: 'Supermarket', email: 'central@heliomkt.com', used: 22, alloc: 25, status: 'Active', created: 'Dec 18, 2025', admin: 'Active' },
];

const typeTone = (t) => ({ Retail: 'neutral', Restaurant: 'neutral', Pharmacy: 'neutral', Supermarket: 'neutral' }[t] || 'neutral');

const adminBadge = (s) => s === 'Active'
  ? <Badge tone="green" dot>Active</Badge>
  : s === 'Pending'
  ? <Badge tone="amber" dot>Pending invite</Badge>
  : <Badge tone="red" dot>Invitation expired</Badge>;

const statusBadge = (s) => s === 'Active'
  ? <Badge tone="green" dot>Active</Badge>
  : <Badge tone="gray" dot>Disabled</Badge>;

// Filter bar
const FilterBar = () => (
  <div className="filter-bar">
    <div className="search-input">
      <Icon.Search />
      <input placeholder="Search by name or email" />
    </div>
    <select className="select">
      <option>All statuses</option><option>Active</option><option>Disabled</option>
    </select>
    <select className="select">
      <option>All types</option><option>Retail</option><option>Restaurant</option><option>Pharmacy</option><option>Supermarket</option>
    </select>
  </div>
);

// Organisations table (desktop)
const OrgTable = ({ loading = false, showMenuRow = null }) => (
  <div className="table-wrap">
    <table className="data">
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Email</th>
          <th style={{textAlign:'right'}}>Stores</th>
          <th>Status</th>
          <th>Created</th>
          <th style={{width: 50}}></th>
        </tr>
      </thead>
      <tbody>
        {loading ? Array.from({length:6}).map((_,i)=>(
          <tr key={i}>
            <td><div className="sk" style={{width:140, height:14}}/></td>
            <td><div className="sk" style={{width:64, height:18, borderRadius:999}}/></td>
            <td><div className="sk" style={{width:180, height:14}}/></td>
            <td style={{textAlign:'right'}}><div className="sk" style={{width:42, height:14, marginLeft:'auto'}}/></td>
            <td><div className="sk" style={{width:64, height:18, borderRadius:999}}/></td>
            <td><div className="sk" style={{width:88, height:14}}/></td>
            <td><div className="sk" style={{width:20, height:20, borderRadius:6}}/></td>
          </tr>
        )) : ORGS.map((o, i) => (
          <tr key={i}>
            <td>
              <div className="name-link">{o.name}</div>
              <div className="sub">{o.email}</div>
            </td>
            <td><Badge tone={typeTone(o.type)}>{o.type}</Badge></td>
            <td style={{color:'var(--muted)', fontSize:13}}>{o.email}</td>
            <td style={{textAlign:'right'}}><StoreCount used={o.used} alloc={o.alloc}/></td>
            <td>{statusBadge(o.status)}</td>
            <td style={{color:'var(--muted)'}}>{o.created}</td>
            <td style={{position:'relative'}}>
              <button className="dots-btn row-actions"><Icon.MoreHorizontal size={16}/></button>
              {showMenuRow === i && (
                <RowMenu items={[
                  {label:'View details', icon:<Icon.Eye/>},
                  {label:'Edit', icon:<Icon.Edit/>},
                  {label:'Adjust store count', icon:<Icon.Store/>},
                  '---',
                  {label: o.status==='Active'?'Disable':'Enable', icon: o.status==='Active'?<Icon.Lock/>:<Icon.Check/>},
                  {label:'Delete', icon:<Icon.Trash/>, danger:true},
                ]}/>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    <div className="pagination">
      <div>Showing <strong style={{color:'var(--ink)'}}>1–8</strong> of <strong style={{color:'var(--ink)'}}>47</strong></div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2" style={{fontSize:13}}>
          <span>Rows</span>
          <select className="select" style={{padding:'4px 28px 4px 10px', fontSize:12.5}}>
            <option>10</option><option>25</option><option>50</option><option>100</option>
          </select>
        </div>
        <div className="pag-controls">
          <button className="pag-btn" disabled><Icon.ChevronLeft size={14}/></button>
          <button className="pag-btn active">1</button>
          <button className="pag-btn">2</button>
          <button className="pag-btn">3</button>
          <span style={{padding:'0 4px', color:'var(--faint)'}}>…</span>
          <button className="pag-btn">6</button>
          <button className="pag-btn"><Icon.ChevronRight size={14}/></button>
        </div>
      </div>
    </div>
  </div>
);

// Artboards — Organisations list variants
const OrgListArtboard = ({ loading = false, empty = false, withMenu = null }) => (
  <div className="artboard-root scroll-y rm">
    <Shell active="orgs" title="Organisations">
      <div className="page-header">
        <div>
          <h1 className="page-title">Organisations</h1>
          <p className="page-sub">{empty?'No organisations have been created yet.':'47 organisations managing 212 stores across 4 categories.'}</p>
        </div>
        <Btn kind="primary" size="lg" icon={<Icon.Plus size={16}/>}>Create Organisation</Btn>
      </div>
      <FilterBar />
      {empty ? (
        <div className="empty-state">
          <div className="empty-icon"><Icon.Building /></div>
          <h3 className="empty-title">No organisations yet</h3>
          <p className="empty-desc">Create your first organisation to start onboarding stores.</p>
          <Btn kind="primary" icon={<Icon.Plus size={14}/>}>Create your first organisation</Btn>
        </div>
      ) : <OrgTable loading={loading} showMenuRow={withMenu} />}
    </Shell>
  </div>
);

Object.assign(window, { ORGS, OrgTable, FilterBar, OrgListArtboard, statusBadge, adminBadge, typeTone });
