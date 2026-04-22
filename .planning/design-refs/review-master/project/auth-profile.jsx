// Login, Invitation acceptance, Profile

const LoginPage = ({ error = false, loading = false }) => (
  <div className="artboard-root rm auth-page">
    <div className="auth-split-left">
      <div style={{display:'flex', alignItems:'center', gap:10, zIndex:1}}>
        <div className="logo-mark" style={{width:36, height:36, borderRadius:9, fontSize:18}}>R</div>
        <div style={{fontSize:17, fontWeight:600, color:'#fff'}}>Review<span style={{color:'var(--yellow)'}}>Master</span></div>
      </div>
      <div style={{zIndex:1, maxWidth: 360}}>
        <div style={{fontSize:28, fontWeight:600, letterSpacing:-0.02, color:'#fff', marginBottom:12, lineHeight:1.2}}>
          The admin console for <span style={{color:'var(--yellow)'}}>multi-tenant retail.</span>
        </div>
        <div style={{fontSize:14, color:'#A1A1AA', lineHeight:1.55}}>
          Provision organisations, manage stores, and oversee every tenant from a single pane.
        </div>
      </div>
      <div style={{zIndex:1, fontSize:12, color:'#71717A'}}>© 2026 Review Master, Inc.</div>
    </div>
    <div className="auth-split-right">
      <div className="auth-card">
        <h1>Sign in to your account</h1>
        <p className="lede">Superadmin access for the Review Master platform.</p>
        {error && (
          <div className="inline-error">
            <Icon.AlertCircle/>
            <div><strong>Incorrect credentials.</strong> Please check your email and password and try again.</div>
          </div>
        )}
        <Field label="Email"><Input type="email" defaultValue="maya.grant@reviewmaster.io" error={error}/></Field>
        <Field label="Password">
          <PasswordInput value="wrongpass" error={error}/>
        </Field>
        <a href="#" className="forgot-link">Forgot password?</a>
        <Btn kind="primary" block size="lg" disabled={loading} icon={loading ? <span style={{display:'inline-block', width:14, height:14, border:'2px solid rgba(0,0,0,0.2)', borderTopColor:'var(--black)', borderRadius:'50%', animation:'spin 0.7s linear infinite'}}/> : null}>
          {loading ? 'Signing in…' : 'Sign in'}
        </Btn>
        <div style={{textAlign:'center', fontSize:12, color:'var(--subtle)', marginTop:24}}>
          Protected by Review Master SSO · <a href="#" style={{color:'var(--muted)'}}>Help</a>
        </div>
      </div>
    </div>
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

const InvitePage = ({ state = 'ok' }) => (
  <div className="artboard-root rm" style={{display:'flex', alignItems:'center', justifyContent:'center', padding:40, background:'var(--bg)'}}>
    <div style={{width:'100%', maxWidth:440, background:'#fff', border:'1px solid var(--line)', borderRadius:16, padding:36, boxShadow:'0 8px 32px rgba(0,0,0,0.04)'}}>
      <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:24}}>
        <div className="logo-mark">R</div>
        <div style={{fontSize:14, fontWeight:600}}>Review<span style={{color:'var(--yellow-hover)'}}>Master</span></div>
      </div>
      {state === 'expired' ? (
        <>
          <div style={{width:48, height:48, borderRadius:12, background:'var(--red-tint)', color:'var(--red)', display:'flex', alignItems:'center', justifyContent:'center', marginBottom:16}}>
            <Icon.AlertCircle size={22}/>
          </div>
          <h1 style={{fontSize:20, fontWeight:600, margin:'0 0 8px', letterSpacing:-0.01}}>Invitation expired</h1>
          <p style={{fontSize:13.5, color:'var(--muted)', margin:'0 0 24px', lineHeight:1.55}}>
            This invitation link is invalid or has expired. Please contact your administrator to request a new one.
          </p>
          <Btn block>Contact administrator</Btn>
        </>
      ) : state === 'used' ? (
        <>
          <div style={{width:48, height:48, borderRadius:12, background:'var(--line-soft)', color:'var(--muted)', display:'flex', alignItems:'center', justifyContent:'center', marginBottom:16}}>
            <Icon.CheckCircle size={22}/>
          </div>
          <h1 style={{fontSize:20, fontWeight:600, margin:'0 0 8px'}}>Invitation already used</h1>
          <p style={{fontSize:13.5, color:'var(--muted)', margin:'0 0 24px'}}>This invitation has already been accepted. Sign in to your account to continue.</p>
          <Btn kind="primary" block>Go to sign in</Btn>
        </>
      ) : (
        <>
          <h1 style={{fontSize:22, fontWeight:600, margin:'0 0 6px', letterSpacing:-0.02}}>Welcome to Bella Bistro Group</h1>
          <p style={{fontSize:13.5, color:'var(--muted)', margin:'0 0 24px'}}>Create your Organisation Admin account to get started.</p>
          <Field label="Email"><Input type="email" value="finance@bellabistro.com" disabled readOnly/></Field>
          <Field label="Full name" required><Input placeholder="e.g., Dara Okafor"/></Field>
          <Field label="Password" required>
            <PasswordInput value="My$ecure2026"/>
            <Strength level={3} label="Strong — add a symbol to reach 'Very strong'"/>
          </Field>
          <Field label="Confirm password" required><PasswordInput/></Field>
          <Btn kind="primary" block size="lg" style={{marginTop:4}}>Create account</Btn>
          <p style={{fontSize:11.5, color:'var(--subtle)', textAlign:'center', marginTop:16}}>
            By creating an account you agree to the <a href="#" style={{color:'var(--muted)'}}>Terms of Service</a>.
          </p>
        </>
      )}
    </div>
  </div>
);

