/// DFG builder for testing
struct DfgBuilder {
    /// Set sim gpr
    void set_gpr(uint8_t id, uint64_t value);

    /// Simulator data getters
    uint64_t pc() const;
    uint64_t sp() const;
    uint64_t icount() const;

    /// Sink vertices getters
    dfg::Vertex init() const;
    dfg::Vertex extmod() const;
    dfg::Vertex complex() const;

    /// Info about test basic block
    struct BasicBlockInfo {
        const dfg::DfgData &dfg_data;
        /// Global icount range
        uint64_t start_ic = 0;
        uint64_t end_ic = 0;

        // Helper getters ...
    };

    /// Info about load
    struct Ld {
        uint64_t addr = 0;
        std::vector<uint8_t> data;
    };

    /// Info about store
    struct St {
        uint64_t addr = 0;
        std::vector<uint8_t> data;
    };

    /// Add specified basic block & return aggregated info about it
    template <class... Args>
    BasicBlockInfo bb(Args &&...args);

    /// Finalize DFG building
    void finalize();
};
