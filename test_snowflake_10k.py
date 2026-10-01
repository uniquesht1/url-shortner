import time
from app.snowflake import SnowflakeGenerator
from app.base62 import encode


def test_10k_snowflake_uniqueness():
    print("=" * 65)
    print("  10,000-ID SNOWFLAKE UNIQUENESS & INTEGRITY TEST  ")
    print("=" * 65)

    TOTAL_IDS = 10_000
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)

    print(f"\n[Test 1] Generating {TOTAL_IDS:,} IDs in a tight loop...")
    generated_ids = []

    start_time = time.perf_counter()
    for _ in range(TOTAL_IDS):
        generated_ids.append(generator.next_id())
    elapsed_time = time.perf_counter() - start_time

    rate = TOTAL_IDS / elapsed_time
    print(f"Generated {TOTAL_IDS:,} IDs in {elapsed_time:.4f} seconds ({rate:,.0f} IDs/second)")

    # 1. Uniqueness check
    print("\n[Test 2] Verifying 100% Uniqueness...")
    unique_ids = set(generated_ids)
    print(f"  Total IDs Generated: {len(generated_ids):,}")
    print(f"  Unique IDs:          {len(unique_ids):,}")
    print(f"  Collisions:          {len(generated_ids) - len(unique_ids)}")

    assert len(unique_ids) == TOTAL_IDS, f"FAIL: Found {TOTAL_IDS - len(unique_ids)} duplicate IDs!"
    print("  >> PASSED: All 10,000 IDs are 100% unique!")

    # 2. Monotonicity check (Snowflake IDs must be strictly increasing)
    print("\n[Test 3] Verifying Chronological Monotonicity...")
    is_sorted = all(generated_ids[i] < generated_ids[i + 1] for i in range(TOTAL_IDS - 1))
    assert is_sorted, "FAIL: Snowflake IDs are not strictly increasing!"
    print("  >> PASSED: All 10,000 IDs are strictly monotonically increasing (k-sortable)!")

    # 3. Bitwise structure verification
    print("\n[Test 4] Verifying Bitwise Field Decomposition...")
    sample_indices = [0, TOTAL_IDS // 2, TOTAL_IDS - 1]
    for idx in sample_indices:
        id_val = generated_ids[idx]
        seq = id_val & 0xFFF  # last 12 bits
        mach = (id_val >> 12) & 0x1F  # 5 bits
        dc = (id_val >> 17) & 0x1F  # 5 bits
        ts = id_val >> 22  # top 42 bits

        print(f"  Sample ID #{idx}: {id_val}")
        print(f"    - Base62:       {encode(id_val)}")
        print(f"    - Timestamp:    {ts} ms")
        print(f"    - Datacenter:   {dc} (expected 1)")
        print(f"    - Machine ID:   {mach} (expected 1)")
        print(f"    - Sequence:     {seq} (0-4095 range)")

        assert dc == 1, f"Expected datacenter 1, got {dc}"
        assert mach == 1, f"Expected machine 1, got {mach}"
        assert 0 <= seq <= 4095, f"Sequence {seq} out of 12-bit range"

    print("  >> PASSED: Bitwise layout matches specification!")

    # 4. Multi-instance cross-collision test
    print("\n[Test 5] Multi-Instance Generation (Machine 1 vs Machine 2)...")
    gen1 = SnowflakeGenerator(datacenter_id=1, machine_id=1)
    gen2 = SnowflakeGenerator(datacenter_id=1, machine_id=2)

    gen1_ids = [gen1.next_id() for _ in range(5_000)]
    gen2_ids = [gen2.next_id() for _ in range(5_000)]

    cross_collision = set(gen1_ids).intersection(set(gen2_ids))
    print(f"  Machine 1 generated: {len(gen1_ids):,} IDs")
    print(f"  Machine 2 generated: {len(gen2_ids):,} IDs")
    print(f"  Cross-collisions:    {len(cross_collision)}")

    assert len(cross_collision) == 0, f"FAIL: Found cross collisions: {cross_collision}"
    print("  >> PASSED: Zero cross-collisions across separate machines!")

    print("\n" + "=" * 65)
    print(">>> 10,000-ID SNOWFLAKE GENERATOR VERIFICATION PASSED! <<<")
    print("=" * 65)


if __name__ == "__main__":
    test_10k_snowflake_uniqueness()