const ProfilePage = () => (
  <div className="artboard-root scroll-y rm">
    <Shell active="profile" title="Profile">
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-sub">Manage your account details and security.</p>
        </div>
      </div>
      <div style={{display:'grid', gridTemplateColumns:'260px 1fr', gap:32, alignItems:'start'}}>
        <div style={{position:'sticky', top:0}}>
          <div className="card" style={{padding:20, textAlign:'center'}}>
            <div style={{width:72, height:72, borderRadius:'50%', background:'var(--black)', color:'var(--yellow)', display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:22, fontWeight:600, marginBottom:12}}>MG</div>
            <div style={{fontSize:15, fontWeight:600, color:'var(--ink)'}}>Maya Grant</div>
            <div style={{fontSize:12.5, color:'var(--muted)', marginBottom:10}}>maya.grant@reviewmaster.io</div>
            <Badge tone="yellow" dot>Superadmin</Badge>
          </div>
          <div className="card" style={{padding:14}}>
            <div style={{fontSize:12, color:'var(--subtle)', textTransform:'uppercase', letterSpacing:0.05, marginBottom:8, fontWeight:500}}>Session</div>
            <div style={{fontSize:12.5, color:'var(--muted)', lineHeight:1.6}}>
              <div>Signed in from New York, NY</div>
              <div>IP 173.211.82.14</div>
              <div>Last login Apr 21, 2026, 9:42 AM</div>
            </div>
          </div>
        </div>
        <div style={{maxWidth:620}}>
          <div className="card">
            <h3 className="card-title">Profile information</h3>
            <p className="card-sub">Update your personal details. Your email is used for sign-in and cannot be changed.</p>
            <Field label="Full name"><Input defaultValue="Maya Grant"/></Field>
            <Field label="Email"><Input defaultValue="maya.grant@reviewmaster.io" disabled/></Field>
            <div className="card-divider"/>
            <div style={{display:'flex', justifyContent:'flex-end'}}><Btn kind="primary">Save changes</Btn></div>
          </div>
          <div className="card">
            <h3 className="card-title">Change password</h3>
            <p className="card-sub">For security, choose a password at least 12 characters with a mix of letters, numbers, and symbols.</p>
            <Field label="Current password"><PasswordInput/></Field>
            <Field label="New password">
              <PasswordInput/>
              <Strength level={4} label="Very strong"/>
            </Field>
            <Field label="Confirm new password"><PasswordInput/></Field>
            <div className="card-divider"/>
            <div style={{display:'flex', justifyContent:'flex-end', gap:8}}>
              <Btn>Cancel</Btn><Btn kind="primary">Update password</Btn>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  </div>
);

Object.assign(window, { LoginPage, InvitePage, ProfilePage });
