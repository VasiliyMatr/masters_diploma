/// Test for `ldp` instruction processing based on `DfgCollectTest` fixture
TEST_F(DfgCollectTest, ldpImmediateOffset) {
    auto bb1 = bb(
        "ldp x3, x4, [sp, #16]",
            Ld{sp() + 16, {uint64_t{10}, uint64_t{20}}},
        "add x5, x3, x4"
    );
    DfgBuilder::finalize();

    expect_edge(init(), bb1.vertex(0), sp(), uint8_t{31}, uint8_t{2});
    // Check edges from initial memory to `ldp`
    auto edge_init_to_ldp_mem0 = expect_edge(init(), bb1.vertex(0), 10, ....);
    auto edge_init_to_ldp_mem1 = expect_edge(init(), bb1.vertex(0), 20, ....);
    // Check edges from `ldp` to `add`
    auto edge_ldp_to_add_x3 = expect_edge(bb1.vertex(0), bb1.vertex(1), 10, ....);
    auto edge_ldp_to_add_x4 = expect_edge(bb1.vertex(0), bb1.vertex(1), 20, ....);

    // Check hints for related edges
    expect_src_dst_hint(edge_init_to_ldp_mem0, edge_ldp_to_add_x3);
    expect_src_dst_hint(edge_init_to_ldp_mem1, edge_ldp_to_add_x4);
}
