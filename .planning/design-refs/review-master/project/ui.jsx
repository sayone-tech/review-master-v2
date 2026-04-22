// Shared UI primitives used across artboards
const { Icon } = window;

const Badge = ({ tone = 'neutral', children, dot }) => (
  <span className={`badge badge-${tone}`}>
    {dot && <span className="ind" />}
    {children}
  </span>
);

const Btn = ({ kind = 'secondary', size, block, children, icon, disabled, ...rest }) => {
  const cls = ['btn', `btn-${kind}`, size && `btn-${size}`, block && 'btn-block'].filter(Boolean).join(' ');
  return <button className={cls} disabled={disabled} {...rest}>{icon}{children}</button>;
};

// Sidebar
const Sidebar = ({ active = 'orgs', collapsed = false }) => (
  <aside className="sidebar" style={collapsed ? { width: 64 } : {}}>
    <div className="sidebar-logo" style={collapsed ? { padding: '4px 18px 28px', justifyContent: 'center' } : {}}>
      <div className="logo-mark">R</div>
      {!collapsed && <div className="logo-text">Review<em>Master</em></div>}
    </div>
    {!collapsed && <div className="sidebar-section-label">Manage</div>}
    <nav>
      <div className={`nav-item ${active === 'orgs' ? 'active' : ''}`} style={collapsed ? {justifyContent:'center', padding:'10px 0'} : {}}>
        <Icon.Building size={18} />{!collapsed && 'Organisations'}
      </div>
      <div className={`nav-item ${active === 'profile' ? 'active' : ''}`} style={collapsed ? {justifyContent:'center', padding:'10px 0'} : {}}>
        <Icon.User size={18} />{!collapsed && 'Profile'}
      </div>
    </nav>
    <div className="sidebar-footer">
      <div className="nav-item" style={collapsed ? {justifyContent:'center', padding:'10px 0'} : {}}>
        <Icon.LogOut size={18} />{!collapsed && 'Log out'}
      </div>
      {!collapsed && (
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">MG</div>
          <div>
            <div style={{ color: '#fff', fontWeight: 500 }}>Maya Grant</div>
            <div style={{ fontSize: 11, color: '#71717A' }}>Superadmin</div>
          </div>
        </div>
      )}
    </div>
  </aside>
);

// Topbar
const Topbar = ({ title = 'Organisations', crumb, hasNotif = true }) => (
  <header className="topbar">
    <div className="topbar-title">
      {crumb ? (<><span>{crumb} </span><strong>{title}</strong></>) : <strong>{title}</strong>}
    </div>
    <div className="topbar-right">
      <button className="icon-btn" aria-label="Notifications">
        <Icon.Bell size={18} />
        {hasNotif && <span className="dot" />}
      </button>
      <div className="avatar">MG</div>
    </div>
  </header>
);

// Stacked App Shell
const Shell = ({ active = 'orgs', title = 'Organisations', crumb, children, collapsed }) => (
  <div className="shell">
    <Sidebar active={active} collapsed={collapsed} />
    <div className="main">
      <Topbar title={title} crumb={crumb} />
      <div className="content">{children}</div>
    </div>
  </div>
);

// Dropdown menu — static, shown inline (non-interactive mockup)
const RowMenu = ({ items, align = 'right', style = {} }) => (
  <div className="menu" style={{ position: 'absolute', top: '100%', [align]: 0, marginTop: 4, zIndex: 20, ...style }}>
    {items.map((it, i) => it === '---' ? (
      <div key={i} className="menu-divider" />
    ) : (
      <div key={i} className={`menu-item ${it.danger ? 'danger' : ''}`}>
        {it.icon}
        <span>{it.label}</span>
      </div>
    ))}
  </div>
);

// Password strength bars
const Strength = ({ level = 3, label = 'Strong' }) => (
  <div className="strength">
    <div className="strength-bars">
      {[1,2,3,4].map(i => (
        <div key={i} className={`strength-bar ${i <= level ? 's'+level : ''}`} />
      ))}
    </div>
    <div className="strength-label">{label}</div>
  </div>
);

