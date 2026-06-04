/// Fixture for `DfgCollector` tests
struct DfgCollectTest : public DfgBuilder, public ::testing::Test {
  protected:
    /// Check that vertex with specified icount exists and return descriptor for it
    dfg::Vertex expect_vertex(uint64_t ic);
    /// Check that specified edge exists and return descriptor for it
    dfg::Edge expect_edge(dfg::Vertex src, dfg::Vertex dst,
                          uint64_t value, uint8_t gpr_id, uint8_t op_id);
    /// Check that specified edge exists and return descriptor for it
    dfg::Edge expect_edge(dfg::Vertex src, dfg::Vertex dst,
                          uint64_t value, const MemoryLocation &loc);
    /// Check that edge `src` has a destination hint pointing to `dst` edge
    void expect_src_dst_hint(dfg::Edge src, dfg::Edge dst);
};
