// Component library showcase

const LibRow = ({ label, children, col = false }) => (
  <div style={{marginBottom:20}}>
    <div style={{fontSize:11, textTransform:'uppercase', letterSpacing:0.08, color:'var(--subtle)', fontWeight:500, marginBottom:10}}>{label}</div>
    <div style={{display:'flex', gap:12, alignItems:'center', flexDirection: col?'column':'row', alignItems: col?'flex-start':'center', flexWrap:'wrap'}}>{children}</div>
  </div>
);

const LibCard = ({ title, children, span = 1 }) => (
  <div style={{background:'#fff', border:'1px solid var(--line)', borderRadius:14, padding:'22px 24px', gridColumn:`span ${span}`}}>
    <div style={{fontSize:13, fontWeight:600, color:'var(--ink)', marginBottom:18, display:'flex', alignItems:'center', gap:6}}>
      <span style={{width:3, height:14, background:'var(--yellow)', borderRadius:2}}/> {title}
    </div>
    {children}
  </div>
);

const ComponentLibrary = () => (
  <div className="artboard-root scroll-y rm" style={{padding:32}}>
    <div style={{maxWidth:1200, margin:'0 auto'}}>
      <div style={{marginBottom:28}}>
        <div style={{fontSize:11, textTransform:'uppercase', letterSpacing:0.1, color:'var(--muted)', fontWeight:600, marginBottom:6}}>Review Master · Design tokens</div>
        <h1 style={{fontSize:28, fontWeight:600, letterSpacing:-0.02, margin:'0 0 6px'}}>Component library</h1>
        <p style={{color:'var(--muted)', fontSize:14, margin:0}}>Foundations, controls, feedback and data primitives used across every screen.</p>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16}}>
        <LibCard title="Palette">
          <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:10}}>
            {[
              ['#FACC15','Yellow 400','Primary'],
              ['#EAB308','Yellow 500','Hover'],
              ['#FEFCE8','Yellow 50','Tint'],
              ['#0A0A0A','Black','Ink'],
              ['#FAFAFA','Gray 50','Canvas'],
              ['#E4E4E7','Gray 200','Line'],
            ].map(([c,n,t])=>(
              <div key={n}>
                <div style={{height:44, borderRadius:8, background:c, border:'1px solid var(--line-soft)'}}/>
                <div style={{fontSize:11, fontWeight:500, marginTop:6}}>{n}</div>
                <div style={{fontSize:10.5, color:'var(--subtle)'}}>{t} · <span className="rm-mono">{c}</span></div>
              </div>
            ))}
          </div>
          <div style={{height:1, background:'var(--line-soft)', margin:'16px 0'}}/>
          <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:10}}>
            {[
              ['#16A34A','Success'],
              ['#DC2626','Danger'],
              ['#D97706','Warning'],
              ['#2563EB','Info'],
            ].map(([c,n])=>(
              <div key={n} style={{display:'flex', alignItems:'center', gap:8}}>
                <div style={{width:22, height:22, borderRadius:6, background:c}}/>
                <div>
                  <div style={{fontSize:11.5, fontWeight:500}}>{n}</div>
                  <div style={{fontSize:10, color:'var(--subtle)'}} className="rm-mono">{c}</div>
                </div>
              </div>
            ))}
          </div>
        </LibCard>

        <LibCard title="Typography">
          <div style={{fontSize:32, fontWeight:600, letterSpacing:-0.03, color:'var(--ink)', marginBottom:4}}>Display · 32/600</div>
          <div style={{fontSize:22, fontWeight:600, letterSpacing:-0.02, marginBottom:4}}>Page title · 22/600</div>
          <div style={{fontSize:15, fontWeight:600, marginBottom:4}}>Card title · 15/600</div>
          <div style={{fontSize:13.5, color:'var(--text)', marginBottom:4}}>Body · 13.5/400</div>
          <div style={{fontSize:12, color:'var(--subtle)', marginBottom:12}}>Caption · 12/400</div>
          <div style={{fontSize:11.5, fontWeight:500, color:'var(--subtle)', letterSpacing:0.08, textTransform:'uppercase'}}>Eyebrow · 11.5/500</div>
          <div style={{height:1, background:'var(--line-soft)', margin:'16px 0'}}/>
          <div style={{display:'flex', gap:24, fontSize:12}}>
            <div><span style={{color:'var(--subtle)'}}>Sans</span> · Geist</div>
            <div><span style={{color:'var(--subtle)'}}>Mono</span> · <span className="rm-mono">Geist Mono</span></div>
          </div>
        </LibCard>
      </div>

      <LibCard title="Buttons">
        <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:16}}>
          <div><div style={{fontSize:11, color:'var(--subtle)', marginBottom:8}}>Primary</div>
            <div style={{display:'flex', flexDirection:'column', gap:8, alignItems:'flex-start'}}>
              <Btn kind="primary" size="lg">Create Organisation</Btn>
              <Btn kind="primary">Save</Btn>
              <Btn kind="primary" size="sm">Apply</Btn>
              <Btn kind="primary" disabled>Disabled</Btn>
            </div>
          </div>
          <div><div style={{fontSize:11, color:'var(--subtle)', marginBottom:8}}>Secondary</div>
            <div style={{display:'flex', flexDirection:'column', gap:8, alignItems:'flex-start'}}>
              <Btn size="lg">Cancel</Btn>
              <Btn icon={<Icon.Edit size={14}/>}>Edit</Btn>
              <Btn size="sm">Filter</Btn>
              <Btn disabled>Disabled</Btn>
            </div>
          </div>
          <div><div style={{fontSize:11, color:'var(--subtle)', marginBottom:8}}>Danger</div>
            <div style={{display:'flex', flexDirection:'column', gap:8, alignItems:'flex-start'}}>
              <Btn kind="danger" size="lg">Delete organisation</Btn>
              <Btn kind="danger">Disable</Btn>
              <Btn kind="danger" size="sm">Remove</Btn>
            </div>
          </div>
          <div><div style={{fontSize:11, color:'var(--subtle)', marginBottom:8}}>Ghost</div>
            <div style={{display:'flex', flexDirection:'column', gap:8, alignItems:'flex-start'}}>
              <Btn kind="ghost" size="lg">View details</Btn>
              <Btn kind="ghost">Close</Btn>
              <Btn kind="ghost" size="sm">More</Btn>
            </div>
          </div>
        </div>
      </LibCard>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginTop:16}}>
        <LibCard title="Badges & status">
          <div style={{display:'flex', flexWrap:'wrap', gap:8, marginBottom:12}}>
            <Badge tone="green" dot>Active</Badge>
            <Badge tone="gray" dot>Disabled</Badge>
            <Badge tone="amber" dot>Pending invite</Badge>
            <Badge tone="red" dot>Invitation expired</Badge>
            <Badge tone="blue" dot>Info</Badge>
            <Badge tone="yellow" dot>Superadmin</Badge>
          </div>
          <div style={{display:'flex', flexWrap:'wrap', gap:8}}>
            <Badge tone="neutral">Retail</Badge>
            <Badge tone="neutral">Restaurant</Badge>
            <Badge tone="neutral">Pharmacy</Badge>
            <Badge tone="neutral">Supermarket</Badge>
          </div>
        </LibCard>

        <LibCard title="Inputs">
          <Field label="Text input"><Input placeholder="Organisation name"/></Field>
          <Field label="With error" error="Enter a valid email address."><Input error defaultValue="dara@example"/></Field>
          <Field label="Select"><Select><option>Retail</option><option>Restaurant</option></Select></Field>
        </LibCard>

        <LibCard title="Toasts">
          <div style={{display:'flex', flexDirection:'column', gap:10}}>
            <Toast kind="success" title="Organisation created" msg="Invitation email sent to finance@bellabistro.com."/>
            <Toast kind="info" title="Allocation updated" msg="Store allocation set to 15."/>
            <Toast kind="warning" title="Heads up" msg="This action cannot be undone."/>
            <Toast kind="error" title="Update failed" msg="Network error. Please retry."/>
          </div>
        </LibCard>

        <LibCard title="Empty state · Loading">
          <div style={{marginBottom:14}}>
            <div className="empty-state" style={{padding:'32px 16px'}}>
              <div className="empty-icon" style={{width:44, height:44}}><Icon.Building size={20}/></div>
              <div className="empty-title">No organisations yet</div>
              <p className="empty-desc" style={{marginBottom:10}}>Create your first organisation to get started.</p>
              <Btn kind="primary" size="sm" icon={<Icon.Plus size={12}/>}>Create</Btn>
            </div>
          </div>
          <div style={{background:'#fff', border:'1px solid var(--line)', borderRadius:10, padding:14}}>
            <div className="sk" style={{width:'60%', height:12, marginBottom:8}}/>
            <div className="sk" style={{width:'85%', height:12, marginBottom:8}}/>
            <div className="sk" style={{width:'40%', height:12}}/>
          </div>
        </LibCard>
      </div>

      <div style={{marginTop:16}}>
        <LibCard title="Icons (lucide-style)">
          <div style={{display:'grid', gridTemplateColumns:'repeat(10, 1fr)', gap:12, color:'var(--muted)'}}>
            {['Building','User','Users','Store','Shield','Bell','Search','Plus','Edit','Trash','Mail','Eye','EyeOff','AlertTriangle','AlertCircle','Info','CheckCircle','LogOut','Settings','Lock','RefreshCw','ChevronLeft','ChevronRight','ChevronDown','MoreHorizontal','Check','X','Menu','ArrowLeft','Circle'].map(n=>{
              const I = Icon[n];
              return (
                <div key={n} style={{display:'flex', flexDirection:'column', alignItems:'center', gap:4}}>
                  <div style={{width:36, height:36, borderRadius:8, border:'1px solid var(--line)', display:'flex', alignItems:'center', justifyContent:'center'}}><I size={16}/></div>
                  <div style={{fontSize:10, color:'var(--subtle)'}}>{n}</div>
                </div>
              );
            })}
          </div>
        </LibCard>
      </div>
    </div>
  </div>
);

Object.assign(window, { ComponentLibrary });
