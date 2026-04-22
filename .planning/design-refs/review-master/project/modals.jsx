// All modals & confirmation popups

const CreateOrgModal = ({ title = 'Create New Organisation', sub = 'Enter the organisation details to get started.', isEdit = false }) => (
  <Modal size="" title={title} sub={sub} footer={<><Btn>Cancel</Btn><Btn kind="primary">{isEdit?'Save changes':'Save'}</Btn></>}>
    <Field label="Organisation name" required>
      <Input placeholder="e.g., Example Corp" defaultValue={isEdit?'Bella Bistro Group':''} />
    </Field>
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:14}}>
      <Field label="Organisation type" required>
        <Select defaultValue={isEdit?'Restaurant':''}>
          <option value="">Select organisation type</option>
          <option>Retail</option><option>Restaurant</option><option>Pharmacy</option><option>Supermarket</option>
        </Select>
      </Field>
      <Field label="Number of stores" required>
        <Input type="number" placeholder="e.g., 5" defaultValue={isEdit?'12':''} />
      </Field>
    </div>
    <Field label="Address">
      <Textarea placeholder="e.g., 123 Main St, City, State, ZIP" defaultValue={isEdit?'48 Canal St, Brooklyn, NY 11222':''} />
    </Field>
    <Field label="Email" required help={isEdit?'Email cannot be changed after creation.':'Invitation will be sent to this address.'}>
      <Input type="email" placeholder="e.g., contact@example.com" defaultValue={isEdit?'finance@bellabistro.com':''} disabled={isEdit}/>
    </Field>
  </Modal>
);

const DetailsModal = () => (
  <Modal title="Bella Bistro Group" sub="Created Mar 14, 2026 · ID ORG-4821"
    footer={<><Btn icon={<Icon.Mail size={14}/>}>Resend invitation</Btn><Btn icon={<Icon.Edit size={14}/>}>Edit</Btn><Btn kind="primary">Close</Btn></>}>
    <div className="info-grid">
      <dt>Name</dt><dd>Bella Bistro Group</dd>
      <dt>Type</dt><dd><Badge tone="neutral">Restaurant</Badge></dd>
      <dt>Address</dt><dd>48 Canal St, Brooklyn, NY 11222</dd>
      <dt>Email</dt><dd className="mono">finance@bellabistro.com</dd>
      <dt>Stores</dt><dd><StoreCount used={8} alloc={12} /> <span style={{color:'var(--subtle)', fontSize:12, marginLeft:6}}>(4 available)</span></dd>
      <dt>Status</dt><dd><Badge tone="green" dot>Active</Badge></dd>
      <dt>Created</dt><dd>Mar 14, 2026</dd>
      <dt>Org admin</dt><dd>
        <Badge tone="amber" dot>Pending invite</Badge>
        <div style={{fontSize:12, color:'var(--subtle)', marginTop:4}}>Last invite sent Apr 18, 2026, 2:14 PM</div>
      </dd>
    </div>
  </Modal>
);

const AdjustStoreModal = ({ warn = false }) => (
  <Modal size="sm" title="Adjust allocated stores"
    footer={<><Btn>Cancel</Btn><Btn kind="primary">Update</Btn></>}>
    <div style={{background:'var(--bg)', border:'1px solid var(--line)', borderRadius:10, padding:'12px 14px', marginBottom:16, display:'flex', alignItems:'center', gap:10}}>
      <Icon.Store size={18} style={{color:'var(--muted)'}}/>
      <div style={{fontSize:13}}>
        Currently using <strong>8</strong> of <strong>12</strong> stores
      </div>
    </div>
    <Field label="New allocation" required
      help={!warn && 'Minimum: 8 (current in-use count)'}
      warn={warn && 'You cannot set this below the current in-use count (8).'}>
      <Input type="number" defaultValue={warn?'5':'15'} error={warn}/>
    </Field>
  </Modal>
);

const DisableConfirm = () => (
  <ConfirmModal tone="amber" icon={<Icon.AlertTriangle/>} title="Disable organisation?"
    message={<>The organisation <strong style={{color:'var(--ink)'}}>'Bella Bistro Group'</strong> and all its stores will be inaccessible. You can re-enable it later.</>}
    footer={<><Btn>Cancel</Btn><Btn kind="danger">Disable</Btn></>}/>
);

const EnableConfirm = () => (
  <ConfirmModal tone="blue" icon={<Icon.Info/>} title="Enable organisation?"
    message={<>The organisation <strong style={{color:'var(--ink)'}}>'Meridian Pharmacy'</strong> will regain access.</>}
    footer={<><Btn>Cancel</Btn><Btn kind="primary">Enable</Btn></>}/>
);

const DeleteConfirm = () => (
  <ConfirmModal tone="red" icon={<Icon.AlertCircle/>} title="Delete organisation?"
    message={<>This will permanently delete <strong style={{color:'var(--ink)'}}>'Bella Bistro Group'</strong> and all associated data. This action cannot be undone.</>}
    footer={<><Btn>Cancel</Btn><Btn kind="danger" disabled>Delete</Btn></>}>
    <div style={{marginTop:16}}>
      <div className="type-confirm">Type <code>Bella Bistro Group</code> to confirm</div>
      <Input placeholder="Organisation name" />
    </div>
  </ConfirmModal>
);

const ResendConfirm = () => (
  <ConfirmModal tone="blue" icon={<Icon.Mail/>} title="Resend invitation?"
    message={<>A new invitation link will be sent to <strong style={{color:'var(--ink)'}}>finance@bellabistro.com</strong>. The previous link will be invalidated.</>}
    footer={<><Btn>Cancel</Btn><Btn kind="primary">Resend</Btn></>}/>
);

// Artboards: modal-over-list
const ModalArtboard = ({ children }) => (
  <div className="artboard-root rm" style={{position:'relative'}}>
    <div style={{position:'absolute',inset:0,filter:'blur(0.5px)',opacity:0.55,transform:'scale(1)',transformOrigin:'top left'}}>
      <OrgListArtboard />
    </div>
    {children}
  </div>
);

Object.assign(window, { CreateOrgModal, DetailsModal, AdjustStoreModal, DisableConfirm, EnableConfirm, DeleteConfirm, ResendConfirm, ModalArtboard });