// Field helpers
const Field = ({ label, required, error, help, warn, children }) => (
  <div className="field">
    {label && <label className="field-label">{label}{required && <span className="req">*</span>}</label>}
    {children}
    {warn && <div className="field-warn"><Icon.AlertTriangle size={14}/><span>{warn}</span></div>}
    {error && <div className="field-error"><Icon.AlertCircle size={12}/>{error}</div>}
    {help && !error && <div className="field-help">{help}</div>}
  </div>
);

const Input = ({ error, ...p }) => <input className={`input ${error ? 'input-error':''}`} {...p} />;
const Textarea = ({ error, ...p }) => <textarea className={`textarea ${error ? 'input-error':''}`} {...p} />;
const Select = ({ children, ...rest }) => <select className="select" style={{width:'100%'}} {...rest}>{children}</select>;

const PasswordInput = ({ show = false, placeholder = '••••••••', value, error }) => (
  <div className="password-wrap">
    <input className={`input ${error?'input-error':''}`} type={show?'text':'password'} placeholder={placeholder} defaultValue={value} style={{paddingRight: 40}} />
    <button className="eye" tabIndex={-1} type="button">
      {show ? <Icon.Eye size={16}/> : <Icon.EyeOff size={16}/>}
    </button>
  </div>
);

// Modal container within an artboard (no portal). Width control via className.
const Modal = ({ size = '', title, sub, onClose, children, footer, hasBackdrop = true }) => (
  <div className={hasBackdrop ? 'modal-backdrop' : ''} style={!hasBackdrop ? {position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',padding:24} : {}}>
    <div className={`modal ${size === 'sm' ? 'modal-sm' : size === 'lg' ? 'modal-lg' : ''}`}>
      <div className="modal-header">
        <div>
          <h3 className="modal-title">{title}</h3>
          {sub && <p className="modal-sub">{sub}</p>}
        </div>
        <button className="modal-close" aria-label="Close"><Icon.X size={18}/></button>
      </div>
      <div className="modal-body">{children}</div>
      {footer && <div className="modal-footer">{footer}</div>}
    </div>
  </div>
);

const ConfirmModal = ({ tone, icon, title, message, children, footer }) => (
  <div className="modal-backdrop">
    <div className="modal modal-sm">
      <div style={{ padding: '24px 24px 8px', display: 'flex', gap: 14 }}>
        <div className={`confirm-icon ${tone}`}>{icon}</div>
        <div style={{flex:1}}>
          <h3 className="modal-title" style={{marginBottom:6}}>{title}</h3>
          <p style={{fontSize:13.5, color:'var(--muted)', margin:0, lineHeight:1.5}}>{message}</p>
          {children}
        </div>
      </div>
      <div className="modal-footer">{footer}</div>
    </div>
  </div>
);

const Toast = ({ kind = 'success', title, msg, icon }) => (
  <div className={`toast toast-${kind}`}>
    {icon || (kind==='success'?<Icon.CheckCircle size={18}/>:kind==='error'?<Icon.AlertCircle size={18}/>:kind==='warning'?<Icon.AlertTriangle size={18}/>:<Icon.Info size={18}/>)}
    <div style={{flex:1, minWidth:0}}>
      {title && <div className="toast-title">{title}</div>}
      {msg && <div className="toast-msg">{msg}</div>}
    </div>
    <button style={{background:'transparent',border:'none',color:'#71717A',cursor:'pointer',padding:0,marginLeft:4}}><Icon.X size={14}/></button>
  </div>
);

// Store count formatted
const StoreCount = ({ used, alloc }) => (
  <span className="store-count">{used}<span className="slash"> / </span><span className="alloc">{alloc}</span></span>
);

Object.assign(window, { Badge, Btn, Sidebar, Topbar, Shell, RowMenu, Strength, Field, Input, Textarea, Select, PasswordInput, Modal, ConfirmModal, Toast, StoreCount });
