/// Trace-based simulation for memory record.
/// Called before related instruction simulation for data injection.
/* virtual */ void TraceSim::process_pre_mem(const trace::MemEvent &ev) {
    switch (ev.kind) {
    case trace::MemEventKind::Load:
        // Inject trace data
        m_sim->write_virt_mem(ev.addr, ev.data);
        break;
    case trace::MemEventKind::Store:
        // Allocate touched memory region
        m_sim->allocate_virt_mem(ev.addr, ev.data.size());
        break;
    }
}

/// Patched trace-based simulation for memory record.
/// Patch trace record and delegate to base method.
void PatchedTraceSim::process_pre_mem(const utl::MemEvent &ev) /* override */ {
    // Patch event
    auto new_ev = m_patches.patch_mem_event(m_current_instruction, ev);
    // Delegate
    TraceSim::process_pre_mem(new_ev);
}
