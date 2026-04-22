// Mobile and Tablet views

const MobileFrame = ({ children, width = 390, height = 780 }) => (
  <div className="artboard-root rm" style={{background:'#E4E4E7', display:'flex', alignItems:'center', justifyContent:'center', padding:20}}>
    <div style={{width, height, borderRadius:28, background:'#fff', boxShadow:'0 20px 60px rgba(0,0,0,0.18), 0 0 0 10px #18181B, 0 0 0 11px #27272A', overflow:'hidden', position:'relative'}}>
      {children}
    </div>
  </div>
);

const MobileList = () => (
  <MobileFrame>
    <div style={{height:'100%', display:'flex', flexDirection:'column', background:'var(--bg)'}}>
      <div style={{height:36, background:'#fff'}}/>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 14px', background:'#fff', borderBottom:'1px solid var(--line)'}}>
        <button className="icon-btn"><Icon.Menu size={18}/></button>
        <div style={{fontSize:14, fontWeight:600}}>Organisations</div>
        <button className="icon-btn" style={{position:'relative'}}><Icon.Bell size={18}/><span className="dot"/></button>
      </div>
      <div style={{padding:14, flex:1, overflow:'auto'}}>
        <Btn kind="primary" block icon={<Icon.Plus size={14}/>} style={{marginBottom:12}}>Create Organisation</Btn>
        <div className="search-input" style={{marginBottom:10}}>
          <Icon.Search/><input placeholder="Search organisations"/>
        </div>
        <div style={{display:'flex', gap:8, marginBottom:14}}>
          <select className="select" style={{flex:1}}><option>All statuses</option></select>
          <select className="select" style={{flex:1}}><option>All types</option></select>
        </div>
        {ORGS.slice(0,5).map((o, i) => (
          <div key={i} className="mobile-card">
            <div className="mobile-card-head">
              <div>
                <div style={{fontWeight:600, fontSize:14, color:'var(--ink)'}}>{o.name}</div>
                <div style={{fontSize:12, color:'var(--subtle)', marginTop:2}}>{o.email}</div>
              </div>
              <button className="dots-btn"><Icon.MoreHorizontal size={16}/></button>
            </div>
            <div style={{display:'flex', gap:6, marginBottom:8}}>
              <Badge tone="neutral">{o.type}</Badge>
              {statusBadge(o.status)}
            </div>
            <dl style={{margin:0}}>
              <div className="mobile-card-row"><dt>Stores</dt><dd><StoreCount used={o.used} alloc={o.alloc}/></dd></div>
              <div className="mobile-card-row"><dt>Created</dt><dd style={{fontWeight:400, color:'var(--muted)'}}>{o.created}</dd></div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  </MobileFrame>
);

const MobileDrawer = () => (
  <MobileFrame>
    <div style={{height:'100%', position:'relative'}}>
      <div style={{position:'absolute', inset:0, background:'rgba(0,0,0,0.5)'}}/>
      <div style={{position:'absolute', top:0, left:0, bottom:0, width:260, background:'var(--black)', color:'#fff', padding:'20px 0'}}>
        <div className="sidebar-logo">
          <div className="logo-mark">R</div>
          <div className="logo-text">Review<em>Master</em></div>
        </div>
        <div className="sidebar-section-label">Manage</div>
        <div className="nav-item active"><Icon.Building size={18}/>Organisations</div>
        <div className="nav-item"><Icon.User size={18}/>Profile</div>
        <div style={{position:'absolute', bottom:20, left:0, right:0}}>
          <div className="nav-item"><Icon.LogOut size={18}/>Log out</div>
        </div>
      </div>
    </div>
  </MobileFrame>
);

const MobileCreateModal = () => (
  <MobileFrame>
    <div style={{height:'100%', background:'#fff', display:'flex', flexDirection:'column'}}>
      <div style={{height:36, background:'#fff'}}/>
      <div style={{padding:'14px 16px', borderBottom:'1px solid var(--line)', display:'flex', alignItems:'center', justifyContent:'space-between'}}>
        <button className="icon-btn"><Icon.X size={18}/></button>
        <div style={{fontSize:14, fontWeight:600}}>Create organisation</div>
        <div style={{width:34}}/>
      </div>
      <div style={{padding:16, flex:1, overflow:'auto'}}>
        <Field label="Organisation name" required><Input placeholder="e.g., Example Corp"/></Field>
        <Field label="Type" required><Select><option>Select organisation type</option><option>Retail</option></Select></Field>
        <Field label="Number of stores" required><Input type="number" placeholder="e.g., 5"/></Field>
        <Field label="Address"><Textarea placeholder="123 Main St…"/></Field>
        <Field label="Email" required><Input type="email" placeholder="contact@example.com"/></Field>
      </div>
      <div style={{padding:14, borderTop:'1px solid var(--line)', display:'flex', gap:8}}>
        <Btn block>Cancel</Btn>
        <Btn kind="primary" block>Save</Btn>
      </div>
    </div>
  </MobileFrame>
);

const TabletView = () => (
  <div className="artboard-root scroll-y rm">
    <Shell active="orgs" title="Organisations" collapsed>
      <div className="page-header">
        <div>
          <h1 className="page-title">Organisations</h1>
          <p className="page-sub">47 organisations · 212 stores</p>
        </div>
        <Btn kind="primary" icon={<Icon.Plus size={14}/>}>Create</Btn>
      </div>
      <FilterBar/>
      <OrgTable/>
    </Shell>
  </div>
);

Object.assign(window, { MobileList, MobileDrawer, MobileCreateModal, TabletView });
